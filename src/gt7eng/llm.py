from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .config import LLMConfig
from .models import RaceSnapshot


ALLOWED_REPAIR_INTENTS = {
    "fuel_status": "how is my fuel",
    "fuel_burn_rate": "what is my fuel burn rate",
    "last_lap_fuel": "how much fuel did I use last lap",
    "pit_status": "do I need to pit",
    "laps_left": "how many laps left",
    "time_remaining": "how much time left",
    "position": "what position am I",
    "last_lap": "what was my last lap",
    "best_lap": "what is my best lap",
    "tires": "how are the tires",
    "status": "give me an update",
    "set_race_duration": "set race duration to 30 minutes",
    "keep_quiet": "keep quiet",
    "more_fuel_updates": "more fuel updates",
    "radio_check": "radio check",
}


@dataclass(slots=True)
class IntentRepair:
    intent: str
    command: str
    confidence: float


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    def available(self) -> bool:
        return bool(self.config.base_url and self.config.model)

    def ask(self, question: str, snapshot: RaceSnapshot) -> str:
        if not self.available():
            return "LLM is not configured. I can still answer core race commands."

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a concise GT7 race engineer. Answer only from the "
                        "provided race_state and request_context. If data is "
                        "unavailable, say it is unavailable. Do not invent opponent "
                        "gaps, nearby car data, weather, tire wear, or strategy facts "
                        "not present."
                        " Fuel level and fuel-per-lap fields are percentages, not liters."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "race_state": snapshot.to_dict(),
                            "request_context": _request_context(),
                            "question": question,
                        },
                        separators=(",", ":"),
                    ),
                },
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": 0.2,
        }
        self._apply_provider_options(payload)
        try:
            return self._request_chat_completion(payload)[:800]
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return f"LLM request failed: {exc}"
        except (KeyError, IndexError, TypeError):
            return "LLM response was not in OpenAI-compatible format."

    def repair_intent(self, transcript: str, snapshot: RaceSnapshot) -> IntentRepair | None:
        if not self.available():
            return None

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Map noisy race-radio STT transcripts to one known GT7 race "
                        "engineer command. Return JSON only. Do not answer the driver. "
                        "If the transcript is not clearly a race command, use intent "
                        "'reject'. Allowed intents: "
                        + ", ".join([*ALLOWED_REPAIR_INTENTS, "reject"])
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "transcript": transcript,
                            "race_context": {
                                "race_mode": snapshot.race_mode,
                                "session_phase": snapshot.session_phase,
                                "current_lap": snapshot.current_lap,
                                "total_laps": snapshot.total_laps,
                            },
                            "output_schema": {
                                "intent": "one allowed intent or reject",
                                "command": "canonical short command for deterministic parser",
                                "confidence": "0.0 to 1.0",
                            },
                            "examples": [
                                {
                                    "transcript": "what spot am i in",
                                    "intent": "position",
                                    "command": "what position am I",
                                    "confidence": 0.86,
                                },
                                {
                                    "transcript": "do we need fuel soon",
                                    "intent": "fuel_status",
                                    "command": "how is my fuel",
                                    "confidence": 0.8,
                                },
                                {
                                    "transcript": "set race timer forty minutes",
                                    "intent": "set_race_duration",
                                    "command": "set race duration to 40 minutes",
                                    "confidence": 0.78,
                                },
                            ],
                        },
                        separators=(",", ":"),
                    ),
                },
            ],
            "max_tokens": min(self.config.max_tokens, 120),
            "temperature": 0,
        }
        self._apply_provider_options(payload)
        try:
            content = self._request_chat_completion(payload)
            data = _extract_json_object(content)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

        intent = str(data.get("intent", "")).strip()
        if intent == "reject" or intent not in ALLOWED_REPAIR_INTENTS:
            return None

        command = str(data.get("command") or ALLOWED_REPAIR_INTENTS[intent]).strip()
        confidence = _clamp_confidence(data.get("confidence"))
        if not command or confidence <= 0:
            return None
        return IntentRepair(intent=intent, command=command, confidence=confidence)

    def _request_chat_completion(self, payload: dict[str, Any]) -> str:
        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=self._headers(),
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()

    def _apply_provider_options(self, payload: dict[str, Any]) -> None:
        if self.config.disable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers


def _extract_json_object(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("No JSON object in LLM response")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM response JSON is not an object")
    return data


def _clamp_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _request_context() -> dict[str, str]:
    now = datetime.now().astimezone()
    return {
        "current_date": now.date().isoformat(),
        "current_time": now.isoformat(timespec="seconds"),
    }
