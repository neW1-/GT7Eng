from __future__ import annotations

import asyncio
import re
import time
from collections import deque
from dataclasses import dataclass

from .alerts import AlertManager
from .config import AppConfig
from .llm import IntentRepair, OpenAICompatibleClient
from .models import Alert, RaceSnapshot, TelemetryFrame
from .pixel_display import PixelDisplayManager
from .second_display import SecondDisplayManager
from .state import RaceState
from .telemetry import CaptureWriter, TelemetrySource
from .timefmt import format_spoken_delta
from .voice import VoiceResult, parse_voice_command
from .wind import HomeAssistantWindManager


@dataclass(slots=True)
class VoiceJob:
    id: str
    kind: str
    text: str
    alert_id: int | None = None
    category: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "alert_id": self.alert_id,
            "category": self.category,
        }


@dataclass(slots=True)
class ConversationFact:
    intent: str
    question: str
    response: str
    data: dict[str, object]
    created_at: float

    def to_dict(self, now: float) -> dict:
        return {
            "intent": self.intent,
            "question": self.question,
            "response": self.response,
            "age_seconds": max(0.0, now - self.created_at),
            "data": self.data,
        }


class ConversationMemory:
    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl_seconds = ttl_seconds
        self._fact: ConversationFact | None = None

    def remember(
        self,
        intent: str,
        question: str,
        response: str,
        data: dict[str, object] | None,
        *,
        now: float | None = None,
    ) -> None:
        if not data:
            self.clear()
            return
        timestamp = time.time() if now is None else now
        self._fact = ConversationFact(
            intent=intent,
            question=question,
            response=response,
            data=data,
            created_at=timestamp,
        )

    def clear(self) -> None:
        self._fact = None

    def current(self, now: float | None = None) -> ConversationFact | None:
        if self._fact is None:
            return None
        timestamp = time.time() if now is None else now
        if timestamp - self._fact.created_at > self.ttl_seconds:
            self.clear()
            return None
        return self._fact

    def snapshot(self, now: float | None = None) -> dict | None:
        timestamp = time.time() if now is None else now
        fact = self.current(timestamp)
        return fact.to_dict(timestamp) if fact is not None else None

    def resolve_follow_up(
        self,
        text: str,
        snapshot: RaceSnapshot,
        *,
        now: float | None = None,
    ) -> VoiceResult | None:
        normalized = _normalize_memory_text(text)
        if not _looks_like_follow_up(normalized):
            return None

        fact = self.current(now)
        if fact is None:
            return VoiceResult(
                True,
                False,
                "follow_up_unavailable",
                "I need a recent answer to refer back to.",
                0.45,
            )

        if _asks_which_lap(normalized):
            lap_number = fact.data.get("lap_number")
            if isinstance(lap_number, int) and lap_number > 0:
                return VoiceResult(
                    True,
                    False,
                    "follow_up_lap",
                    f"That was lap {lap_number}.",
                    1.0,
                )
            return VoiceResult(
                True,
                False,
                "follow_up_unavailable",
                "That did not refer to a specific lap.",
                0.7,
            )

        if _asks_sample_count(normalized):
            sample_count = fact.data.get("fuel_sample_count")
            if isinstance(sample_count, int) and sample_count > 0:
                plural = "sample" if sample_count == 1 else "samples"
                return VoiceResult(
                    True,
                    False,
                    "follow_up_sample_count",
                    f"That is based on {sample_count} completed fuel {plural}.",
                    1.0,
                )

        if _asks_total_cars(normalized):
            total_cars = fact.data.get("total_cars") or snapshot.total_cars
            if isinstance(total_cars, int) and total_cars > 0:
                return VoiceResult(
                    True,
                    False,
                    "follow_up_total_cars",
                    f"{total_cars} cars total.",
                    1.0,
                )

        if _asks_how_much_that(normalized):
            response = _amount_response(fact)
            if response is not None:
                return VoiceResult(True, False, "follow_up_amount", response, 1.0)

        if _asks_faster_than_best(normalized):
            response = _faster_than_best_response(fact, snapshot)
            if response is not None:
                return VoiceResult(True, False, "follow_up_best_delta", response, 1.0)

        if _asks_repeat(normalized):
            return VoiceResult(
                True,
                False,
                "follow_up_repeat",
                f"I said: {fact.response}",
                1.0,
            )

        return None


class RaceEngineerService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.state = RaceState(config)
        self.alerts = AlertManager(config)
        self.llm = OpenAICompatibleClient(config.llm)
        self.conversation_memory = ConversationMemory()
        self.alert_log: deque[Alert] = deque(maxlen=500)
        self.voice_jobs: deque[VoiceJob] = deque(maxlen=500)
        self.acked_voice_jobs: set[str] = set()
        self._source_task: asyncio.Task | None = None
        self._capture: CaptureWriter | None = None
        self._muted = config.engineer_muted
        self._last_voice_debug: dict = {}
        self._sync_second_display_theme()
        self.pixel_display = PixelDisplayManager(
            config.pixel_display,
            snapshot_provider=self.state.stale_snapshot,
        )
        self.second_display = SecondDisplayManager(
            config.second_display,
            snapshot_provider=self.state.stale_snapshot,
        )
        self.wind = HomeAssistantWindManager(
            config.wind,
            snapshot_provider=self.state.stale_snapshot,
        )

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
        self.pixel_display.publish(update.snapshot)
        self.second_display.publish(update.snapshot)
        self.wind.publish(update.snapshot)
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

    async def start_pixel_display(self) -> None:
        await self.pixel_display.start()

    async def stop_pixel_display(self) -> None:
        await self.pixel_display.stop()

    async def reconfigure_pixel_display(self) -> None:
        await self.pixel_display.reconfigure()
        if self._sync_second_display_theme():
            await self.second_display.reconfigure()

    async def start_second_display(self) -> None:
        if self._sync_second_display_theme():
            await self.second_display.reconfigure()
        await self.second_display.start()

    async def stop_second_display(self) -> None:
        await self.second_display.stop()

    async def reconfigure_second_display(self) -> None:
        self._sync_second_display_theme()
        await self.second_display.reconfigure()

    async def start_wind(self) -> None:
        await self.wind.start()

    async def stop_wind(self) -> None:
        await self.wind.stop()

    async def reconfigure_wind(self) -> None:
        await self.wind.reconfigure()

    async def stop_source(self) -> None:
        if self._source_task:
            self._source_task.cancel()
            try:
                await self._source_task
            except asyncio.CancelledError:
                pass

    def handle_command(self, text: str, source: str = "text") -> dict:
        self._prepare_for_driver_request(source)
        snapshot = self._snapshot_for_request(source)
        follow_up = self._resolve_follow_up(text, snapshot)
        if follow_up is not None:
            response = self._command_response(text, follow_up, source)
            self._queue_response_voice_job(response)
            return response

        result = parse_voice_command(text, snapshot, self.config)
        if result.ignored:
            return self._command_response(text, result, source)
        if result.handled:
            self._apply_intent(result)
            response = self._command_response(text, result, source)
            self._remember_response(text, result, response, snapshot)
            self._queue_response_voice_job(response)
            return response

        repaired = self._try_intent_repair(text, source, snapshot)
        if repaired is not None:
            return repaired

        answer = self.llm.ask(
            text,
            snapshot,
            conversation_context=self.conversation_memory.snapshot(),
        )
        result = VoiceResult(True, False, "llm_question", answer, 0.5)
        response = self._command_response(text, result, source)
        self.conversation_memory.clear()
        self._queue_response_voice_job(response)
        return response

    def handle_transcript(
        self,
        text: str,
        source: str = "discord",
        confidence: float = 1.0,
    ) -> dict:
        if not text.strip():
            result = VoiceResult(False, True, "low_confidence", "", confidence)
            return self._command_response(text, result, source)

        self._prepare_for_driver_request(source)
        snapshot = self._snapshot_for_request(source)
        follow_up = self._resolve_follow_up(text, snapshot)
        if follow_up is not None:
            response = self._command_response(text, follow_up, source)
            self._queue_response_voice_job(response)
            return response

        result = parse_voice_command(text, snapshot, self.config)
        if result.ignored:
            return self._command_response(text, result, source)
        if result.handled:
            self._apply_intent(result)
            response = self._command_response(text, result, source)
            self._remember_response(text, result, response, snapshot)
            self._queue_response_voice_job(response)
            return response

        repaired = self._try_intent_repair(text, source, snapshot)
        if repaired is not None:
            return repaired

        if confidence < self.config.stt.min_confidence:
            result = VoiceResult(False, True, "low_confidence", "", confidence)
            return self._command_response(text, result, source)

        if self.config.voice_mode == "quiet_driver":
            ignored = VoiceResult(False, True, "unknown_quiet_driver", "", result.confidence)
            return self._command_response(text, ignored, source)

        answer = self.llm.ask(
            text,
            snapshot,
            conversation_context=self.conversation_memory.snapshot(),
        )
        result = VoiceResult(True, False, "llm_question", answer, 0.5)
        response = self._command_response(text, result, source)
        self.conversation_memory.clear()
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
                "last": self._last_voice_debug,
                "memory": self.conversation_memory.snapshot(),
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
                "llm": {
                    "configured": self.llm.available(),
                    "model": self.config.llm.model,
                    "disable_thinking": self.config.llm.disable_thinking,
                    "intent_repair_enabled": self.config.llm.intent_repair_enabled,
                    "intent_repair_min_confidence": (
                        self.config.llm.intent_repair_min_confidence
                    ),
                },
                "tts": {
                    "engine": self.config.tts.engine,
                    "radio_effects": self.config.tts.radio_effects,
                },
                "pixel_display": {
                    "enabled": self.config.pixel_display.enabled,
                    "address": self.config.pixel_display.address,
                    "update_hz": self.config.pixel_display.update_hz,
                    "rev_position": self.config.pixel_display.rev_position,
                    "brightness": self.config.pixel_display.brightness,
                    "dim_brightness": self.config.pixel_display.dim_brightness,
                    "orientation": self.config.pixel_display.orientation,
                    "gear_layout": self.config.pixel_display.gear_layout,
                    "width": self.config.pixel_display.width,
                    "height": self.config.pixel_display.height,
                    "size_source": self.config.pixel_display.size_source,
                    "rev_scale": self.config.pixel_display.rev_scale,
                    "rev_start_percent": self.config.pixel_display.rev_start_percent,
                    "shift_mode": self.config.pixel_display.shift_mode,
                    "shift_percent": self.config.pixel_display.shift_percent,
                    "flash_hz": self.config.pixel_display.flash_hz,
                    "fuel_enabled": self.config.pixel_display.fuel_enabled,
                    "color_theme": self.config.pixel_display.color_theme,
                    "gear_color": self.config.pixel_display.gear_color,
                    "rev_low_color": self.config.pixel_display.rev_low_color,
                    "rev_mid_color": self.config.pixel_display.rev_mid_color,
                    "rev_high_color": self.config.pixel_display.rev_high_color,
                    "shift_color": self.config.pixel_display.shift_color,
                    "fuel_safe_color": self.config.pixel_display.fuel_safe_color,
                    "fuel_warn_color": self.config.pixel_display.fuel_warn_color,
                    "fuel_danger_color": self.config.pixel_display.fuel_danger_color,
                    "fuel_critical_color": self.config.pixel_display.fuel_critical_color,
                    "rpm_min": self.config.pixel_display.rpm_min,
                    "rpm_max": self.config.pixel_display.rpm_max,
                },
                "second_display": {
                    "enabled": self.config.second_display.enabled,
                    "address": self.config.second_display.address,
                    "update_hz": self.config.second_display.update_hz,
                    "brightness": self.config.second_display.brightness,
                    "dim_brightness": self.config.second_display.dim_brightness,
                    "orientation": self.config.second_display.orientation,
                    "width": self.config.second_display.width,
                    "height": self.config.second_display.height,
                    "size_source": self.config.second_display.size_source,
                    "alert_hold_seconds": self.config.second_display.alert_hold_seconds,
                    "flash_hold_seconds": self.config.second_display.flash_hold_seconds,
                    "color_theme": self.config.second_display.color_theme,
                    "label_color": self.config.second_display.label_color,
                    "count_color": self.config.second_display.count_color,
                    "active_color": self.config.second_display.active_color,
                    "alert_color": self.config.second_display.alert_color,
                    "dim_color": self.config.second_display.dim_color,
                    "tire_normal_color": self.config.second_display.tire_normal_color,
                    "tire_warm_color": self.config.second_display.tire_warm_color,
                    "tire_hot_color": self.config.second_display.tire_hot_color,
                },
                "wind": {
                    "enabled": self.config.wind.enabled,
                    "ha_base_url": self.config.wind.ha_base_url,
                    "ha_entity_id": self.config.wind.ha_entity_id,
                    "update_hz": self.config.wind.update_hz,
                    "max_speed_kph": self.config.wind.max_speed_kph,
                    "curve_exponent": self.config.wind.curve_exponent,
                    "deadband_kph": self.config.wind.deadband_kph,
                    "off_level": self.config.wind.off_level,
                    "min_active_level": self.config.wind.min_active_level,
                    "max_level": self.config.wind.max_level,
                    "smoothing_seconds": self.config.wind.smoothing_seconds,
                    "hysteresis_levels": self.config.wind.hysteresis_levels,
                    "timeout_seconds": self.config.wind.timeout_seconds,
                },
            },
            "pixel_display": self.pixel_display.status(),
            "second_display": self.second_display.status(),
            "wind": self.wind.status(),
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
        self.config.engineer_muted = muted

    def set_voice_mode(self, mode: str) -> None:
        if mode in {"wake_phrase", "quiet_driver", "quiet_driver_ai"}:
            self.config.voice_mode = mode  # type: ignore[assignment]
        elif mode == "silent":
            self._muted = True

    async def _consume_source(self, source: TelemetrySource) -> None:
        async for frame in source.frames():
            self.update_frame(frame)

    def _append_alerts(self, alerts: list[Alert]) -> None:
        for alert in alerts:
            self.alert_log.append(alert)
            self.second_display.publish_alert(alert)
            if alert.category == "lap":
                self._publish_lap_fuel_page()
            if alert.speak and (not self._muted or alert.priority == "critical"):
                self.voice_jobs.append(
                    VoiceJob(
                        id=f"alert-{alert.id}",
                        kind="tts",
                        text=alert.message,
                        alert_id=alert.id,
                        category=alert.category,
                    )
                )

    def _publish_lap_fuel_page(self) -> None:
        snapshot = self.state.snapshot
        if not snapshot.lap_history:
            return
        last_lap = snapshot.lap_history[-1]
        if snapshot.fuel_level is None and last_lap.fuel_used is None:
            return
        self.second_display.publish_alert(
            Alert(
                id=0,
                timestamp=time.time(),
                category="fuel_lap",  # type: ignore[arg-type]
                priority="info",
                message="Lap fuel usage.",
                speak=False,
            )
        )

    def _sync_second_display_theme(self) -> bool:
        theme = self.config.pixel_display.color_theme
        if self.config.second_display.color_theme == theme:
            return False
        self.config.second_display.color_theme = theme
        return True

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

    def _try_intent_repair(
        self,
        text: str,
        source: str,
        snapshot: RaceSnapshot,
    ) -> dict | None:
        if not self.config.llm.intent_repair_enabled:
            return None

        repair = self.llm.repair_intent(text, snapshot)
        if repair is None:
            return None
        if repair.confidence < self.config.llm.intent_repair_min_confidence:
            return None

        repaired_text = self._repair_text_for_parser(repair)
        result = parse_voice_command(repaired_text, snapshot, self.config)
        if not result.handled or result.intent != repair.intent:
            return None

        result.confidence = repair.confidence
        self._apply_intent(result)
        response = self._command_response(
            text,
            result,
            source,
            repair={
                "intent": repair.intent,
                "command": repair.command,
                "confidence": repair.confidence,
            },
        )
        self._remember_response(text, result, response, snapshot)
        self._queue_response_voice_job(response)
        return response

    def _repair_text_for_parser(self, repair: IntentRepair) -> str:
        if self.config.voice_mode == "wake_phrase":
            return f"{self.config.wake_phrase} {repair.command}"
        return repair.command

    def _prepare_for_driver_request(self, source: str) -> None:
        if source != "discord":
            return
        self.voice_jobs = deque(
            (job for job in self.voice_jobs if job.category != "system"),
            maxlen=self.voice_jobs.maxlen,
        )

    def _snapshot_for_request(self, source: str) -> RaceSnapshot:
        if source == "discord":
            return self.state.stale_snapshot()
        return self.snapshot

    def _resolve_follow_up(self, text: str, snapshot: RaceSnapshot) -> VoiceResult | None:
        follow_up_text = text
        if self.config.voice_mode == "wake_phrase":
            normalized = _normalize_memory_text(text)
            phrase = _normalize_memory_text(self.config.wake_phrase)
            if not normalized.startswith(phrase):
                return None
            follow_up_text = normalized[len(phrase) :].strip(" ,")
        return self.conversation_memory.resolve_follow_up(follow_up_text, snapshot)

    def _remember_response(
        self,
        text: str,
        result: VoiceResult,
        response: dict,
        snapshot: RaceSnapshot,
    ) -> None:
        if result.ignored or not result.handled:
            return
        self.conversation_memory.remember(
            result.intent,
            text,
            str(response.get("response", "")),
            _conversation_fact_data(result.intent, snapshot),
        )

    def _command_response(
        self,
        text: str,
        result: VoiceResult,
        source: str,
        repair: dict | None = None,
    ) -> dict:
        response = {
            "received_at": time.time(),
            "source": source,
            "text": text,
            "handled": result.handled,
            "ignored": result.ignored,
            "intent": result.intent,
            "confidence": result.confidence,
            "response": result.response,
            "speak": bool(result.response and not result.ignored),
            "repair": repair,
        }
        self._last_voice_debug = {
            "received_at": response["received_at"],
            "source": source,
            "text": text,
            "handled": result.handled,
            "ignored": result.ignored,
            "intent": result.intent,
            "confidence": result.confidence,
            "response": result.response,
            "repair": repair,
        }
        return response

    def _queue_response_voice_job(self, response: dict) -> None:
        if response["source"] != "discord" or not response["speak"]:
            return
        jobs: list[VoiceJob] = []
        if self.config.tts.radio_effects:
            jobs.append(
                VoiceJob(
                    id=f"tone-{int(response['received_at'] * 1000)}",
                    kind="tone",
                    text="confirmation",
                )
            )
        jobs.append(
            VoiceJob(
                id=f"response-{int(response['received_at'] * 1000)}",
                kind="tts",
                text=response["response"],
            )
        )
        for job in reversed(jobs):
            self.voice_jobs.appendleft(job)


def _conversation_fact_data(intent: str, snapshot: RaceSnapshot) -> dict[str, object] | None:
    if intent == "best_lap":
        data: dict[str, object] = {}
        if snapshot.best_lap_time_ms is not None and snapshot.best_lap_time_ms >= 0:
            data["lap_time_ms"] = snapshot.best_lap_time_ms
            data["lap_time"] = snapshot.to_dict()["best_lap_time"]
        if snapshot.best_lap_number is not None:
            data["lap_number"] = snapshot.best_lap_number
        return data or None
    if intent == "last_lap":
        data = {}
        if snapshot.last_lap_time_ms is not None and snapshot.last_lap_time_ms >= 0:
            data["lap_time_ms"] = snapshot.last_lap_time_ms
            data["lap_time"] = snapshot.to_dict()["last_lap_time"]
        lap_number = _last_completed_lap_number(snapshot)
        if lap_number is not None:
            data["lap_number"] = lap_number
        return data or None
    if intent == "fuel_burn_rate" and snapshot.fuel_per_lap is not None:
        return {
            "fuel_per_lap": snapshot.fuel_per_lap,
            "fuel_sample_count": snapshot.fuel_sample_count,
        }
    if intent == "last_lap_fuel":
        last_lap = snapshot.lap_history[-1] if snapshot.lap_history else None
        if last_lap is not None and last_lap.fuel_used is not None:
            return {
                "lap_number": last_lap.lap_number,
                "fuel_used": last_lap.fuel_used,
            }
        return None
    if intent == "position" and snapshot.current_position is not None:
        data = {"current_position": snapshot.current_position}
        if snapshot.total_cars is not None:
            data["total_cars"] = snapshot.total_cars
        return data
    if intent in {"laps_left", "time_remaining"}:
        data = {}
        for key, value in [
            ("current_lap", snapshot.current_lap),
            ("laps_left", snapshot.laps_left),
            ("race_time_remaining_ms", snapshot.race_time_remaining_ms),
        ]:
            if value is not None:
                data[key] = value
        return data or None
    if intent == "pit_status":
        return {
            "pit_recommendation": snapshot.pit_recommendation,
            "fuel_margin_laps": snapshot.fuel_margin_laps,
            "fuel_per_lap": snapshot.fuel_per_lap,
            "laps_left": snapshot.laps_left,
        }
    if intent == "fuel_status":
        return {
            "fuel_level": snapshot.fuel_level,
            "fuel_laps_remaining": snapshot.fuel_laps_remaining,
            "fuel_margin_laps": snapshot.fuel_margin_laps,
        }
    return None


def _last_completed_lap_number(snapshot: RaceSnapshot) -> int | None:
    if snapshot.lap_history:
        return snapshot.lap_history[-1].lap_number
    if snapshot.current_lap is not None and snapshot.current_lap > 1:
        return snapshot.current_lap - 1
    return None


def _normalize_memory_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _looks_like_follow_up(text: str) -> bool:
    if not text:
        return False
    return (
        "that" in text
        or text.startswith("and ")
        or text in {"why", "why?", "again", "repeat"}
        or _asks_sample_count(text)
        or _asks_total_cars(text)
        or _asks_faster_than_best(text)
    )


def _asks_which_lap(text: str) -> bool:
    return (
        ("which lap" in text or "what lap" in text or "when was that" in text)
        and "based on" not in text
    )


def _asks_sample_count(text: str) -> bool:
    return "based on" in text and ("lap" in text or "sample" in text)


def _asks_total_cars(text: str) -> bool:
    return "how many cars" in text or "total cars" in text or "cars in the race" in text


def _asks_how_much_that(text: str) -> bool:
    return "how much" in text and "that" in text


def _asks_faster_than_best(text: str) -> bool:
    return (
        "faster" in text
        and ("best" in text or "best lap" in text)
        and ("that" in text or "it" in text)
    )


def _asks_repeat(text: str) -> bool:
    return (
        "what was that again" in text
        or "say that again" in text
        or "repeat" in text
        or text == "again"
    )


def _amount_response(fact: ConversationFact) -> str | None:
    fuel_used = fact.data.get("fuel_used")
    if isinstance(fuel_used, (int, float)):
        return f"That was {fuel_used:.1f} percent fuel."
    fuel_per_lap = fact.data.get("fuel_per_lap")
    if isinstance(fuel_per_lap, (int, float)):
        return f"That was {fuel_per_lap:.1f} percent per lap."
    return None


def _faster_than_best_response(
    fact: ConversationFact,
    snapshot: RaceSnapshot,
) -> str | None:
    lap_time = fact.data.get("lap_time_ms")
    best_lap = snapshot.best_lap_time_ms
    if not isinstance(lap_time, int) or best_lap is None or best_lap < 0:
        return None
    delta = lap_time - best_lap
    if delta <= 0:
        return "Yes. That matched your best lap."
    return f"No. It was {format_spoken_delta(delta)} slower than your best."
