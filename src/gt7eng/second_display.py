from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from .config import SecondDisplayConfig
from .models import Alert, RaceSnapshot
from .pixel_display import PixelClient, PixelFrame, _default_client_factory
from .pixel_themes import PREBUILT_PIXEL_THEMES

logger = logging.getLogger(__name__)

Color = tuple[int, int, int]
TIRE_NORMAL_COLOR = "00ff00"
TIRE_WARM_COLOR = "ffee00"
TIRE_HOT_COLOR = "ff0000"


FONT: dict[str, list[str]] = {
    " ": ["000", "000", "000", "000", "000"],
    "+": ["000", "010", "111", "010", "000"],
    "-": ["000", "000", "111", "000", "000"],
    ".": ["000", "000", "000", "000", "010"],
    ":": ["000", "010", "000", "010", "000"],
    "/": ["001", "001", "010", "100", "100"],
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "100", "100"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    "A": ["010", "101", "111", "101", "101"],
    "B": ["110", "101", "110", "101", "110"],
    "C": ["111", "100", "100", "100", "111"],
    "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "111", "100", "111"],
    "F": ["111", "100", "111", "100", "100"],
    "G": ["111", "100", "101", "101", "111"],
    "H": ["101", "101", "111", "101", "101"],
    "I": ["111", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "101", "111"],
    "K": ["101", "101", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101"],
    "N": ["101", "111", "111", "111", "101"],
    "O": ["111", "101", "101", "101", "111"],
    "P": ["111", "101", "111", "100", "100"],
    "Q": ["111", "101", "101", "111", "001"],
    "R": ["110", "101", "110", "101", "101"],
    "S": ["111", "100", "111", "001", "111"],
    "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "010"],
    "W": ["101", "101", "111", "111", "101"],
    "X": ["101", "101", "010", "101", "101"],
    "Y": ["101", "101", "010", "010", "010"],
    "Z": ["111", "001", "010", "100", "111"],
}


@dataclass(slots=True)
class SecondDisplayPalette:
    label: Color
    count: Color
    active: Color
    alert: Color
    delta_good: Color
    delta_bad: Color
    dim: Color
    tire_normal: Color
    tire_warm: Color
    tire_hot: Color


@dataclass(slots=True)
class ActiveFlags:
    tc: bool = False
    asm: bool = False
    ws: bool = False
    lck: bool = False


class SecondDisplayRenderer:
    def __init__(
        self,
        config: SecondDisplayConfig,
        *,
        width: int | None = None,
        height: int | None = None,
    ):
        self.config = config
        self.width = max(8, int(width or config.width))
        self.height = max(8, int(height or config.height))
        self.palette = palette_from_config(config)

    def render_snapshot(
        self,
        snapshot: RaceSnapshot,
        *,
        alert: Alert | None = None,
        active: ActiveFlags | None = None,
        now: float | None = None,
    ) -> PixelFrame:
        timestamp = time.monotonic() if now is None else now
        pixels = bytearray(self.width * self.height * 3)
        if alert is not None and self._draw_alert_page(pixels, snapshot, alert):
            return PixelFrame(self.width, self.height, bytes(pixels))
        if not _snapshot_is_available(snapshot):
            self._draw_center_text(pixels, "WAIT", self.palette.dim)
            return PixelFrame(self.width, self.height, bytes(pixels))
        flags = active or ActiveFlags(
            tc=snapshot.tcs_active,
            asm=snapshot.asm_active,
            ws=snapshot.wheelspin_active,
            lck=snapshot.lockup_active,
        )
        self._draw_coaching_page(pixels, snapshot, flags, timestamp)
        return PixelFrame(self.width, self.height, bytes(pixels))

    def render_black(self) -> PixelFrame:
        return PixelFrame(self.width, self.height, bytes(self.width * self.height * 3))

    def diagnostics(self, snapshot: RaceSnapshot) -> dict:
        stats = snapshot.driving_style
        return {
            "counts": {
                "tc": stats.tcs_events,
                "asm": stats.asm_events,
                "ws": stats.wheelspin_events,
                "lck": stats.lockup_events,
            },
            "active": {
                "tc": snapshot.tcs_active,
                "asm": snapshot.asm_active,
                "ws": snapshot.wheelspin_active,
                "lck": snapshot.lockup_active,
            },
        }

    def _draw_alert_page(
        self,
        pixels: bytearray,
        snapshot: RaceSnapshot,
        alert: Alert,
    ) -> bool:
        if alert.category == "car":
            return False
        if alert.category == "tires" and _tire_alert_is_age(alert):
            self._draw_tire_age_page(pixels, snapshot)
            return True
        if alert.category == "tires":
            self._draw_tire_page(pixels, snapshot)
            return True
        if alert.category == "lap":
            self._draw_lap_page(pixels, snapshot, alert)
            return True
        if alert.category == "position":
            self._draw_stack(pixels, "POS", _position_text(snapshot), self.palette.active)
            return True
        if alert.category in {"fuel", "fuel_lap"}:
            label = "BOX" if _fuel_alert_is_box(alert) else "FUEL"
            self._draw_fuel_page(pixels, snapshot, label)
            return True
        if alert.category == "incident":
            label = "SPIN" if "spin" in alert.message.lower() else "HIT"
            self._draw_center_text(pixels, label, self.palette.alert)
            return True
        if alert.category == "system":
            self._draw_center_text(pixels, "STALE", self.palette.alert)
            return True
        if alert.category == "driving":
            label, value = _driving_alert_text(alert, snapshot)
            self._draw_stack(pixels, label, value, self.palette.alert)
            return True
        self._draw_stack(
            pixels,
            _alert_category_label(alert),
            _alert_value_text(alert, snapshot),
            self.palette.alert,
        )
        return True

    def _draw_coaching_page(
        self,
        pixels: bytearray,
        snapshot: RaceSnapshot,
        active: ActiveFlags,
        timestamp: float,
    ) -> None:
        stats = snapshot.driving_style
        mid_x = self.width // 2
        secondary_height = max(8, self.height // 4)
        if active.ws or active.lck or stats.wheelspin_events or stats.lockup_events:
            secondary_height = max(10, self.height // 3)
        assist_height = max(1, self.height - secondary_height)
        self._draw_line_x(pixels, mid_x, self.palette.dim)
        self._draw_line_y(pixels, assist_height, self.palette.dim)
        flash_on = int(timestamp * 8 * 2) % 2 == 0
        assist_tiles = [
            (0, 0, mid_x, assist_height, "TC", stats.tcs_events, active.tc),
            (mid_x, 0, self.width - mid_x, assist_height, "ASM", stats.asm_events, active.asm),
        ]
        for x, y, width, height, label, count, is_active in assist_tiles:
            self._draw_assist_tile(
                pixels,
                x,
                y,
                width,
                height,
                label,
                _count_text(count),
                is_active,
                flash_on,
            )

        compact_tiles = [
            (0, assist_height, mid_x, secondary_height, "WS", stats.wheelspin_events, active.ws),
            (mid_x, assist_height, self.width - mid_x, secondary_height, "LCK", stats.lockup_events, active.lck),
        ]
        for x, y, width, height, label, count, is_active in compact_tiles:
            self._draw_compact_tile(
                pixels,
                x,
                y,
                width,
                height,
                _compact_count_text(label, count),
                count,
                is_active,
                flash_on,
            )

    def _draw_assist_tile(
        self,
        pixels: bytearray,
        x: int,
        y: int,
        width: int,
        height: int,
        label: str,
        count: str,
        active: bool,
        flash_on: bool,
    ) -> None:
        inset = 2 if width >= 24 and height >= 24 else 1
        label_color = self.palette.active if active and flash_on else self.palette.dim
        if not active and count != "0":
            label_color = self.palette.label
        count_color = self.palette.count if count != "0" else self.palette.dim
        self._draw_text_in_area(
            pixels,
            label,
            label_color,
            x + inset,
            y + inset,
            max(1, width - inset * 2),
            max(1, int(height * 0.36) - inset),
        )
        self._draw_text_in_area(
            pixels,
            count,
            count_color,
            x + inset,
            y + max(1, int(height * 0.35)),
            max(1, width - inset * 2),
            max(1, height - int(height * 0.35) - inset),
        )

    def _draw_compact_tile(
        self,
        pixels: bytearray,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        count: int,
        active: bool,
        flash_on: bool,
    ) -> None:
        inset = 1
        color = self.palette.alert if active and flash_on else self.palette.dim
        if not active and count > 0:
            color = self.palette.label
        self._draw_text_in_area(
            pixels,
            text,
            color,
            x + inset,
            y + inset,
            max(1, width - inset * 2),
            max(1, height - inset * 2),
        )

    def _draw_tire_page(self, pixels: bytearray, snapshot: RaceSnapshot) -> None:
        self._draw_tire_blocks(pixels, snapshot, 0, 0, self.width, self.height)

    def _draw_tire_age_page(self, pixels: bytearray, snapshot: RaceSnapshot) -> None:
        corner_size = max(8, min(self.width, self.height) // 4)
        corner_width = min(corner_size, max(1, self.width // 2))
        corner_height = min(corner_size, max(1, self.height // 2))
        tires = [
            (0, 0, corner_width, corner_height, "FL", snapshot.tire_temps.fl),
            (
                self.width - corner_width,
                0,
                corner_width,
                corner_height,
                "FR",
                snapshot.tire_temps.fr,
            ),
            (
                0,
                self.height - corner_height,
                corner_width,
                corner_height,
                "RL",
                snapshot.tire_temps.rl,
            ),
            (
                self.width - corner_width,
                self.height - corner_height,
                corner_width,
                corner_height,
                "RR",
                snapshot.tire_temps.rr,
            ),
        ]
        for x, y, width, height, label, temp in tires:
            self._draw_tire_block(pixels, x, y, width, height, label, temp)

        self._draw_text_in_area(
            pixels,
            _tire_age_text(snapshot),
            self.palette.count,
            corner_width,
            corner_height,
            max(1, self.width - corner_width * 2),
            max(1, self.height - corner_height * 2),
        )

    def _draw_tire_blocks(
        self,
        pixels: bytearray,
        snapshot: RaceSnapshot,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        mid_x = x + width // 2
        mid_y = y + height // 2
        tires = [
            (x, y, mid_x - x, mid_y - y, "FL", snapshot.tire_temps.fl),
            (mid_x, y, x + width - mid_x, mid_y - y, "FR", snapshot.tire_temps.fr),
            (x, mid_y, mid_x - x, y + height - mid_y, "RL", snapshot.tire_temps.rl),
            (
                mid_x,
                mid_y,
                x + width - mid_x,
                y + height - mid_y,
                "RR",
                snapshot.tire_temps.rr,
            ),
        ]
        for x0, y0, tile_width, tile_height, label, temp in tires:
            self._draw_tire_block(pixels, x0, y0, tile_width, tile_height, label, temp)

    def _draw_tire_block(
        self,
        pixels: bytearray,
        x: int,
        y: int,
        width: int,
        height: int,
        label: str,
        temp: float | None,
    ) -> None:
        color = self._tire_color(temp)
        self._fill_rect(pixels, x, y, width, height, color)
        text_color = (0, 0, 0) if _brightness(color) > 120 else self.palette.count
        self._draw_text_in_area(
            pixels,
            label,
            text_color,
            x + 1,
            y + 1,
            max(1, width - 2),
            max(1, height - 2),
        )

    def _tire_color(self, temp: float | None) -> Color:
        if temp is None or not math.isfinite(float(temp)):
            return self.palette.dim
        if temp >= 115:
            return self.palette.tire_hot
        if temp >= 100:
            return self.palette.tire_warm
        return self.palette.tire_normal

    def _draw_lap_page(
        self,
        pixels: bytearray,
        snapshot: RaceSnapshot,
        alert: Alert,
    ) -> None:
        top_height = max(8, self.height // 3)
        middle_height = max(8, self.height // 3)
        bottom_height = max(1, self.height - top_height - middle_height)
        delta_ms = _previous_lap_delta_ms(snapshot)
        if delta_ms is None:
            delta_color = self.palette.dim
        elif delta_ms <= 0:
            delta_color = self.palette.delta_good
        else:
            delta_color = self.palette.delta_bad
        self._draw_text_in_area(
            pixels,
            _lap_label(snapshot, alert),
            self.palette.active,
            1,
            1,
            self.width - 2,
            max(1, top_height - 1),
        )
        self._draw_text_in_area(
            pixels,
            _lap_time_text(snapshot),
            self.palette.count,
            1,
            top_height,
            self.width - 2,
            middle_height,
        )
        self._draw_text_in_area(
            pixels,
            _previous_lap_delta_text(snapshot),
            delta_color,
            1,
            top_height + middle_height,
            self.width - 2,
            bottom_height,
        )

    def _draw_fuel_page(
        self,
        pixels: bytearray,
        snapshot: RaceSnapshot,
        label: str,
    ) -> None:
        top_height = max(8, self.height // 3)
        middle_height = max(8, self.height // 3)
        bottom_height = max(1, self.height - top_height - middle_height)
        self._draw_text_in_area(
            pixels,
            label,
            self.palette.alert,
            1,
            1,
            self.width - 2,
            max(1, top_height - 1),
        )
        self._draw_text_in_area(
            pixels,
            _fuel_level_text(snapshot),
            self.palette.count,
            1,
            top_height,
            self.width - 2,
            middle_height,
        )
        self._draw_text_in_area(
            pixels,
            _fuel_used_text(snapshot),
            _fuel_used_color(snapshot, self.palette),
            1,
            top_height + middle_height,
            self.width - 2,
            bottom_height,
        )

    def _draw_stack(self, pixels: bytearray, top: str, bottom: str, color: Color) -> None:
        self._draw_text_in_area(
            pixels,
            top,
            color,
            1,
            1,
            self.width - 2,
            max(1, self.height // 2 - 2),
        )
        self._draw_text_in_area(
            pixels,
            bottom,
            self.palette.count,
            1,
            max(1, self.height // 2),
            self.width - 2,
            max(1, self.height // 2 - 1),
        )

    def _draw_center_text(self, pixels: bytearray, text: str, color: Color) -> None:
        self._draw_text_in_area(pixels, text, color, 1, 1, self.width - 2, self.height - 2)

    def _draw_text_in_area(
        self,
        pixels: bytearray,
        text: str,
        color: Color,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        pattern = _compose_text_pattern(text)
        if not pattern:
            return
        pattern_height = len(pattern)
        pattern_width = len(pattern[0])
        if pattern_width <= 0 or pattern_height <= 0:
            return
        scale = max(1, min(width // pattern_width, height // pattern_height))
        draw_width = pattern_width * scale
        draw_height = pattern_height * scale
        x_start = x + max(0, (width - draw_width) // 2)
        y_start = y + max(0, (height - draw_height) // 2)
        for row_index, row in enumerate(pattern):
            for col_index, value in enumerate(row):
                if value != "1":
                    continue
                x0 = x_start + col_index * scale
                y0 = y_start + row_index * scale
                for py in range(y0, min(y0 + scale, self.height)):
                    for px in range(x0, min(x0 + scale, self.width)):
                        _set_pixel(pixels, self.width, px, py, color)

    def _fill_rect(
        self,
        pixels: bytearray,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Color,
    ) -> None:
        for py in range(max(0, y), min(self.height, y + height)):
            for px in range(max(0, x), min(self.width, x + width)):
                _set_pixel(pixels, self.width, px, py, color)

    def _draw_line_x(self, pixels: bytearray, x: int, color: Color) -> None:
        if x <= 0 or x >= self.width:
            return
        for y in range(self.height):
            _set_pixel(pixels, self.width, x, y, color)

    def _draw_line_y(self, pixels: bytearray, y: int, color: Color) -> None:
        if y <= 0 or y >= self.height:
            return
        for x in range(self.width):
            _set_pixel(pixels, self.width, x, y, color)


class SecondDisplayManager:
    def __init__(
        self,
        config: SecondDisplayConfig,
        *,
        snapshot_provider: Callable[[], RaceSnapshot] | None = None,
        client_factory: Callable[[str], PixelClient] | None = None,
        renderer: SecondDisplayRenderer | None = None,
    ):
        self.config = config
        self.snapshot_provider = snapshot_provider
        self.client_factory = client_factory or _default_client_factory
        self.renderer = renderer or SecondDisplayRenderer(config)
        self._task: asyncio.Task | None = None
        self._wake_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: PixelClient | None = None
        self._latest_snapshot = RaceSnapshot()
        self._active_until = {"tc": 0.0, "asm": 0.0, "ws": 0.0, "lck": 0.0}
        self._last_counts = {"tc": 0, "asm": 0, "ws": 0, "lck": 0}
        self._active_alert: Alert | None = None
        self._active_alert_until = 0.0
        self._alert_queue: deque[Alert] = deque(maxlen=20)
        self._last_hash = ""
        self._stopping = False
        self._backoff_seconds = 1.0
        self._next_connect_at = 0.0
        self._connected = False
        self._last_error = ""
        self._last_sent_at: float | None = None
        self._frames_sent = 0
        self._device_width: int | None = None
        self._device_height: int | None = None
        self._reported_device_width: int | None = None
        self._reported_device_height: int | None = None

    async def start(self) -> None:
        if not self.config.enabled or self._task is not None:
            return
        self._loop = asyncio.get_running_loop()
        self._wake_event = asyncio.Event()
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="second-display")

    async def stop(self) -> None:
        self._stopping = True
        if self._wake_event is not None:
            self._wake_event.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._send_shutdown_frame()
        await self._disconnect()

    async def reconfigure(self) -> None:
        was_running = self._task is not None
        if was_running:
            await self.stop()
        self._last_hash = ""
        self._device_width = None
        self._device_height = None
        self._reported_device_width = None
        self._reported_device_height = None
        self.renderer = SecondDisplayRenderer(self.config)
        if self.config.enabled and was_running:
            await self.start()

    def publish(self, snapshot: RaceSnapshot) -> None:
        if not self.config.enabled:
            return
        self._latest_snapshot = snapshot
        self._track_active_events(snapshot)
        self._wake()

    def publish_alert(self, alert: Alert) -> None:
        if not self.config.enabled or alert.category == "car":
            return
        now = time.monotonic()
        if self._active_alert is None or now >= self._active_alert_until:
            self._active_alert = alert
            self._active_alert_until = now + self.config.alert_hold_seconds
        else:
            self._alert_queue.append(alert)
        self._wake()

    def status(self) -> dict:
        snapshot = self._current_snapshot()
        now = time.monotonic()
        return {
            "enabled": self.config.enabled,
            "configured": bool(self.config.address),
            "connected": self._connected,
            "address": _redact_address(self.config.address),
            "device_width": self._device_width,
            "device_height": self._device_height,
            "reported_device_width": self._reported_device_width,
            "reported_device_height": self._reported_device_height,
            "update_hz": self.config.update_hz,
            "brightness": self.config.brightness,
            "color_theme": self.config.color_theme,
            "alert": (
                {
                    "category": self._active_alert.category,
                    "message": self._active_alert.message,
                    "remaining_seconds": max(0.0, self._active_alert_until - now),
                    "queued": len(self._alert_queue),
                }
                if self._active_alert is not None and now < self._active_alert_until
                else None
            ),
            "display": self.renderer.diagnostics(snapshot),
            "last_error": self._last_error,
            "last_sent_at": self._last_sent_at,
            "frames_sent": self._frames_sent,
            "reconnect_backoff_seconds": self._backoff_seconds,
        }

    async def _run(self) -> None:
        interval = 1.0 / max(1.0, self.config.update_hz)
        while not self._stopping:
            try:
                await self._wait_for_next_tick(interval)
                snapshot = self._current_snapshot()
                now = time.monotonic()
                frame = self.renderer.render_snapshot(
                    snapshot,
                    alert=self._current_alert(now),
                    active=self._current_active_flags(snapshot, now),
                    now=now,
                )
                await self._send_frame(frame)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)
                logger.warning("Second display update failed: %s", exc)
                await self._disconnect()
                await asyncio.sleep(self._backoff_seconds)
                self._backoff_seconds = min(self._backoff_seconds * 2, 30.0)

    async def _wait_for_next_tick(self, interval: float) -> None:
        event = self._wake_event
        if event is None:
            await asyncio.sleep(interval)
            return
        try:
            await asyncio.wait_for(event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            return
        finally:
            event.clear()

    def _current_snapshot(self) -> RaceSnapshot:
        if self.snapshot_provider is not None:
            return self.snapshot_provider()
        return self._latest_snapshot

    def _track_active_events(self, snapshot: RaceSnapshot) -> None:
        now = time.monotonic()
        stats = snapshot.driving_style
        values = {
            "tc": (snapshot.tcs_active, stats.tcs_events),
            "asm": (snapshot.asm_active, stats.asm_events),
            "ws": (snapshot.wheelspin_active, stats.wheelspin_events),
            "lck": (snapshot.lockup_active, stats.lockup_events),
        }
        for key, (active, count) in values.items():
            if count < self._last_counts[key]:
                self._active_until[key] = 0.0
            elif active or count > self._last_counts[key]:
                self._active_until[key] = now + self.config.flash_hold_seconds
            self._last_counts[key] = count

    def _current_active_flags(self, snapshot: RaceSnapshot, now: float) -> ActiveFlags:
        return ActiveFlags(
            tc=snapshot.tcs_active or now < self._active_until["tc"],
            asm=snapshot.asm_active or now < self._active_until["asm"],
            ws=snapshot.wheelspin_active or now < self._active_until["ws"],
            lck=snapshot.lockup_active or now < self._active_until["lck"],
        )

    def _current_alert(self, now: float) -> Alert | None:
        if self._active_alert is not None and now >= self._active_alert_until:
            self._active_alert = None
        if self._active_alert is None and self._alert_queue:
            self._active_alert = self._alert_queue.popleft()
            self._active_alert_until = now + self.config.alert_hold_seconds
        return self._active_alert

    def _wake(self) -> None:
        if self._loop is not None and self._wake_event is not None:
            self._loop.call_soon_threadsafe(self._wake_event.set)

    async def _send_frame(self, frame: PixelFrame) -> None:
        frame_hash = hashlib.sha1(frame.pixels).hexdigest()
        if frame_hash == self._last_hash:
            return
        client = await self._ensure_connected()
        await client.send_image_hex(frame.to_png().hex(), ".png", resize_method="fit")
        self._last_hash = frame_hash
        self._last_sent_at = time.time()
        self._frames_sent += 1
        self._last_error = ""

    async def _ensure_connected(self) -> PixelClient:
        if not self.config.address:
            raise RuntimeError("GT7ENG_SECOND_DISPLAY_ADDRESS is not configured")
        if self._client is not None and self._connected:
            return self._client

        now = time.monotonic()
        if now < self._next_connect_at:
            await asyncio.sleep(self._next_connect_at - now)

        client = self.client_factory(self.config.address)
        await client.connect()
        await client.set_brightness(self.config.brightness)
        await client.set_orientation(self.config.orientation)
        self._client = client
        self._connected = True
        self._backoff_seconds = 1.0
        self._next_connect_at = 0.0
        self._update_device_info(client)
        self._sync_client_render_size(client)
        return client

    def _update_device_info(self, client: PixelClient) -> None:
        try:
            info = client.get_device_info()
        except Exception:
            return
        width = getattr(info, "width", None)
        height = getattr(info, "height", None)
        if isinstance(width, int) and width > 0:
            self._reported_device_width = width
        if isinstance(height, int) and height > 0:
            self._reported_device_height = height
        render_width, render_height = self._render_dimensions()
        self._device_width = render_width
        self._device_height = render_height
        if self.renderer.width != render_width or self.renderer.height != render_height:
            self.renderer = SecondDisplayRenderer(
                self.config,
                width=render_width,
                height=render_height,
            )

    def _render_dimensions(self) -> tuple[int, int]:
        if (
            self.config.size_source == "auto"
            and self._reported_device_width is not None
            and self._reported_device_height is not None
        ):
            return self._reported_device_width, self._reported_device_height
        return self.config.width, self.config.height

    def _sync_client_render_size(self, client: PixelClient) -> None:
        if self.config.size_source != "config":
            return
        session = getattr(client, "_session", None)
        info = getattr(session, "_device_info", None)
        if info is None:
            return
        try:
            info.width = self.config.width
            info.height = self.config.height
        except Exception:
            logger.debug("Second display device info dimensions could not be overridden.")

    async def _send_shutdown_frame(self) -> None:
        if self._client is None or not self._connected:
            return
        try:
            frame = self.renderer.render_black()
            await self._client.send_image_hex(frame.to_png().hex(), ".png", resize_method="fit")
        except Exception as exc:
            logger.debug("Second display shutdown frame failed: %s", exc)

    async def _disconnect(self) -> None:
        client = self._client
        self._client = None
        self._connected = False
        self._next_connect_at = time.monotonic() + self._backoff_seconds
        if client is None:
            return
        try:
            await client.disconnect()
        except Exception as exc:
            logger.debug("Second display disconnect failed: %s", exc)


def palette_from_config(config: SecondDisplayConfig) -> SecondDisplayPalette:
    theme = PREBUILT_PIXEL_THEMES.get(config.color_theme, PREBUILT_PIXEL_THEMES["simdt_blue"])

    def color(name: str, fallback: str) -> Color:
        return _hex_to_rgb(getattr(config, name) or fallback)

    return SecondDisplayPalette(
        label=color("label_color", theme["gear"]),
        count=color("count_color", "ffffff"),
        active=color("active_color", theme["rev_mid"]),
        alert=color("alert_color", theme["shift"]),
        delta_good=_hex_to_rgb(theme["fuel_safe"]),
        delta_bad=_hex_to_rgb("ff2d2d"),
        dim=color("dim_color", "203038"),
        tire_normal=color("tire_normal_color", TIRE_NORMAL_COLOR),
        tire_warm=color("tire_warm_color", TIRE_WARM_COLOR),
        tire_hot=color("tire_hot_color", TIRE_HOT_COLOR),
    )


def _snapshot_is_available(snapshot: RaceSnapshot) -> bool:
    return snapshot.connected and snapshot.session_phase in {"racing", "paused", "finished"}


def _count_text(value: int) -> str:
    value = max(0, int(value))
    if value < 10_000:
        return str(value)
    if value < 1_000_000:
        return f"{min(999, value // 1_000)}K"
    return "1M+"


def _compact_count_text(label: str, value: int) -> str:
    value = max(0, int(value))
    prefix = "LK" if label == "LCK" else label
    if value < 100:
        return f"{prefix}{value}"
    if value < 1_000:
        return f"{prefix[:1]}{value}"
    return f"{prefix[:1]}{_count_text(value)}"


def _ratio(value: int | None, total: int | None) -> str:
    if value is None:
        return "--"
    if total is None:
        return str(value)
    return f"{value}/{total}"


def _position_text(snapshot: RaceSnapshot) -> str:
    if snapshot.current_position is None:
        return "P--"
    if snapshot.total_cars is None:
        return f"P{snapshot.current_position}"
    return f"P{snapshot.current_position}/{snapshot.total_cars}"


def _fuel_alert_is_box(alert: Alert) -> bool:
    message = alert.message.lower()
    return "box" in message or "pit required" in message


def _tire_alert_is_age(alert: Alert) -> bool:
    return alert.message.lower().startswith("tire age ")


def _lap_label(snapshot: RaceSnapshot, alert: Alert) -> str:
    lap_number = snapshot.lap_history[-1].lap_number if snapshot.lap_history else None
    lap_number = lap_number or _alert_lap_number(alert) or snapshot.current_lap
    if lap_number is None:
        return "L--"
    if snapshot.total_laps is None:
        return f"L{lap_number}"
    return f"L{lap_number}/{snapshot.total_laps}"


def _lap_time_text(snapshot: RaceSnapshot) -> str:
    if not snapshot.lap_history:
        return "--:--"
    milliseconds = snapshot.lap_history[-1].lap_time_ms
    if milliseconds is None or milliseconds < 0:
        return "--:--"
    total_tenths = int(round(milliseconds / 100))
    total_seconds, tenths = divmod(total_tenths, 10)
    minutes, seconds = divmod(total_seconds, 60)
    if minutes >= 10:
        return f"{minutes}:{seconds:02}"
    return f"{minutes}:{seconds:02}.{tenths}"


def _previous_lap_delta_ms(snapshot: RaceSnapshot) -> int | None:
    if len(snapshot.lap_history) < 2:
        return None
    current = snapshot.lap_history[-1].lap_time_ms
    previous = snapshot.lap_history[-2].lap_time_ms
    if current is None or previous is None or current < 0 or previous < 0:
        return None
    return current - previous


def _previous_lap_delta_text(snapshot: RaceSnapshot) -> str:
    delta = _previous_lap_delta_ms(snapshot)
    if delta is None:
        return "--"
    sign = "+" if delta >= 0 else "-"
    return f"{sign}{abs(delta) / 1000:.1f}"


def _fuel_level_text(snapshot: RaceSnapshot) -> str:
    return _fuel_number(snapshot.fuel_level)


def _fuel_used_text(snapshot: RaceSnapshot) -> str:
    if not snapshot.lap_history:
        return "--"
    return _fuel_number(snapshot.lap_history[-1].fuel_used)


def _fuel_used_delta(snapshot: RaceSnapshot) -> float | None:
    if len(snapshot.lap_history) < 2:
        return None
    current = snapshot.lap_history[-1].fuel_used
    previous = snapshot.lap_history[-2].fuel_used
    if current is None or previous is None:
        return None
    if not math.isfinite(float(current)) or not math.isfinite(float(previous)):
        return None
    return float(current) - float(previous)


def _fuel_used_color(snapshot: RaceSnapshot, palette: SecondDisplayPalette) -> Color:
    delta = _fuel_used_delta(snapshot)
    if delta is None:
        return palette.count
    if delta <= 0:
        return palette.delta_good
    return palette.delta_bad


def _fuel_number(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return "--"
    value = max(0.0, min(100.0, float(value)))
    if value < 10 and abs(value - round(value)) >= 0.05:
        return f"{value:.1f}"
    return f"{value:.0f}"


def _tire_age_text(snapshot: RaceSnapshot) -> str:
    age = None
    if snapshot.lap_history:
        age = snapshot.lap_history[-1].tire_age_laps
    if age is None:
        age = snapshot.tire_age_laps
    if age is None:
        return "--"
    return _count_text(max(0, int(age)))


def _driving_alert_text(alert: Alert, snapshot: RaceSnapshot) -> tuple[str, str]:
    message = alert.message.lower()
    stats = _last_lap_driving_style(snapshot)
    if "lockup" in message:
        return "LCK", _count_text(stats.lockup_events)
    if "wheelspin" in message:
        return "WS", _count_text(stats.wheelspin_events)
    if "traction" in message or "tcs" in message:
        return "TC", _count_text(stats.tcs_events)
    if "asm" in message:
        return "ASM", _count_text(stats.asm_events)
    return "DRV", _dominant_driving_count(snapshot)


def _last_lap_driving_style(snapshot: RaceSnapshot):
    if snapshot.lap_history:
        return snapshot.lap_history[-1].driving_style
    return snapshot.driving_style


def _dominant_driving_count(snapshot: RaceSnapshot) -> str:
    stats = _last_lap_driving_style(snapshot)
    value = max(
        stats.tcs_events,
        stats.asm_events,
        stats.wheelspin_events,
        stats.lockup_events,
    )
    return _count_text(value)


def _alert_category_label(alert: Alert) -> str:
    labels = {
        "pit": "PIT",
        "voice": "VOIC",
        "fuel": "FUEL",
        "lap": "LAP",
        "position": "POS",
        "tires": "TIRE",
        "incident": "INC",
        "system": "SYS",
    }
    return labels.get(alert.category, alert.category[:4].upper() or "ALRT")


def _alert_value_text(alert: Alert, snapshot: RaceSnapshot) -> str:
    if alert.category == "pit":
        return _fuel_level_text(snapshot)
    if alert.priority == "critical":
        return "CRIT"
    if alert.priority == "important":
        return "IMP"
    return "INFO"


def _alert_lap_number(alert: Alert) -> int | None:
    message = alert.message.strip()
    if not message.lower().startswith("lap "):
        return None
    digits = []
    for ch in message[4:]:
        if ch.isdigit():
            digits.append(ch)
            continue
        break
    if not digits:
        return None
    return int("".join(digits))


def _compose_text_pattern(text: str) -> list[str]:
    chars = [ch.upper() for ch in text[:8]]
    patterns = [FONT.get(ch, FONT["-"]) for ch in chars]
    if not patterns:
        return []
    composed: list[str] = []
    for row_index in range(len(patterns[0])):
        composed.append("0".join(pattern[row_index] for pattern in patterns))
    return composed


def _set_pixel(pixels: bytearray, width: int, x: int, y: int, color: Color) -> None:
    offset = (y * width + x) * 3
    pixels[offset] = color[0]
    pixels[offset + 1] = color[1]
    pixels[offset + 2] = color[2]


def _hex_to_rgb(value: str) -> Color:
    normalized = value.strip().lstrip("#")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def _brightness(color: Color) -> float:
    return color[0] * 0.299 + color[1] * 0.587 + color[2] * 0.114


def _redact_address(address: str) -> str:
    if not address:
        return ""
    if len(address) <= 8:
        return "***"
    return f"{address[:4]}...{address[-4:]}"


def preview_png(
    config: SecondDisplayConfig,
    snapshot: RaceSnapshot,
    *,
    alert: Alert | None = None,
) -> bytes:
    renderer = SecondDisplayRenderer(config)
    return renderer.render_snapshot(snapshot, alert=alert).to_png()
