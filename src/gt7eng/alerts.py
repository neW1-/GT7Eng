from __future__ import annotations

import time

from .config import AppConfig
from .models import Alert, RaceSnapshot, StateUpdate
from .timefmt import format_delta, format_duration_words, format_lap_time, plural


class AlertManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self._next_id = 1
        self._last_by_key: dict[str, float] = {}
        self._system_connected: bool | None = None
        self._fuel_thresholds_announced: set[int] = set()
        self._tire_wear_stage = 0
        self._pending_position_start: int | None = None
        self._pending_position_latest: int | None = None
        self._pending_position_changed_at: float | None = None

    def from_update(self, update: StateUpdate) -> list[Alert]:
        if update.snapshot.session_phase in {"menu", "loading", "paused", "finished", "stale"}:
            return []
        alerts: list[Alert] = []
        alerts.extend(self._position_alerts(update))
        alerts.extend(self._lap_alerts(update))
        alerts.extend(self._fuel_alerts(update.snapshot, completed=update.completed_lap is not None))
        alerts.extend(self._tire_alerts(update.snapshot))
        alerts.extend(self._incident_alerts(update))
        alerts.extend(self._driving_alerts(update))
        alerts.extend(self._car_alerts(update.snapshot))
        return alerts

    def connection_alerts(self, snapshot: RaceSnapshot) -> list[Alert]:
        if self._system_connected is None:
            self._system_connected = snapshot.connected
            return []
        if snapshot.connected == self._system_connected:
            return []
        self._system_connected = snapshot.connected
        if snapshot.connected:
            return [self._alert("system", "important", "Telemetry connected.")]
        return [
            self._alert(
                "system",
                "critical",
                "Telemetry stale. Check GT7, PS5 network, and UDP firewall.",
            )
        ]

    def _position_alerts(self, update: StateUpdate) -> list[Alert]:
        if not self.config.category_enabled("position", "balanced"):
            self._clear_pending_position()
            return []
        if update.position_changed is not None:
            old, new = update.position_changed
            self._record_position_change(old, new, update.timestamp)
        return self._flush_position_alerts(update.timestamp)

    def _record_position_change(self, old: int | None, new: int, changed_at: float) -> None:
        if self._pending_position_start is None:
            self._pending_position_start = old
        self._pending_position_latest = new
        self._pending_position_changed_at = changed_at

    def _flush_position_alerts(self, now: float) -> list[Alert]:
        if (
            self._pending_position_latest is None
            or self._pending_position_changed_at is None
            or now - self._pending_position_changed_at < self.config.position_coalesce_seconds
        ):
            return []

        old = self._pending_position_start
        new = self._pending_position_latest
        self._clear_pending_position()
        if old == new:
            return []
        if old is None:
            message = f"P{new}."
        elif new < old:
            gained = old - new
            message = f"Gained {plural(gained, 'place')}, now P{new}."
        else:
            lost = new - old
            message = f"Lost {plural(lost, 'place')}, now P{new}."
        return [self._alert("position", "important", message)]

    def _clear_pending_position(self) -> None:
        self._pending_position_start = None
        self._pending_position_latest = None
        self._pending_position_changed_at = None

    def _lap_alerts(self, update: StateUpdate) -> list[Alert]:
        if update.completed_lap is None:
            return []
        if not self.config.category_enabled("lap", "balanced"):
            return []

        snap = update.snapshot
        lap = update.completed_lap
        delta = None
        if snap.best_lap_time_ms is not None and lap.lap_time_ms is not None:
            delta = lap.lap_time_ms - snap.best_lap_time_ms
        parts = [f"Lap {lap.lap_number}: {format_lap_time(lap.lap_time_ms)}."]
        if delta is not None:
            parts.append(f"{format_delta(delta)} to best.")
        if (
            snap.average_lap_time_ms is not None
            and lap.lap_time_ms is not None
            and self.config.category_enabled("lap", "detailed")
        ):
            avg_delta = lap.lap_time_ms - snap.average_lap_time_ms
            parts.append(f"{format_delta(avg_delta)} to recent average.")
        if snap.laps_left == 1:
            parts.append("Final lap.")
        elif snap.laps_left == 2:
            parts.append("Two laps left.")
        elif snap.laps_left is not None:
            parts.append(f"{plural(snap.laps_left, 'lap')} left.")
        elif snap.race_mode == "timed" and snap.race_time_remaining_ms is not None:
            parts.append(f"{format_duration_words(snap.race_time_remaining_ms)} remaining.")
        return [self._alert("lap", "info", " ".join(parts))]

    def _fuel_alerts(self, snapshot: RaceSnapshot, completed: bool) -> list[Alert]:
        if not self.config.category_enabled("fuel", "critical"):
            return []
        margin = snapshot.fuel_margin_laps
        alerts: list[Alert] = []
        if margin is not None:
            if margin < 0 and self._allowed("fuel_critical", 20):
                alerts.append(self._alert("fuel", "critical", "Fuel critical. Box this lap."))
            elif margin < self.config.fuel_safety_laps and self._allowed("fuel_tight", 45):
                alerts.append(
                    self._alert("fuel", "important", "Fuel is tight. Save fuel or box soon.")
                )
            elif (
                completed
                and self.config.category_enabled("fuel", "detailed")
                and snapshot.fuel_laps_remaining is not None
            ):
                alerts.append(
                    self._alert(
                        "fuel",
                        "info",
                        f"Fuel for {snapshot.fuel_laps_remaining:.1f} laps, margin {margin:.1f}.",
                    )
                )
        alerts.extend(self._fuel_threshold_alerts(snapshot))
        return alerts

    def _fuel_threshold_alerts(self, snapshot: RaceSnapshot) -> list[Alert]:
        if not self.config.category_enabled("fuel", "balanced"):
            return []
        if snapshot.fuel_level is None:
            return []
        percentage = max(0.0, min(100.0, snapshot.fuel_level))
        for threshold in [50, 20, 10]:
            if percentage > threshold + 5:
                self._fuel_thresholds_announced.discard(threshold)
            if percentage <= threshold and threshold not in self._fuel_thresholds_announced:
                self._fuel_thresholds_announced.add(threshold)
                priority = "important" if threshold > 10 else "critical"
                return [self._alert("fuel", priority, f"Fuel below {threshold} percent.")]
        return []

    def _tire_alerts(self, snapshot: RaceSnapshot) -> list[Alert]:
        if not self.config.category_enabled("tires", "critical"):
            return []
        alerts: list[Alert] = []
        hottest = snapshot.tire_temps.max()
        spread = snapshot.tire_temps.spread()
        if hottest is not None and hottest >= 115 and self._allowed("tire_hot", 30):
            alerts.append(self._alert("tires", "important", "Tire temps are high. Look after them."))
        if (
            spread is not None
            and spread >= 25
            and self.config.category_enabled("tires", "balanced")
            and self._allowed("tire_spread", 45)
        ):
            alerts.append(self._alert("tires", "info", "Tire temperature spread is building."))
        wear = snapshot.tire_wear_percent.max()
        if wear is not None and self.config.category_enabled("tires", "balanced"):
            stage = 0
            if wear >= 40:
                stage = 3
            elif wear >= 25:
                stage = 2
            elif wear >= 15:
                stage = 1
            if stage > self._tire_wear_stage and self._allowed("tire_wear", 90):
                self._tire_wear_stage = stage
                alerts.append(
                    self._alert(
                        "tires",
                        "important" if stage >= 2 else "info",
                        f"Estimated tire wear is {wear:.0f} percent on the worst corner.",
                    )
                )
        return alerts

    def _incident_alerts(self, update: StateUpdate) -> list[Alert]:
        if not update.incident_detected:
            return []
        if not self.config.category_enabled("incident", "balanced"):
            return []
        if not self._allowed(f"incident_{update.incident_detected}", 120):
            return []
        message = (
            "Possible spin detected. Get it settled."
            if update.incident_detected == "spin"
            else "Possible impact detected. Check the car."
        )
        return [self._alert("incident", "important", message)]

    def _driving_alerts(self, update: StateUpdate) -> list[Alert]:
        if update.completed_lap is None:
            return []
        if not self.config.category_enabled("driving", "detailed"):
            return []
        if not self._allowed("driving_style", 120):
            return []
        stats = update.snapshot.driving_style
        if stats.lockup_events >= 2:
            return [self._alert("driving", "info", "Brake lockups are building. Ease peak brake pressure.")]
        if stats.wheelspin_events >= 2:
            return [self._alert("driving", "info", "Wheelspin is costing traction. Squeeze the throttle on exit.")]
        if stats.tcs_events >= 3:
            return [self._alert("driving", "info", "Traction control is working often. Smooth the throttle inputs.")]
        if stats.asm_events >= 3:
            return [self._alert("driving", "info", "ASM is intervening often. Keep the car straighter on entry.")]
        return []

    def _car_alerts(self, snapshot: RaceSnapshot) -> list[Alert]:
        if not self.config.category_enabled("car", "critical"):
            return []
        alerts: list[Alert] = []
        if snapshot.water_temp is not None and snapshot.water_temp >= 110 and self._allowed("water_hot", 30):
            alerts.append(self._alert("car", "critical", "Water temperature is high."))
        if snapshot.oil_temp is not None and snapshot.oil_temp >= 130 and self._allowed("oil_hot", 30):
            alerts.append(self._alert("car", "critical", "Oil temperature is high."))
        return alerts

    def _alert(self, category: str, priority: str, message: str) -> Alert:
        alert = Alert(
            id=self._next_id,
            timestamp=time.time(),
            category=category,
            priority=priority,  # type: ignore[arg-type]
            message=message,
        )
        self._next_id += 1
        return alert

    def _allowed(self, key: str, cooldown_seconds: float) -> bool:
        now = time.time()
        last = self._last_by_key.get(key, 0)
        if now - last < cooldown_seconds:
            return False
        self._last_by_key[key] = now
        return True
