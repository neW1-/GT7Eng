from __future__ import annotations

import time
from collections import deque

from .config import AppConfig
from .models import (
    DrivingStyleStats,
    LapRecord,
    RaceSnapshot,
    SessionPhase,
    StateUpdate,
    TelemetryFrame,
    WheelValues,
)
from .timefmt import plural


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
        self._saw_racing = False
        self._non_racing_since: float | None = None
        self._tire_radius_baseline: WheelValues | None = None
        self._driving_style = DrivingStyleStats()
        self._last_tcs_active = False
        self._last_asm_active = False
        self._wheelspin_active = False
        self._lockup_active = False
        self._last_incident: str | None = None
        self._timer_mode = "unknown"
        self._timed_race_started_at: float | None = None
        self._timed_race_elapsed_ms = 0
        self._timed_race_last_sample_at: float | None = None

    @property
    def snapshot(self) -> RaceSnapshot:
        return self._last_snapshot or RaceSnapshot()

    def update(self, frame: TelemetryFrame) -> StateUpdate:
        now = time.time()
        self.frames.append(frame)
        self._packet_count += 1
        self._first_frame_time = self._first_frame_time or now
        phase = self._session_phase(frame)
        if self._new_session_started(frame, phase):
            self._reset_race_session()
        self._update_lifecycle(frame, phase)

        previous_snapshot = self._last_snapshot
        completed_lap = self._detect_completed_lap(frame)
        position_changed = self._detect_position_change(frame)
        driving_event = self._update_driving_style(frame)
        incident_detected = self._detect_incident(frame, phase)

        fuel_percent = _fuel_percent(frame.fuel_level)
        if frame.current_lap is not None and fuel_percent is not None:
            self._lap_start_fuel.setdefault(frame.current_lap, fuel_percent)

        snapshot = self._build_snapshot(frame, phase, incident_detected)
        self._last_frame = frame
        self._last_snapshot = snapshot
        return StateUpdate(
            snapshot=snapshot,
            previous=previous_snapshot,
            timestamp=frame.timestamp,
            completed_lap=completed_lap,
            position_changed=position_changed,
            incident_detected=incident_detected,
            driving_event=driving_event,
        )

    def stale_snapshot(self) -> RaceSnapshot:
        snapshot = self.snapshot
        if self._last_frame is None:
            return snapshot
        age = max(0.0, time.time() - self._last_frame.timestamp)
        snapshot.connected = age <= self.config.stale_seconds
        snapshot.last_packet_age = age
        if not snapshot.connected:
            snapshot.session_phase = "stale"
        return snapshot

    def _detect_completed_lap(self, frame: TelemetryFrame) -> LapRecord | None:
        last = self._last_frame
        if last is None or last.current_lap is None or frame.current_lap is None:
            return None
        if frame.current_lap <= last.current_lap or last.current_lap <= 0:
            return None

        start_fuel = self._lap_start_fuel.get(last.current_lap)
        fuel_used = None
        fuel_percent = _fuel_percent(frame.fuel_level)
        if start_fuel is not None and fuel_percent is not None:
            fuel_used = max(0.0, start_fuel - fuel_percent)

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

    def _build_snapshot(
        self,
        frame: TelemetryFrame,
        phase: SessionPhase,
        incident_detected: str | None,
    ) -> RaceSnapshot:
        fuel_samples = self._fuel_samples()
        fuel_per_lap = self._fuel_per_lap(fuel_samples)
        total_laps = _total_laps(frame.total_laps)
        race_mode = self._race_mode(frame, phase)
        laps_left = self._laps_left(frame.current_lap, total_laps)
        race_elapsed_ms = self._race_elapsed_ms(frame, race_mode, phase)
        race_duration_ms = self._race_duration_ms(race_mode)
        race_time_remaining_ms = self._race_time_remaining_ms(
            race_mode, race_elapsed_ms, race_duration_ms
        )
        fuel_percent = _fuel_percent(frame.fuel_level)
        fuel_laps_remaining = None
        fuel_margin = None
        if fuel_per_lap and fuel_percent is not None and fuel_per_lap > 0:
            fuel_laps_remaining = fuel_percent / fuel_per_lap
            fuel_margin = (
                fuel_laps_remaining - laps_left if laps_left is not None else None
            )

        average_lap = self._average_lap_time()
        best_lap = self._best_lap_record()
        best_lap_time = (
            best_lap.lap_time_ms if best_lap is not None else frame.best_lap_time_ms
        )
        packet_rate = self._packet_rate()
        age = max(0.0, time.time() - frame.timestamp)
        tire_wear = self._tire_wear(frame)
        return RaceSnapshot(
            connected=age <= self.config.stale_seconds,
            last_packet_age=age,
            packet_rate_hz=packet_rate,
            session_phase=phase,
            current_lap=frame.current_lap,
            total_laps=total_laps,
            laps_left=laps_left,
            race_mode=race_mode,
            timer_mode=self._timer_mode,  # type: ignore[arg-type]
            race_elapsed_time_ms=race_elapsed_ms,
            race_duration_ms=race_duration_ms,
            race_time_remaining_ms=race_time_remaining_ms,
            current_position=frame.current_position,
            total_cars=frame.total_cars,
            last_lap_time_ms=frame.last_lap_time_ms,
            best_lap_time_ms=best_lap_time,
            best_lap_number=best_lap.lap_number if best_lap is not None else None,
            average_lap_time_ms=average_lap,
            fuel_level=fuel_percent,
            fuel_capacity=100.0 if fuel_percent is not None else None,
            fuel_per_lap=fuel_per_lap,
            fuel_sample_count=len(fuel_samples),
            fuel_laps_remaining=fuel_laps_remaining,
            fuel_margin_laps=fuel_margin,
            pit_recommendation=self._pit_recommendation(
                fuel_laps_remaining,
                fuel_margin,
                fuel_percent,
                len(fuel_samples),
            ),
            speed_kph=frame.speed_kph,
            engine_rpm=frame.engine_rpm,
            current_gear=frame.current_gear,
            tire_temps=frame.tire_temps,
            tire_radius=frame.tire_radius,
            tire_wear_percent=tire_wear,
            oil_temp=frame.oil_temp,
            water_temp=frame.water_temp,
            track_id=frame.track_id,
            track_name=frame.track_name,
            tcs_active=frame.tcs_active,
            asm_active=frame.asm_active,
            hand_brake_active=frame.hand_brake_active,
            rev_limit=frame.rev_limit,
            incident_status=incident_detected or self._last_incident,
            driving_style=DrivingStyleStats(
                tcs_events=self._driving_style.tcs_events,
                asm_events=self._driving_style.asm_events,
                wheelspin_events=self._driving_style.wheelspin_events,
                lockup_events=self._driving_style.lockup_events,
            ),
            lap_history=list(self.lap_history[-20:]),
        )

    def _fuel_samples(self) -> list[float]:
        return [
            lap.fuel_used
            for lap in self.lap_history[-5:]
            if lap.fuel_used is not None and lap.fuel_used > 0
        ]

    def _fuel_per_lap(self, values: list[float]) -> float | None:
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

    def _best_lap_record(self) -> LapRecord | None:
        valid = [
            lap
            for lap in self.lap_history
            if lap.lap_time_ms is not None and lap.lap_time_ms > 0
        ]
        if not valid:
            return None
        return min(valid, key=lambda lap: lap.lap_time_ms or 0)

    def _laps_left(self, current_lap: int | None, total_laps: int | None) -> int | None:
        if current_lap is None or total_laps is None:
            return None
        return max(0, total_laps - current_lap + 1)

    def _race_mode(self, frame: TelemetryFrame, phase: SessionPhase) -> str:
        if _total_laps(frame.total_laps) is not None:
            return "lap"
        if frame.total_laps == 0 and (
            frame.current_lap is not None and frame.current_lap > 0
            or phase in {"racing", "paused", "finished"}
        ):
            return "timed"
        return "unknown"

    def _race_elapsed_ms(
        self, frame: TelemetryFrame, race_mode: str, phase: SessionPhase
    ) -> int | None:
        if race_mode != "timed":
            return None
        if self._timed_race_started_at is None:
            self._timed_race_started_at = frame.timestamp
        if self._timed_race_last_sample_at is not None and phase == "racing":
            elapsed_ms = max(0.0, frame.timestamp - self._timed_race_last_sample_at) * 1000
            self._timed_race_elapsed_ms += int(elapsed_ms)
        self._timed_race_last_sample_at = frame.timestamp
        self._timer_mode = "app_elapsed"
        return self._timed_race_elapsed_ms

    def _race_duration_ms(self, race_mode: str) -> int | None:
        if race_mode != "timed" or self.config.race_duration_minutes is None:
            return None
        return int(self.config.race_duration_minutes * 60_000)

    def _race_time_remaining_ms(
        self,
        race_mode: str,
        race_elapsed_ms: int | None,
        race_duration_ms: int | None,
    ) -> int | None:
        if race_mode != "timed":
            return None
        if race_elapsed_ms is None or race_duration_ms is None:
            return None
        return max(0, race_duration_ms - race_elapsed_ms)

    def _session_phase(self, frame: TelemetryFrame) -> SessionPhase:
        if frame.is_loading:
            return "loading"
        if frame.is_paused:
            return "paused"
        if frame.total_laps and frame.current_lap and frame.current_lap > frame.total_laps:
            return "finished"
        if frame.cars_on_track:
            return "racing"
        if frame.current_lap is not None and frame.current_lap > 0:
            return "racing"
        return "menu"

    def _new_session_started(self, frame: TelemetryFrame, phase: SessionPhase) -> bool:
        last = self._last_frame
        if last is None or phase not in {"racing", "paused"}:
            return False
        if frame.current_lap is None:
            return False

        if (
            last.current_lap is not None
            and last.current_lap > 1
            and frame.current_lap <= 1
        ):
            return True

        last_total = _total_laps(last.total_laps)
        current_total = _total_laps(frame.total_laps)
        if (
            last_total is not None
            and current_total is not None
            and last_total != current_total
            and frame.current_lap <= 1
        ):
            return True

        last_fuel = _fuel_percent(last.fuel_level)
        current_fuel = _fuel_percent(frame.fuel_level)
        return (
            frame.current_lap <= 1
            and last_fuel is not None
            and current_fuel is not None
            and current_fuel - last_fuel >= 20.0
        )

    def _update_lifecycle(self, frame: TelemetryFrame, phase: SessionPhase) -> None:
        if phase == "racing":
            self._saw_racing = True
            self._non_racing_since = None
            return

        if not self._saw_racing or phase == "paused":
            return

        if phase not in {"menu", "loading", "finished"}:
            return

        self._non_racing_since = self._non_racing_since or frame.timestamp
        if frame.timestamp - self._non_racing_since >= 2.5:
            self._reset_race_session()

    def _reset_race_session(self) -> None:
        self.lap_history.clear()
        self._lap_start_fuel.clear()
        self._tire_radius_baseline = None
        self._driving_style = DrivingStyleStats()
        self._last_tcs_active = False
        self._last_asm_active = False
        self._wheelspin_active = False
        self._lockup_active = False
        self._last_incident = None
        self._timer_mode = "unknown"
        self._timed_race_started_at = None
        self._timed_race_elapsed_ms = 0
        self._timed_race_last_sample_at = None
        self._saw_racing = False
        self._non_racing_since = None

    def _tire_wear(self, frame: TelemetryFrame) -> WheelValues:
        radii = frame.tire_radius
        if self._tire_radius_baseline is None:
            values = radii.values()
            if values and all(value > 0 for value in values):
                self._tire_radius_baseline = WheelValues(
                    fl=radii.fl,
                    fr=radii.fr,
                    rl=radii.rl,
                    rr=radii.rr,
                )
            return WheelValues()

        def wear(base: float | None, current: float | None) -> float | None:
            if base is None or current is None or base <= 0:
                return None
            return max(0.0, (base - current) / base * 100.0)

        base = self._tire_radius_baseline
        return WheelValues(
            fl=wear(base.fl, radii.fl),
            fr=wear(base.fr, radii.fr),
            rl=wear(base.rl, radii.rl),
            rr=wear(base.rr, radii.rr),
        )

    def _update_driving_style(self, frame: TelemetryFrame) -> str | None:
        event = None
        if frame.tcs_active and not self._last_tcs_active:
            self._driving_style.tcs_events += 1
            event = "tcs"
        if frame.asm_active and not self._last_asm_active:
            self._driving_style.asm_events += 1
            event = event or "asm"

        wheelspin = self._likely_wheelspin(frame)
        if wheelspin and not self._wheelspin_active:
            self._driving_style.wheelspin_events += 1
            event = event or "wheelspin"

        lockup = self._likely_lockup(frame)
        if lockup and not self._lockup_active:
            self._driving_style.lockup_events += 1
            event = event or "lockup"

        self._last_tcs_active = frame.tcs_active
        self._last_asm_active = frame.asm_active
        self._wheelspin_active = wheelspin
        self._lockup_active = lockup
        return event

    def _likely_wheelspin(self, frame: TelemetryFrame) -> bool:
        if frame.throttle is None or frame.throttle < 60:
            return False
        if frame.speed_kph is None or frame.speed_kph < 25:
            return False
        front = _avg([frame.wheel_rps.fl, frame.wheel_rps.fr])
        rear = _avg([frame.wheel_rps.rl, frame.wheel_rps.rr])
        if front is None or rear is None or front <= 0:
            return False
        return rear / front >= 1.15

    def _likely_lockup(self, frame: TelemetryFrame) -> bool:
        if frame.brake is None or frame.brake < 150:
            return False
        if frame.speed_kph is None or frame.speed_kph < 35:
            return False
        wheels = frame.wheel_rps.values()
        if len(wheels) < 4:
            return False
        avg = sum(wheels) / len(wheels)
        if avg <= 0:
            return False
        return min(wheels) < avg * 0.7

    def _detect_incident(self, frame: TelemetryFrame, phase: SessionPhase) -> str | None:
        last = self._last_frame
        if last is None or phase != "racing":
            return None
        speed = frame.speed_kph or 0.0
        last_speed = last.speed_kph or 0.0
        speed_drop = last_speed - speed
        yaw_rate = abs(frame.angular_velocity.z or 0.0)
        roll_rate = abs(frame.angular_velocity.x or 0.0)

        incident = None
        if last_speed >= 80 and speed_drop >= 55 and speed <= 40:
            incident = "crash"
        elif speed >= 25 and (yaw_rate >= 2.5 or roll_rate >= 2.5):
            incident = "spin"

        if incident:
            self._last_incident = incident
        return incident

    def _pit_recommendation(
        self,
        fuel_laps_remaining: float | None,
        fuel_margin: float | None,
        fuel_level: float | None,
        fuel_sample_count: int,
    ) -> str:
        if fuel_laps_remaining is None:
            return "Need one completed lap for fuel projection."
        if fuel_margin is not None and fuel_margin >= self.config.fuel_safety_laps:
            return "Fuel to the end is safe."
        if fuel_margin is not None and fuel_margin >= 0:
            return "Fuel tight. Save fuel to make the end."
        if (
            fuel_laps_remaining <= 2.0
            and not _urgent_fuel_projection_confident(fuel_level, fuel_sample_count)
        ):
            return "Fuel projection unstable. Need another clean lap."
        if fuel_laps_remaining <= 1.0:
            return "Box this lap."
        if fuel_laps_remaining <= 2.0:
            return "Box within 1 lap."
        if fuel_margin is None:
            return f"Fuel for about {fuel_laps_remaining:.1f} laps. Race length unavailable."
        if fuel_margin < 0:
            safe_laps = max(1, int(fuel_laps_remaining - self.config.fuel_safety_laps))
            return f"Pit required. Box within {plural(safe_laps, 'lap')}."
        return "Fuel to the end is safe."

    def _packet_rate(self) -> float:
        if not self._first_frame_time:
            return 0.0
        elapsed = max(0.001, time.time() - self._first_frame_time)
        return self._packet_count / elapsed


def _avg(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _fuel_percent(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(100.0, value))


def _total_laps(value: int | None) -> int | None:
    if value is None or value <= 0:
        return None
    return value


def _urgent_fuel_projection_confident(
    fuel_level: float | None,
    fuel_sample_count: int,
) -> bool:
    if fuel_sample_count >= 2:
        return True
    if fuel_level is None:
        return False
    return fuel_level <= 25.0
