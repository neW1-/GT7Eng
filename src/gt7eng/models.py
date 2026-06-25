from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .timefmt import format_duration, format_lap_time

AlertPriority = Literal["critical", "important", "info"]
SessionPhase = Literal["unknown", "menu", "loading", "paused", "racing", "finished", "stale"]
RaceMode = Literal["unknown", "lap", "timed"]
TimerMode = Literal["unknown", "app_elapsed"]


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
class VectorValues:
    x: float | None = None
    y: float | None = None
    z: float | None = None

    @classmethod
    def from_obj(cls, value: Any) -> "VectorValues":
        if value is None:
            return cls()
        if isinstance(value, (list, tuple)):
            values = list(value) + [None, None, None]
            return cls(
                x=_num_or_none(values[0]),
                y=_num_or_none(values[1]),
                z=_num_or_none(values[2]),
            )
        return cls(
            x=_num_or_none(getattr(value, "x", None)),
            y=_num_or_none(getattr(value, "y", None)),
            z=_num_or_none(getattr(value, "z", None)),
        )


@dataclass(slots=True)
class DrivingStyleStats:
    tcs_events: int = 0
    asm_events: int = 0
    wheelspin_events: int = 0
    lockup_events: int = 0


@dataclass(slots=True)
class TelemetryFrame:
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    packet_id: int | None = None
    speed_kph: float | None = None
    engine_rpm: float | None = None
    min_alert_rpm: float | None = None
    max_alert_rpm: float | None = None
    current_gear: int | None = None
    suggested_gear: int | None = None
    throttle: int | None = None
    brake: int | None = None
    clutch_pedal: float | None = None
    position: VectorValues = field(default_factory=VectorValues)
    velocity: VectorValues = field(default_factory=VectorValues)
    rotation: VectorValues = field(default_factory=VectorValues)
    angular_velocity: VectorValues = field(default_factory=VectorValues)
    current_lap: int | None = None
    total_laps: int | None = None
    time_of_day_ms: int | None = None
    last_lap_time_ms: int | None = None
    best_lap_time_ms: int | None = None
    current_position: int | None = None
    total_cars: int | None = None
    fuel_level: float | None = None
    fuel_capacity: float | None = None
    tire_temps: WheelValues = field(default_factory=WheelValues)
    tire_radius: WheelValues = field(default_factory=WheelValues)
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
    in_gear: bool = False
    tcs_active: bool = False
    asm_active: bool = False
    hand_brake_active: bool = False
    rev_limit: bool = False
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

        raw = getattr(telemetry, "as_dict", {}) or {}
        if callable(raw):
            raw = raw()

        return cls(
            source="gt-telem",
            packet_id=_int_or_none(getattr(telemetry, "packet_id", None)),
            speed_kph=_num_or_none(getattr(telemetry, "speed_kph", None)),
            engine_rpm=_num_or_none(getattr(telemetry, "engine_rpm", None)),
            min_alert_rpm=_num_or_none(getattr(telemetry, "min_alert_rpm", None)),
            max_alert_rpm=_num_or_none(getattr(telemetry, "max_alert_rpm", None)),
            current_gear=_int_or_none(getattr(telemetry, "current_gear", None)),
            suggested_gear=_int_or_none(getattr(telemetry, "suggested_gear", None)),
            throttle=_int_or_none(getattr(telemetry, "throttle", None)),
            brake=_int_or_none(getattr(telemetry, "brake", None)),
            clutch_pedal=_num_or_none(getattr(telemetry, "clutch_pedal", None)),
            position=VectorValues.from_obj(getattr(telemetry, "position", None)),
            velocity=VectorValues.from_obj(getattr(telemetry, "velocity", None)),
            rotation=VectorValues.from_obj(getattr(telemetry, "rotation", None)),
            angular_velocity=VectorValues.from_obj(
                getattr(telemetry, "angular_velocity", None)
            ),
            current_lap=_int_or_none(getattr(telemetry, "current_lap", None)),
            total_laps=_int_or_none(getattr(telemetry, "total_laps", None)),
            time_of_day_ms=_int_or_none(getattr(telemetry, "time_of_day_ms", None)),
            last_lap_time_ms=_int_or_none(getattr(telemetry, "last_lap_time_ms", None)),
            best_lap_time_ms=_int_or_none(getattr(telemetry, "best_lap_time_ms", None)),
            current_position=current_position,
            total_cars=_int_or_none(getattr(telemetry, "total_cars", None)),
            fuel_level=_num_or_none(getattr(telemetry, "fuel_level", None)),
            fuel_capacity=_num_or_none(getattr(telemetry, "fuel_capacity", None)),
            tire_temps=WheelValues.from_obj(getattr(telemetry, "tire_temp", None)),
            tire_radius=WheelValues.from_obj(getattr(telemetry, "tire_radius", None)),
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
            in_gear=bool(getattr(telemetry, "in_gear", False)),
            tcs_active=bool(getattr(telemetry, "tcs_active", False)),
            asm_active=bool(getattr(telemetry, "asm_active", False)),
            hand_brake_active=bool(getattr(telemetry, "hand_brake_active", False)),
            rev_limit=bool(getattr(telemetry, "rev_limit", False)),
            raw=_json_safe(raw) if isinstance(raw, dict) else {},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelemetryFrame":
        values = dict(data)
        for key in ["tire_temps", "tire_radius", "wheel_rps", "suspension_height"]:
            raw = values.get(key)
            if isinstance(raw, dict):
                values[key] = WheelValues(**raw)
            elif raw is None:
                values[key] = WheelValues()
        for key in ["position", "velocity", "rotation", "angular_velocity"]:
            raw = values.get(key)
            if isinstance(raw, dict):
                values[key] = VectorValues(**raw)
            elif raw is None:
                values[key] = VectorValues()
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
    driving_style: DrivingStyleStats = field(default_factory=DrivingStyleStats)

    @property
    def lap_time(self) -> str:
        return format_lap_time(self.lap_time_ms)


@dataclass(slots=True)
class RaceSnapshot:
    connected: bool = False
    last_packet_age: float | None = None
    packet_rate_hz: float = 0.0
    session_phase: SessionPhase = "unknown"
    current_lap: int | None = None
    total_laps: int | None = None
    laps_left: int | None = None
    race_mode: RaceMode = "unknown"
    timer_mode: TimerMode = "unknown"
    race_elapsed_time_ms: int | None = None
    race_duration_ms: int | None = None
    race_time_remaining_ms: int | None = None
    current_position: int | None = None
    total_cars: int | None = None
    last_lap_time_ms: int | None = None
    best_lap_time_ms: int | None = None
    best_lap_number: int | None = None
    average_lap_time_ms: int | None = None
    fuel_level: float | None = None
    fuel_capacity: float | None = None
    fuel_per_lap: float | None = None
    fuel_sample_count: int = 0
    fuel_unit: str = "percent"
    fuel_laps_remaining: float | None = None
    fuel_margin_laps: float | None = None
    pit_recommendation: str = "No fuel data yet."
    speed_kph: float | None = None
    engine_rpm: float | None = None
    min_alert_rpm: float | None = None
    max_alert_rpm: float | None = None
    current_gear: int | None = None
    suggested_gear: int | None = None
    tire_temps: WheelValues = field(default_factory=WheelValues)
    tire_radius: WheelValues = field(default_factory=WheelValues)
    tire_wear_percent: WheelValues = field(default_factory=WheelValues)
    oil_temp: float | None = None
    water_temp: float | None = None
    track_id: int | None = None
    track_name: str | None = None
    tcs_active: bool = False
    asm_active: bool = False
    hand_brake_active: bool = False
    rev_limit: bool = False
    wheelspin_active: bool = False
    lockup_active: bool = False
    incident_status: str | None = None
    driving_style: DrivingStyleStats = field(default_factory=DrivingStyleStats)
    lap_history: list[LapRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["last_lap_time"] = format_lap_time(self.last_lap_time_ms)
        data["best_lap_time"] = format_lap_time(self.best_lap_time_ms)
        data["average_lap_time"] = format_lap_time(self.average_lap_time_ms)
        data["race_elapsed_time"] = format_duration(self.race_elapsed_time_ms)
        data["race_duration"] = format_duration(self.race_duration_ms)
        data["race_time_remaining"] = format_duration(self.race_time_remaining_ms)
        data["fuel_level_percent"] = self.fuel_level
        data["fuel_per_lap_percent"] = self.fuel_per_lap
        return data


@dataclass(slots=True)
class StateUpdate:
    snapshot: RaceSnapshot
    previous: RaceSnapshot | None
    timestamp: float = 0.0
    completed_lap: LapRecord | None = None
    position_changed: tuple[int | None, int] | None = None
    incident_detected: str | None = None
    driving_event: str | None = None


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


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple) and hasattr(value, "_fields"):
        return [_json_safe(item) for item in value]
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
