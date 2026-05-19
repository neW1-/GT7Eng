from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .timefmt import format_lap_time

AlertPriority = Literal["critical", "important", "info"]


@dataclass(slots=True)
class WheelValues:
    fl: float | None = None
    fr: float | None = None
    rl: float | None = None
    rr: float | None = None

    @classmethod
    def from_obj(cls, value: Any) -> "WheelValues":
        if value is None:
            return cls()
        return cls(
            fl=_num_or_none(getattr(value, "fl", None)),
            fr=_num_or_none(getattr(value, "fr", None)),
            rl=_num_or_none(getattr(value, "rl", None)),
            rr=_num_or_none(getattr(value, "rr", None)),
        )

    def values(self) -> list[float]:
        return [v for v in [self.fl, self.fr, self.rl, self.rr] if v is not None]

    def max(self) -> float | None:
        vals = self.values()
        return max(vals) if vals else None

    def spread(self) -> float | None:
        vals = self.values()
        return max(vals) - min(vals) if vals else None


@dataclass(slots=True)
class TelemetryFrame:
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    packet_id: int | None = None
    speed_kph: float | None = None
    engine_rpm: float | None = None
    current_gear: int | None = None
    suggested_gear: int | None = None
    throttle: int | None = None
    brake: int | None = None
    clutch_pedal: float | None = None
    current_lap: int | None = None
    total_laps: int | None = None
    last_lap_time_ms: int | None = None
    best_lap_time_ms: int | None = None
    current_position: int | None = None
    total_cars: int | None = None
    fuel_level: float | None = None
    fuel_capacity: float | None = None
    tire_temps: WheelValues = field(default_factory=WheelValues)
    wheel_rps: WheelValues = field(default_factory=WheelValues)
    suspension_height: WheelValues = field(default_factory=WheelValues)
    oil_temp: float | None = None
    water_temp: float | None = None
    oil_pressure: float | None = None
    boost_pressure: float | None = None
    track_id: int | None = None
    track_name: str | None = None
    is_paused: bool = False
    is_loading: bool = False
    cars_on_track: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_gt_telem(cls, telemetry: Any) -> "TelemetryFrame":
        track_id = _int_or_none(getattr(telemetry, "track_id", None))
        track_name = None
        try:
            from gt_telem import TRACK_NAMES  # type: ignore

            track_name = TRACK_NAMES.get(track_id) if track_id is not None else None
        except Exception:
            track_name = None

        current_position = _int_or_none(getattr(telemetry, "race_start_pos", None))
        if current_position is not None and current_position <= 0:
            current_position = None

        return cls(
            source="gt-telem",
            packet_id=_int_or_none(getattr(telemetry, "packet_id", None)),
            speed_kph=_num_or_none(getattr(telemetry, "speed_kph", None)),
            engine_rpm=_num_or_none(getattr(telemetry, "engine_rpm", None)),
            current_gear=_int_or_none(getattr(telemetry, "current_gear", None)),
            suggested_gear=_int_or_none(getattr(telemetry, "suggested_gear", None)),
            throttle=_int_or_none(getattr(telemetry, "throttle", None)),
            brake=_int_or_none(getattr(telemetry, "brake", None)),
            clutch_pedal=_num_or_none(getattr(telemetry, "clutch_pedal", None)),
            current_lap=_int_or_none(getattr(telemetry, "current_lap", None)),
            total_laps=_int_or_none(getattr(telemetry, "total_laps", None)),
            last_lap_time_ms=_int_or_none(getattr(telemetry, "last_lap_time_ms", None)),
            best_lap_time_ms=_int_or_none(getattr(telemetry, "best_lap_time_ms", None)),
            current_position=current_position,
            total_cars=_int_or_none(getattr(telemetry, "total_cars", None)),
            fuel_level=_num_or_none(getattr(telemetry, "fuel_level", None)),
            fuel_capacity=_num_or_none(getattr(telemetry, "fuel_capacity", None)),
            tire_temps=WheelValues.from_obj(getattr(telemetry, "tire_temp", None)),
            wheel_rps=WheelValues.from_obj(getattr(telemetry, "wheel_rps", None)),
            suspension_height=WheelValues.from_obj(
                getattr(telemetry, "suspension_height", None)
            ),
            oil_temp=_num_or_none(getattr(telemetry, "oil_temp", None)),
            water_temp=_num_or_none(getattr(telemetry, "water_temp", None)),
            oil_pressure=_num_or_none(getattr(telemetry, "oil_pressure", None)),
            boost_pressure=_num_or_none(getattr(telemetry, "boost_pressure", None)),
            track_id=track_id,
            track_name=track_name,
            is_paused=bool(getattr(telemetry, "is_paused", False)),
            is_loading=bool(getattr(telemetry, "is_loading", False)),
            cars_on_track=bool(getattr(telemetry, "cars_on_track", False)),
            raw=getattr(telemetry, "as_dict", {}) or {},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelemetryFrame":
        values = dict(data)
        for key in ["tire_temps", "wheel_rps", "suspension_height"]:
            raw = values.get(key)
            if isinstance(raw, dict):
                values[key] = WheelValues(**raw)
            elif raw is None:
                values[key] = WheelValues()
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


@dataclass(slots=True)
class LapRecord:
    lap_number: int
    lap_time_ms: int | None
    fuel_used: float | None
    completed_at: float

    @property
    def lap_time(self) -> str:
        return format_lap_time(self.lap_time_ms)


@dataclass(slots=True)
class RaceSnapshot:
    connected: bool = False
    last_packet_age: float | None = None
    packet_rate_hz: float = 0.0
    current_lap: int | None = None
    total_laps: int | None = None
    laps_left: int | None = None
    current_position: int | None = None
    total_cars: int | None = None
    last_lap_time_ms: int | None = None
    best_lap_time_ms: int | None = None
    average_lap_time_ms: int | None = None
    fuel_level: float | None = None
    fuel_capacity: float | None = None
    fuel_per_lap: float | None = None
    fuel_laps_remaining: float | None = None
    fuel_margin_laps: float | None = None
    pit_recommendation: str = "No fuel data yet."
    speed_kph: float | None = None
    engine_rpm: float | None = None
    current_gear: int | None = None
    tire_temps: WheelValues = field(default_factory=WheelValues)
    oil_temp: float | None = None
    water_temp: float | None = None
    track_id: int | None = None
    track_name: str | None = None
    lap_history: list[LapRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["last_lap_time"] = format_lap_time(self.last_lap_time_ms)
        data["best_lap_time"] = format_lap_time(self.best_lap_time_ms)
        data["average_lap_time"] = format_lap_time(self.average_lap_time_ms)
        return data


@dataclass(slots=True)
class StateUpdate:
    snapshot: RaceSnapshot
    previous: RaceSnapshot | None
    completed_lap: LapRecord | None = None
    position_changed: tuple[int | None, int] | None = None


@dataclass(slots=True)
class Alert:
    id: int
    timestamp: float
    category: str
    priority: AlertPriority
    message: str
    speak: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
