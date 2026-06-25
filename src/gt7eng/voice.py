from __future__ import annotations

import re
from dataclasses import dataclass

from .config import AppConfig
from .models import RaceSnapshot
from .timefmt import format_duration_words, format_lap_time


@dataclass(slots=True)
class VoiceResult:
    handled: bool
    ignored: bool
    intent: str
    response: str
    confidence: float = 1.0
    race_duration_minutes: float | None = None


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

    if _asks_last_lap_fuel(normalized):
        return VoiceResult(True, False, "last_lap_fuel", _last_lap_fuel(snapshot))
    if _asks_fuel_burn_rate(normalized):
        return VoiceResult(True, False, "fuel_burn_rate", _fuel_burn_rate(snapshot))
    if _matches(normalized, "fuel", "gas"):
        return VoiceResult(True, False, "fuel_status", _fuel_status(snapshot))
    race_duration = _parse_race_duration_minutes(normalized)
    if race_duration is not None:
        return VoiceResult(
            True,
            False,
            "set_race_duration",
            f"Race duration set to {format_duration_words(int(race_duration * 60_000))}.",
            1.0,
            race_duration,
        )
    if _asks_pit_age(normalized):
        return VoiceResult(True, False, "pit_age", _pit_age_status(snapshot))
    if _matches(normalized, "pit", "box", "stop"):
        return VoiceResult(True, False, "pit_status", snapshot.pit_recommendation)
    if (
        "laps left" in normalized
        or "how many laps" in normalized
        or normalized in {"lap", "laps"}
    ):
        return VoiceResult(True, False, "laps_left", _lap_status(snapshot))
    if "time left" in normalized or "time remaining" in normalized or "how much time" in normalized:
        return VoiceResult(True, False, "time_remaining", _time_remaining(snapshot))
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
    parts = [f"Fuel is {snapshot.fuel_level:.1f} percent."]
    if snapshot.fuel_laps_remaining is not None:
        parts.append(f"That is {snapshot.fuel_laps_remaining:.1f} laps.")
    if snapshot.fuel_margin_laps is not None:
        parts.append(f"Margin is {snapshot.fuel_margin_laps:.1f} laps.")
    return " ".join(parts)


def _fuel_burn_rate(snapshot: RaceSnapshot) -> str:
    if snapshot.fuel_per_lap is None:
        return "Need one completed lap for fuel burn."
    return f"Fuel burn is {snapshot.fuel_per_lap:.1f} percent per lap."


def _last_lap_fuel(snapshot: RaceSnapshot) -> str:
    last_lap = snapshot.lap_history[-1] if snapshot.lap_history else None
    if last_lap is None or last_lap.fuel_used is None:
        return "Need one completed lap for fuel burn."
    return f"Last lap used {last_lap.fuel_used:.1f} percent fuel."


def _pit_age_status(snapshot: RaceSnapshot) -> str:
    if snapshot.laps_since_pit_service is None:
        return "No pit service detected yet."
    if snapshot.laps_since_pit_service == 0:
        return "Pit service was this lap."
    suffix = "" if snapshot.laps_since_pit_service == 1 else "s"
    return f"Pit service was {snapshot.laps_since_pit_service} lap{suffix} ago."


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


def _lap_status(snapshot: RaceSnapshot) -> str:
    if snapshot.race_mode == "timed":
        lap = (
            f"Lap {snapshot.current_lap}"
            if snapshot.current_lap is not None and snapshot.current_lap > 0
            else "Timed race"
        )
        if snapshot.race_time_remaining_ms is not None:
            return f"{lap}, {format_duration_words(snapshot.race_time_remaining_ms)} remaining."
        return f"{lap}. Time remaining is unavailable; set the race duration."
    if snapshot.laps_left is not None:
        return f"{snapshot.laps_left} laps left."
    if snapshot.current_lap is not None:
        return f"Lap {snapshot.current_lap}. Laps left is unavailable."
    return "Laps left is unavailable."


def _time_remaining(snapshot: RaceSnapshot) -> str:
    if snapshot.race_time_remaining_ms is None:
        return "Time remaining is unavailable."
    return f"{format_duration_words(snapshot.race_time_remaining_ms)} remaining."


def _status(snapshot: RaceSnapshot) -> str:
    parts: list[str] = []
    if snapshot.current_position is not None:
        parts.append(f"P{snapshot.current_position}")
    if (
        snapshot.current_lap is not None
        and snapshot.current_lap > 0
        and snapshot.total_laps is not None
    ):
        parts.append(f"lap {snapshot.current_lap} of {snapshot.total_laps}")
    elif snapshot.current_lap is not None and snapshot.current_lap > 0:
        parts.append(f"lap {snapshot.current_lap}")
    if snapshot.laps_left is not None:
        parts.append(f"{snapshot.laps_left} laps left")
    elif snapshot.race_time_remaining_ms is not None:
        parts.append(f"{format_duration_words(snapshot.race_time_remaining_ms)} remaining")
    if snapshot.fuel_laps_remaining is not None:
        parts.append(f"fuel {snapshot.fuel_laps_remaining:.1f} laps")
    if not parts:
        return "No race state yet."
    return ", ".join(parts) + "."


def _matches(text: str, *words: str) -> bool:
    return any(word in text for word in words)


def _asks_fuel_burn_rate(text: str) -> bool:
    if not _matches(text, "fuel", "gas"):
        return False
    return any(
        phrase in text
        for phrase in (
            "burn rate",
            "fuel burn",
            "consumption",
            "per lap",
            "use rate",
            "usage rate",
        )
    )


def _asks_last_lap_fuel(text: str) -> bool:
    if not _matches(text, "fuel", "gas") or "last lap" not in text:
        return False
    return any(
        word in text
        for word in (
            "use",
            "used",
            "burn",
            "burned",
            "consumption",
            "spend",
            "spent",
        )
    )


def _asks_pit_age(text: str) -> bool:
    if not _matches(text, "pit", "box", "stop"):
        return False
    return any(
        phrase in text
        for phrase in (
            "how long ago",
            "when did",
            "when was",
            "last pit",
            "last stop",
            "last box",
            "laps since",
            "since i pit",
            "since i pitted",
            "since my pit",
            "since the pit",
        )
    )


def _parse_race_duration_minutes(text: str) -> float | None:
    if "race" not in text and "duration" not in text and "timer" not in text:
        return None
    match = re.search(
        r"(?:set|use|race|duration|timer|time|length).{0,30}?"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>hour|hours|hr|hrs|minute|minutes|min|mins)",
        text,
    )
    if not match:
        return None
    value = float(match.group("value"))
    unit = match.group("unit")
    if unit.startswith("hour") or unit.startswith("hr"):
        return value * 60.0
    return value


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())
