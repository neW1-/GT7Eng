from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass

from .alerts import AlertManager
from .config import AppConfig
from .llm import OpenAICompatibleClient
from .models import Alert, RaceSnapshot, TelemetryFrame
from .state import RaceState
from .telemetry import CaptureWriter, TelemetrySource
from .voice import VoiceResult, parse_voice_command


@dataclass(slots=True)
class VoiceJob:
    id: str
    kind: str
    text: str
    alert_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "alert_id": self.alert_id,
        }


class RaceEngineerService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.state = RaceState(config)
        self.alerts = AlertManager(config)
        self.llm = OpenAICompatibleClient(config.llm)
        self.alert_log: deque[Alert] = deque(maxlen=500)
        self.voice_jobs: deque[VoiceJob] = deque(maxlen=500)
        self.acked_voice_jobs: set[str] = set()
        self._source_task: asyncio.Task | None = None
        self._capture: CaptureWriter | None = None
        self._muted = False

    @property
    def snapshot(self) -> RaceSnapshot:
        snapshot = self.state.stale_snapshot()
        self._append_alerts(self.alerts.connection_alerts(snapshot))
        return snapshot

    def update_frame(self, frame: TelemetryFrame) -> list[Alert]:
        update = self.state.update(frame)
        alerts = self.alerts.from_update(update)
        if self._capture:
            self._capture.write(frame)
        self._append_alerts(alerts)
        return alerts

    def start_capture(self, capture: CaptureWriter) -> None:
        self._capture = capture

    def stop_capture(self) -> None:
        if self._capture:
            self._capture.close()
        self._capture = None

    async def start_source(self, source: TelemetrySource) -> None:
        if self._source_task and not self._source_task.done():
            return
        self._source_task = asyncio.create_task(self._consume_source(source))

    async def stop_source(self) -> None:
        if self._source_task:
            self._source_task.cancel()
            try:
                await self._source_task
            except asyncio.CancelledError:
                pass

    def handle_command(self, text: str, source: str = "text") -> dict:
        result = parse_voice_command(text, self.snapshot, self.config)
        if result.ignored:
            return self._command_response(text, result, source)
        if result.handled:
            self._apply_intent(result)
            response = self._command_response(text, result, source)
            self._queue_response_voice_job(response)
            return response

        answer = self.llm.ask(text, self.snapshot)
        result = VoiceResult(True, False, "llm_question", answer, 0.5)
        response = self._command_response(text, result, source)
        self._queue_response_voice_job(response)
        return response

    def handle_transcript(
        self,
        text: str,
        source: str = "discord",
        confidence: float = 1.0,
    ) -> dict:
        if confidence < self.config.stt.min_confidence:
            result = VoiceResult(False, True, "low_confidence", "", confidence)
            return self._command_response(text, result, source)

        result = parse_voice_command(text, self.snapshot, self.config)
        if result.ignored:
            return self._command_response(text, result, source)
        if result.handled:
            self._apply_intent(result)
            response = self._command_response(text, result, source)
            self._queue_response_voice_job(response)
            return response

        if self.config.voice_mode == "quiet_driver":
            ignored = VoiceResult(False, True, "unknown_quiet_driver", "", result.confidence)
            return self._command_response(text, ignored, source)

        answer = self.llm.ask(text, self.snapshot)
        result = VoiceResult(True, False, "llm_question", answer, 0.5)
        response = self._command_response(text, result, source)
        self._queue_response_voice_job(response)
        return response

    def alerts_after(self, after_id: int = 0, speak_only: bool = False) -> list[dict]:
        items = [
            alert
            for alert in self.alert_log
            if alert.id > after_id and (not speak_only or alert.speak)
        ]
        if self._muted:
            items = [alert for alert in items if alert.priority == "critical"]
        return [alert.to_dict() for alert in items]

    def status(self) -> dict:
        return {
            "snapshot": self.snapshot.to_dict(),
            "alerts": [alert.to_dict() for alert in list(self.alert_log)[-25:]],
            "voice": {
                "mode": self.config.voice_mode,
                "wake_phrase": self.config.wake_phrase,
                "muted": self._muted,
                "stt_enabled": self.config.stt.enabled,
            },
            "config": {
                "preset": self.config.preset,
                "verbosity": self.config.verbosity,
                "heartbeat_type": self.config.heartbeat_type,
                "race_duration_minutes": self.config.race_duration_minutes,
                "stt": {
                    "enabled": self.config.stt.enabled,
                    "engine": self.config.stt.engine,
                    "model": self.config.stt.model,
                },
                "tts": {
                    "engine": self.config.tts.engine,
                    "radio_effects": self.config.tts.radio_effects,
                },
            },
        }

    def next_voice_jobs(self, limit: int = 1) -> list[dict]:
        jobs: list[dict] = []
        while self.voice_jobs and len(jobs) < limit:
            job = self.voice_jobs.popleft()
            if job.id in self.acked_voice_jobs:
                continue
            jobs.append(job.to_dict())
        return jobs

    def acknowledge_voice_job(self, job_id: str, status: str) -> None:
        self.acked_voice_jobs.add(job_id)

    def set_muted(self, muted: bool) -> None:
        self._muted = muted

    def set_voice_mode(self, mode: str) -> None:
        if mode in {"wake_phrase", "quiet_driver"}:
            self.config.voice_mode = mode  # type: ignore[assignment]
        elif mode == "silent":
            self._muted = True

    async def _consume_source(self, source: TelemetrySource) -> None:
        async for frame in source.frames():
            self.update_frame(frame)

    def _append_alerts(self, alerts: list[Alert]) -> None:
        for alert in alerts:
            self.alert_log.append(alert)
            if alert.speak and (not self._muted or alert.priority == "critical"):
                self.voice_jobs.append(
                    VoiceJob(
                        id=f"alert-{alert.id}",
                        kind="tts",
                        text=alert.message,
                        alert_id=alert.id,
                    )
                )

    def _apply_intent(self, result: VoiceResult) -> None:
        if result.intent == "keep_quiet":
            self._muted = True
        elif result.intent == "more_fuel_updates":
            self.config.verbosity["fuel"] = "detailed"
            self._muted = False
        elif result.intent == "radio_check":
            self._muted = False
        elif result.intent == "set_race_duration" and result.race_duration_minutes:
            self.config.race_duration_minutes = result.race_duration_minutes

    def _command_response(self, text: str, result: VoiceResult, source: str) -> dict:
        return {
            "received_at": time.time(),
            "source": source,
            "text": text,
            "handled": result.handled,
            "ignored": result.ignored,
            "intent": result.intent,
            "confidence": result.confidence,
            "response": result.response,
            "speak": bool(result.response and not result.ignored),
        }

    def _queue_response_voice_job(self, response: dict) -> None:
        if response["source"] != "discord" or not response["speak"]:
            return
        if self.config.tts.radio_effects:
            self.voice_jobs.append(
                VoiceJob(
                    id=f"tone-{int(response['received_at'] * 1000)}",
                    kind="tone",
                    text="confirmation",
                )
            )
        self.voice_jobs.append(
            VoiceJob(
                id=f"response-{int(response['received_at'] * 1000)}",
                kind="tts",
                text=response["response"],
            )
        )
