from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Callable, Protocol

import httpx

from .config import WindConfig
from .models import RaceSnapshot

logger = logging.getLogger(__name__)


class WindClient(Protocol):
    async def set_level(self, level: int) -> None:
        ...


class HomeAssistantWindClient:
    def __init__(self, config: WindConfig):
        self.config = config

    async def set_level(self, level: int) -> None:
        if not self.config.ha_base_url:
            raise RuntimeError("GT7ENG_WIND_HA_BASE_URL is not configured")
        if not self.config.ha_token:
            raise RuntimeError("GT7ENG_WIND_HA_TOKEN is not configured")
        if not self.config.ha_entity_id:
            raise RuntimeError("GT7ENG_WIND_HA_ENTITY_ID is not configured")

        url = f"{self.config.ha_base_url.rstrip('/')}/api/services/number/set_value"
        headers = {
            "Authorization": f"Bearer {self.config.ha_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": self.config.ha_entity_id, "value": level}
        timeout = httpx.Timeout(self.config.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()


class HomeAssistantWindManager:
    def __init__(
        self,
        config: WindConfig,
        *,
        snapshot_provider: Callable[[], RaceSnapshot] | None = None,
        client_factory: Callable[[WindConfig], WindClient] | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.config = config
        self.snapshot_provider = snapshot_provider
        self.client_factory = client_factory or HomeAssistantWindClient
        self.clock = clock or time.monotonic
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._latest_snapshot = RaceSnapshot()
        self._client: WindClient | None = None
        self._connected = False
        self._last_error = ""
        self._backoff_seconds = 1.0
        self._next_send_at = 0.0
        self._last_sent_at: float | None = None
        self._last_sent_level: int | None = None
        self._target_level = self._off_level()
        self._smoothed_level = float(self._off_level())
        self._current_level: int | None = None
        self._commands_sent = 0
        self._last_tick_at: float | None = None
        self._last_send_attempt_at: float | None = None

    async def start(self) -> None:
        if not self.config.enabled or self._task is not None:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="ha-wind")

    async def stop(self) -> None:
        self._stopping = True
        task = self._task
        was_running = task is not None
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if was_running and self.configured:
            await self._send_level(self._off_level(), force=True)

    async def reconfigure(self) -> None:
        was_running = self._task is not None
        if was_running:
            await self.stop()
        self._client = None
        self._last_error = ""
        self._connected = False
        self._target_level = self._off_level()
        self._smoothed_level = float(self._off_level())
        self._current_level = None
        self._last_sent_level = None
        self._last_tick_at = None
        self._last_send_attempt_at = None
        if self.config.enabled and was_running:
            await self.start()

    def publish(self, snapshot: RaceSnapshot) -> None:
        if not self.config.enabled:
            return
        self._latest_snapshot = snapshot

    def status(self) -> dict:
        return {
            "enabled": self.config.enabled,
            "configured": self.configured,
            "connected": self._connected,
            "ha_base_url": self.config.ha_base_url,
            "ha_entity_id": self.config.ha_entity_id,
            "update_hz": self.config.update_hz,
            "max_speed_kph": self.config.max_speed_kph,
            "curve_exponent": self.config.curve_exponent,
            "deadband_kph": self.config.deadband_kph,
            "min_level": self.config.min_level,
            "max_level": self.config.max_level,
            "smoothing_seconds": self.config.smoothing_seconds,
            "hysteresis_levels": self.config.hysteresis_levels,
            "timeout_seconds": self.config.timeout_seconds,
            "current_level": self._current_level,
            "target_level": self._target_level,
            "smoothed_level": self._smoothed_level,
            "last_sent_level": self._last_sent_level,
            "last_sent_at": self._last_sent_at,
            "last_error": self._last_error,
            "reconnect_backoff_seconds": self._backoff_seconds,
            "commands_sent": self._commands_sent,
        }

    @property
    def configured(self) -> bool:
        return bool(
            self.config.ha_base_url
            and self.config.ha_token
            and self.config.ha_entity_id
        )

    async def update_once(self, *, now: float | None = None) -> None:
        timestamp = self.clock() if now is None else now
        snapshot = self._current_snapshot()
        self._target_level = self.target_level(snapshot)
        command_level = self._smooth_target(timestamp)
        self._current_level = command_level
        if not self._should_send(command_level):
            return
        await self._send_level(command_level, now=timestamp)

    def target_level(self, snapshot: RaceSnapshot) -> int:
        if not _snapshot_is_active(snapshot):
            return self._off_level()
        speed = _finite_float(snapshot.speed_kph)
        if speed is None or speed < self.config.deadband_kph:
            return self._off_level()

        low, high = self._level_bounds()
        span = max(0, high - low)
        if span == 0:
            return low
        normalized = _clamp(speed / max(1.0, self.config.max_speed_kph), 0.0, 1.0)
        curved = math.pow(normalized, self.config.curve_exponent)
        level = low + int(round(curved * span))
        if level <= low:
            level = min(high, low + 1)
        return int(_clamp(level, low, high))

    async def _run(self) -> None:
        interval = self._interval()
        while not self._stopping:
            try:
                await asyncio.sleep(interval)
                await self.update_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)
                self._connected = False
                logger.warning("Home Assistant wind update failed: %s", exc)
                await asyncio.sleep(self._backoff_seconds)
                self._backoff_seconds = min(self._backoff_seconds * 2, 30.0)

    def _current_snapshot(self) -> RaceSnapshot:
        if self.snapshot_provider is not None:
            return self.snapshot_provider()
        return self._latest_snapshot

    def _smooth_target(self, timestamp: float) -> int:
        if self._last_tick_at is None:
            elapsed = self._interval()
            self._last_tick_at = timestamp
        else:
            elapsed = max(0.0, timestamp - self._last_tick_at)
            self._last_tick_at = timestamp
        smoothing = max(0.0, self.config.smoothing_seconds)
        if smoothing <= 0:
            self._smoothed_level = float(self._target_level)
        else:
            alpha = _clamp(elapsed / smoothing, 0.0, 1.0)
            self._smoothed_level += (self._target_level - self._smoothed_level) * alpha
        low, high = self._level_bounds()
        return int(round(_clamp(self._smoothed_level, low, high)))

    def _should_send(self, level: int) -> bool:
        if self._last_sent_level is None:
            return True
        threshold = max(0, int(self.config.hysteresis_levels))
        return abs(level - self._last_sent_level) >= threshold and level != self._last_sent_level

    async def _send_level(
        self,
        level: int,
        *,
        force: bool = False,
        now: float | None = None,
    ) -> None:
        if not self.configured:
            self._connected = False
            self._last_error = "Home Assistant wind is not fully configured"
            return
        timestamp = self.clock() if now is None else now
        if (
            not force
            and self._last_send_attempt_at is not None
            and timestamp - self._last_send_attempt_at < self._interval()
        ):
            return
        if not force and timestamp < self._next_send_at:
            return
        self._last_send_attempt_at = timestamp
        client = self._client or self.client_factory(self.config)
        self._client = client
        try:
            await client.set_level(level)
        except Exception as exc:
            self._connected = False
            self._last_error = str(exc)
            self._next_send_at = timestamp + self._backoff_seconds
            self._backoff_seconds = min(self._backoff_seconds * 2, 30.0)
            return
        self._connected = True
        self._last_error = ""
        self._backoff_seconds = 1.0
        self._next_send_at = 0.0
        self._last_sent_level = level
        self._current_level = level
        self._last_sent_at = time.time()
        self._commands_sent += 1

    def _interval(self) -> float:
        return 1.0 / max(0.1, self.config.update_hz)

    def _off_level(self) -> int:
        low, _ = self._level_bounds()
        return low

    def _level_bounds(self) -> tuple[int, int]:
        low = max(0, int(self.config.min_level))
        high = max(low, int(self.config.max_level))
        return low, high


def _snapshot_is_active(snapshot: RaceSnapshot) -> bool:
    return snapshot.connected and snapshot.session_phase == "racing"


def _finite_float(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
