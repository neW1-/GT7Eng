from __future__ import annotations

import re
from dataclasses import dataclass

from .config import AppConfig
from .models import RaceSnapshot
from .timefmt import format_lap_time


@dataclass(slots=True)
class VoiceResult:
    handled: bool
    ignored: bool
    intent: str
    response: str
    confidence: float = 1.0


def parse_voice_command(text: str, snapshot: RaceSnapshot, config: AppConfig) -> VoiceResult:
    original = text.strip()
    normalized = _normalize(original)
    if not normalized:
        return VoiceResult(False, True, "empty", "", 0.0)

    if config.voice_mode == "wake_phrase":
        phrase = _normalize(config.wake_phrase)
        if not normalized.startswith(phrase):
            return VoiceResult(False, True, "missing_wake_phrase", "", 0.0)
        normalized = normalized[len(phrase) :].strip(" ,")
        if not normalized:
            return VoiceResult(True, False, "radio_check", "Engineer online.", 1.0)

    if _matches(normalized, "fuel", "gas"):
        return VoiceResult(True, False, "fuel_status", _fuel_status(snapshot))
    if _matches(normalized, "pit", "box", "stop"):
        return VoiceResult(True, False, "pit_status", snapshot.pit_recommendation)
    if "laps left" in normalized or "how many laps" in normalized:
        laps = snapshot.laps_left
        response = "Laps left is unavailable." if laps is None else f"{laps} laps left."
        return VoiceResult(True, False, "laps_left", response)
    if "last lap" in normalized:
        return VoiceResult(
            True,
            False,
            "last_lap",
            f"Last lap was {format_lap_time(snapshot.last_lap_time_ms)}.",
        )
    if "best lap" in normalized or normalized == "best":
        return VoiceResult(
            True,
            False,
            "best_lap",
            f"Best lap is {format_lap_time(snapshot.best_lap_time_ms)}.",
        )
    if "position" in normalized or re.search(r"\bp\s*\d?\b", normalized):
        if snapshot.current_position is None:
            response = "Position is unavailable."
        else:
            response = f"You are P{snapshot.current_position}."
        return VoiceResult(True, False, "position", response)
    if "tire" in normalized or "tyre" in normalized:
        return VoiceResult(True, False, "tires", _tire_status(snapshot))
    if "update" in normalized or "status" in normalized:
        return VoiceResult(True, False, "status", _status(snapshot))
    if "keep quiet" in normalized or "shut up" in normalized:
        return VoiceResult(True, False, "keep_quiet", "Copy. Keeping quiet.", 1.0)
    if "more fuel" in normalized:
        return VoiceResult(True, False, "more_fuel_updates", "Copy. More fuel updates.", 1.0)
    if "radio check" in normalized:
        return VoiceResult(True, False, "radio_check", "Radio check. Engineer online.", 1.0)

    return VoiceResult(False, False, "unknown", "", 0.25)


def _fuel_status(snapshot: RaceSnapshot) -> str:
    if snapshot.fuel_level is None:
        return "Fuel data is unavailable."
    parts = [f"Fuel is {snapshot.fuel_level:.1f} liters."]
    if snapshot.fuel_laps_remaining is not None:
        parts.append(f"That is {snapshot.fuel_laps_remaining:.1f} laps.")
    if snapshot.fuel_margin_laps is not None:
        parts.append(f"Margin is {snapshot.fuel_margin_laps:.1f} laps.")
    return " ".join(parts)


def _tire_status(snapshot: RaceSnapshot) -> str:
    hottest = snapshot.tire_temps.max()
    spread = snapshot.tire_temps.spread()
    if hottest is None:
        return "Tire data is unavailable."
    if hottest >= 115:
        return f"Tires are hot. Hottest is {hottest:.0f} degrees."
    if spread is not None and spread >= 25:
        return f"Tire spread is high at {spread:.0f} degrees."
    return f"Tires look okay. Hottest is {hottest:.0f} degrees."


def _status(snapshot: RaceSnapshot) -> str:
    parts: list[str] = []
    if snapshot.current_position is not None:
        parts.append(f"P{snapshot.current_position}")
    if snapshot.current_lap is not None and snapshot.total_laps is not None:
        parts.append(f"lap {snapshot.current_lap} of {snapshot.total_laps}")
    if snapshot.laps_left is not None:
        parts.append(f"{snapshot.laps_left} laps left")
    if snapshot.fuel_laps_remaining is not None:
        parts.append(f"fuel {snapshot.fuel_laps_remaining:.1f} laps")
    if not parts:
        return "No race state yet."
    return ", ".join(parts) + "."


def _matches(text: str, *words: str) -> bool:
    return any(word in text for word in words)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())
