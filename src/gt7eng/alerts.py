from __future__ import annotations

import time

from .config import AppConfig
from .models import Alert, RaceSnapshot, StateUpdate
from .timefmt import format_delta, format_lap_time, plural


class AlertManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self._next_id = 1
        self._last_by_key: dict[str, float] = {}
        self._system_connected: bool | None = None

    def from_update(self, update: StateUpdate) -> list[Alert]:
        alerts: list[Alert] = []
        alerts.extend(self._position_alerts(update))
        alerts.extend(self._lap_alerts(update))
        alerts.extend(self._fuel_alerts(update.snapshot, completed=update.completed_lap is not None))
        alerts.extend(self._tire_alerts(update.snapshot))
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
            return []
        if update.position_changed is None:
            return []
        old, new = update.position_changed
        if old is None:
            message = f"P{new}."
        elif new < old:
            gained = old - new
            message = f"Gained {plural(gained, 'place')}, now P{new}."
        else:
            lost = new - old
            message = f"Lost {plural(lost, 'place')}, now P{new}."
        return [self._alert("position", "important", message)]

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
        if snap.laps_left is not None:
            parts.append(f"{plural(snap.laps_left, 'lap')} left.")
        return [self._alert("lap", "info", " ".join(parts))]

    def _fuel_alerts(self, snapshot: RaceSnapshot, completed: bool) -> list[Alert]:
        if not self.config.category_enabled("fuel", "critical"):
            return []
        margin = snapshot.fuel_margin_laps
        if margin is None:
            return []

        alerts: list[Alert] = []
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
        return alerts

    def _tire_alerts(self, snapshot: RaceSnapshot) -> list[Alert]:
        if not self.config.category_enabled("tires", "critical"):
            return []
        hottest = snapshot.tire_temps.max()
        spread = snapshot.tire_temps.spread()
        if hottest is not None and hottest >= 115 and self._allowed("tire_hot", 30):
            return [self._alert("tires", "important", "Tire temps are high. Look after them.")]
        if (
            spread is not None
            and spread >= 25
            and self.config.category_enabled("tires", "balanced")
            and self._allowed("tire_spread", 45)
        ):
            return [self._alert("tires", "info", "Tire temperature spread is building.")]
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
