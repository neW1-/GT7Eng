from __future__ import annotations

import time
from collections import deque

from .config import AppConfig
from .models import LapRecord, RaceSnapshot, StateUpdate, TelemetryFrame


class RaceState:
    def __init__(self, config: AppConfig):
        self.config = config
        self.frames: deque[TelemetryFrame] = deque(maxlen=config.max_frame_buffer)
        self.lap_history: list[LapRecord] = []
        self._lap_start_fuel: dict[int, float] = {}
        self._last_snapshot: RaceSnapshot | None = None
        self._last_frame: TelemetryFrame | None = None
        self._first_frame_time: float | None = None
        self._packet_count = 0

    @property
    def snapshot(self) -> RaceSnapshot:
        return self._last_snapshot or RaceSnapshot()

    def update(self, frame: TelemetryFrame) -> StateUpdate:
        now = time.time()
        self.frames.append(frame)
        self._packet_count += 1
        self._first_frame_time = self._first_frame_time or now

        previous_snapshot = self._last_snapshot
        completed_lap = self._detect_completed_lap(frame)
        position_changed = self._detect_position_change(frame)

        if frame.current_lap is not None and frame.fuel_level is not None:
            self._lap_start_fuel.setdefault(frame.current_lap, frame.fuel_level)

        snapshot = self._build_snapshot(frame)
        self._last_frame = frame
        self._last_snapshot = snapshot
        return StateUpdate(
            snapshot=snapshot,
            previous=previous_snapshot,
            completed_lap=completed_lap,
            position_changed=position_changed,
        )

    def stale_snapshot(self) -> RaceSnapshot:
        snapshot = self.snapshot
        if self._last_frame is None:
            return snapshot
        age = max(0.0, time.time() - self._last_frame.timestamp)
        snapshot.connected = age <= self.config.stale_seconds
        snapshot.last_packet_age = age
        return snapshot

    def _detect_completed_lap(self, frame: TelemetryFrame) -> LapRecord | None:
        last = self._last_frame
        if last is None or last.current_lap is None or frame.current_lap is None:
            return None
        if frame.current_lap <= last.current_lap or last.current_lap <= 0:
            return None

        start_fuel = self._lap_start_fuel.get(last.current_lap)
        fuel_used = None
        if start_fuel is not None and frame.fuel_level is not None:
            fuel_used = max(0.0, start_fuel - frame.fuel_level)

        lap = LapRecord(
            lap_number=last.current_lap,
            lap_time_ms=frame.last_lap_time_ms,
            fuel_used=fuel_used,
            completed_at=frame.timestamp,
        )
        self.lap_history.append(lap)
        return lap

    def _detect_position_change(self, frame: TelemetryFrame) -> tuple[int | None, int] | None:
        last_position = (
            self._last_frame.current_position if self._last_frame is not None else None
        )
        if frame.current_position is None:
            return None
        if last_position is None or last_position == frame.current_position:
            return None
        return last_position, frame.current_position

    def _build_snapshot(self, frame: TelemetryFrame) -> RaceSnapshot:
        fuel_per_lap = self._fuel_per_lap()
        laps_left = self._laps_left(frame.current_lap, frame.total_laps)
        fuel_laps_remaining = None
        fuel_margin = None
        if fuel_per_lap and frame.fuel_level is not None and fuel_per_lap > 0:
            fuel_laps_remaining = frame.fuel_level / fuel_per_lap
            fuel_margin = (
                fuel_laps_remaining - laps_left if laps_left is not None else None
            )

        average_lap = self._average_lap_time()
        packet_rate = self._packet_rate()
        age = max(0.0, time.time() - frame.timestamp)
        return RaceSnapshot(
            connected=age <= self.config.stale_seconds,
            last_packet_age=age,
            packet_rate_hz=packet_rate,
            current_lap=frame.current_lap,
            total_laps=frame.total_laps,
            laps_left=laps_left,
            current_position=frame.current_position,
            total_cars=frame.total_cars,
            last_lap_time_ms=frame.last_lap_time_ms,
            best_lap_time_ms=frame.best_lap_time_ms,
            average_lap_time_ms=average_lap,
            fuel_level=frame.fuel_level,
            fuel_capacity=frame.fuel_capacity,
            fuel_per_lap=fuel_per_lap,
            fuel_laps_remaining=fuel_laps_remaining,
            fuel_margin_laps=fuel_margin,
            pit_recommendation=self._pit_recommendation(fuel_margin),
            speed_kph=frame.speed_kph,
            engine_rpm=frame.engine_rpm,
            current_gear=frame.current_gear,
            tire_temps=frame.tire_temps,
            oil_temp=frame.oil_temp,
            water_temp=frame.water_temp,
            track_id=frame.track_id,
            track_name=frame.track_name,
            lap_history=list(self.lap_history[-20:]),
        )

    def _fuel_per_lap(self) -> float | None:
        values = [
            lap.fuel_used
            for lap in self.lap_history[-5:]
            if lap.fuel_used is not None and lap.fuel_used > 0
        ]
        if not values:
            return None
        return sum(values) / len(values)

    def _average_lap_time(self) -> int | None:
        values = [
            lap.lap_time_ms
            for lap in self.lap_history[-10:]
            if lap.lap_time_ms is not None and lap.lap_time_ms > 0
        ]
        if not values:
            return None
        return int(sum(values) / len(values))

    def _laps_left(self, current_lap: int | None, total_laps: int | None) -> int | None:
        if current_lap is None or total_laps is None or total_laps <= 0:
            return None
        return max(0, total_laps - current_lap + 1)

    def _pit_recommendation(self, fuel_margin: float | None) -> str:
        if fuel_margin is None:
            return "Need one completed lap for fuel projection."
        if fuel_margin < 0:
            return "Fuel short. Box this lap."
        if fuel_margin < self.config.fuel_safety_laps:
            return "Fuel tight. Prepare to box or save fuel."
        return "Fuel to the end is safe."

    def _packet_rate(self) -> float:
        if not self._first_frame_time:
            return 0.0
        elapsed = max(0.001, time.time() - self._first_frame_time)
        return self._packet_count / elapsed
