from __future__ import annotations

import asyncio
import binascii
import hashlib
import logging
import math
import struct
import time
import zlib
from dataclasses import dataclass
from typing import Callable, Protocol

from .config import PixelDisplayConfig
from .models import RaceSnapshot

logger = logging.getLogger(__name__)

Color = tuple[int, int, int]


THEMES: dict[str, dict[str, str]] = {
    "simdt_blue": {
        "gear": "31d7ff",
        "rev_low": "26d8ff",
        "rev_mid": "ff96f0",
        "rev_high": "ff3d86",
        "shift": "ff4aa8",
        "fuel_safe": "26d8ff",
        "fuel_warn": "ff96f0",
        "fuel_danger": "ff3d86",
        "fuel_critical": "ff2d2d",
    },
    "warm_amber": {
        "gear": "ff8a24",
        "rev_low": "ff9f2e",
        "rev_mid": "ff5f1a",
        "rev_high": "c51616",
        "shift": "ff2400",
        "fuel_safe": "ffb347",
        "fuel_warn": "ff8a24",
        "fuel_danger": "ff4b1f",
        "fuel_critical": "c51616",
    },
    "race_gyr": {
        "gear": "f5f8ff",
        "rev_low": "00d36f",
        "rev_mid": "ffd21f",
        "rev_high": "ff2d2d",
        "shift": "ff2d2d",
        "fuel_safe": "00d36f",
        "fuel_warn": "ffd21f",
        "fuel_danger": "ff7a1f",
        "fuel_critical": "ff2d2d",
    },
}


GLYPHS: dict[str, list[str]] = {
    "0": ["111", "101", "101", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "010", "010", "111"],
    "2": ["111", "001", "001", "111", "100", "100", "111"],
    "3": ["111", "001", "001", "111", "001", "001", "111"],
    "4": ["101", "101", "101", "111", "001", "001", "001"],
    "5": ["111", "100", "100", "111", "001", "001", "111"],
    "6": ["111", "100", "100", "111", "101", "101", "111"],
    "7": ["111", "001", "001", "010", "010", "100", "100"],
    "8": ["111", "101", "101", "111", "101", "101", "111"],
    "9": ["111", "101", "101", "111", "001", "001", "111"],
    "N": ["101", "111", "111", "111", "111", "111", "101"],
    "R": ["110", "101", "101", "110", "101", "101", "101"],
    "-": ["000", "000", "000", "111", "000", "000", "000"],
}


@dataclass(slots=True)
class PixelFrame:
    width: int
    height: int
    pixels: bytes

    def to_png(self) -> bytes:
        return encode_png(self.width, self.height, self.pixels)

    def pixel(self, x: int, y: int) -> Color:
        offset = (y * self.width + x) * 3
        return (
            self.pixels[offset],
            self.pixels[offset + 1],
            self.pixels[offset + 2],
        )


@dataclass(slots=True)
class PixelPalette:
    gear: Color
    rev_low: Color
    rev_mid: Color
    rev_high: Color
    shift: Color
    fuel_safe: Color
    fuel_warn: Color
    fuel_danger: Color
    fuel_critical: Color


@dataclass(slots=True)
class RevBarState:
    percent: float
    start_rpm: float | None
    full_rpm: float | None
    source: str


@dataclass(slots=True)
class FuelBarState:
    enabled: bool
    visible: bool
    percent: float | None
    position: str
    color_zone: str


class PixelClient(Protocol):
    async def connect(self) -> None:
        ...

    async def disconnect(self) -> None:
        ...

    def get_device_info(self):
        ...

    async def set_brightness(self, level: int) -> None:
        ...

    async def set_orientation(self, orientation: int) -> None:
        ...

    async def send_image_hex(
        self,
        hex_string: str | bytes,
        file_extension: str,
        resize_method: str = "fit",
        save_slot: int = 0,
    ) -> None:
        ...


class PixelDisplayRenderer:
    def __init__(
        self,
        config: PixelDisplayConfig,
        *,
        width: int | None = None,
        height: int | None = None,
    ):
        self.config = config
        self.width = max(8, int(width or config.width))
        self.height = max(8, int(height or config.height))
        self.palette = palette_from_config(config)

    def render_snapshot(self, snapshot: RaceSnapshot, *, now: float | None = None) -> PixelFrame:
        timestamp = time.monotonic() if now is None else now
        pixels = bytearray(self.width * self.height * 3)
        if not _snapshot_is_live(snapshot):
            self._draw_idle(pixels)
            return PixelFrame(self.width, self.height, bytes(pixels))

        rev_state = self.rev_state(snapshot)
        self._draw_rev_bar(pixels, rev_state.percent)
        self._draw_fuel_bar(pixels, self.fuel_state(snapshot))

        shift_active = self.shift_active(snapshot, rev_state.percent)
        flash_on = True
        if shift_active:
            flash_on = int(timestamp * self.config.flash_hz * 2) % 2 == 0
        gear_color = self.palette.shift if shift_active else self.palette.gear
        if flash_on:
            self._draw_gears(pixels, snapshot, gear_color)
        return PixelFrame(self.width, self.height, bytes(pixels))

    def render_black(self) -> PixelFrame:
        return PixelFrame(self.width, self.height, bytes(self.width * self.height * 3))

    def rev_percent(self, snapshot: RaceSnapshot) -> float:
        return self.rev_state(snapshot).percent

    def rev_state(self, snapshot: RaceSnapshot) -> RevBarState:
        rpm = snapshot.engine_rpm
        start_rpm, full_rpm, source = self._rev_range(snapshot)
        if snapshot.rev_limit:
            return RevBarState(1.0, start_rpm, full_rpm, source)
        if rpm is None:
            return RevBarState(0.0, start_rpm, full_rpm, source)
        if start_rpm is None or full_rpm is None or full_rpm <= start_rpm:
            return RevBarState(0.0, start_rpm, full_rpm, source)
        percent = _clamp((rpm - start_rpm) / (full_rpm - start_rpm), 0.0, 1.0)
        return RevBarState(percent, start_rpm, full_rpm, source)

    def shift_active(self, snapshot: RaceSnapshot, rev_percent: float | None = None) -> bool:
        if snapshot.rev_limit:
            return True
        if self.config.shift_mode == "percent":
            percent = self.rev_percent(snapshot) if rev_percent is None else rev_percent
            return percent >= self.config.shift_percent
        return False

    def rev_diagnostics(self, snapshot: RaceSnapshot) -> dict:
        state = self.rev_state(snapshot)
        return {
            "engine_rpm": snapshot.engine_rpm,
            "start_rpm": state.start_rpm,
            "full_rpm": state.full_rpm,
            "percent": state.percent,
            "source": state.source,
            "scale": self.config.rev_scale,
            "shift_mode": self.config.shift_mode,
            "gear_layout": self.config.gear_layout,
            "shift_active": self.shift_active(snapshot, state.percent),
        }

    def fuel_diagnostics(self, snapshot: RaceSnapshot) -> dict:
        state = self.fuel_state(snapshot)
        return {
            "enabled": state.enabled,
            "visible": state.visible,
            "percent": state.percent,
            "position": state.position,
            "color_zone": state.color_zone,
        }

    def fuel_state(self, snapshot: RaceSnapshot) -> FuelBarState:
        position = self._fuel_position()
        if not self.config.fuel_enabled:
            return FuelBarState(False, False, None, position, "hidden")
        value = _finite_float(snapshot.fuel_level)
        if value is None:
            return FuelBarState(True, False, None, position, "hidden")
        if value >= 100:
            return FuelBarState(True, False, None, position, "hidden")
        percent = _clamp(value, 0.0, 100.0)
        return FuelBarState(True, True, percent, position, self._fuel_color_zone(percent))

    def _rev_range(self, snapshot: RaceSnapshot) -> tuple[float | None, float | None, str]:
        if self.config.rev_scale == "wide":
            alert_max = _positive(snapshot.max_alert_rpm)
            if alert_max is not None:
                return alert_max * self.config.rev_start_percent, alert_max, "gt_alert_max"
            rpm_min = _positive(self.config.rpm_min)
            rpm_max = _positive(self.config.rpm_max)
            if rpm_min is not None and rpm_max is not None and rpm_max > rpm_min:
                return rpm_min, rpm_max, "config"
            return None, None, "none"

        rpm_min = _positive(snapshot.min_alert_rpm)
        rpm_max = _positive(snapshot.max_alert_rpm)
        if rpm_min is not None and rpm_max is not None and rpm_max > rpm_min:
            return rpm_min, rpm_max, "gt_alert_window"
        rpm_min = _positive(self.config.rpm_min)
        rpm_max = _positive(self.config.rpm_max)
        if rpm_min is not None and rpm_max is not None and rpm_max > rpm_min:
            return rpm_min, rpm_max, "config"
        return None, None, "none"

    def _draw_idle(self, pixels: bytearray) -> None:
        color = _scale_color(self.palette.rev_mid, self._dim_scale())
        self._draw_label(pixels, "--", color)

    def _draw_rev_bar(self, pixels: bytearray, rev_percent: float) -> None:
        bar_height = max(1, self.height // 10)
        y_start = 0 if self.config.rev_position == "top" else self.height - bar_height
        filled = int(round(_clamp(rev_percent, 0.0, 1.0) * self.width))
        for y in range(y_start, y_start + bar_height):
            for x in range(filled):
                position = (x + 1) / self.width
                if position >= 0.9:
                    color = self.palette.rev_high
                elif position >= 0.7:
                    color = self.palette.rev_mid
                else:
                    color = self.palette.rev_low
                _set_pixel(pixels, self.width, x, y, color)

    def _draw_fuel_bar(self, pixels: bytearray, state: FuelBarState) -> None:
        if not state.visible or state.percent is None:
            return
        y = 0 if state.position == "top" else self.height - 1
        percent = _clamp(state.percent, 0.0, 100.0)
        filled = int(round((percent / 100.0) * self.width))
        if percent > 0:
            filled = max(1, filled)
        color = self._fuel_color(state.color_zone)
        for x in range(min(self.width, filled)):
            _set_pixel(pixels, self.width, x, y, color)

    def _fuel_position(self) -> str:
        return "bottom" if self.config.rev_position == "top" else "top"

    def _fuel_color_zone(self, percent: float) -> str:
        if percent <= 10:
            return "critical"
        if percent <= 20:
            return "danger"
        if percent <= 50:
            return "warn"
        return "safe"

    def _fuel_color(self, zone: str) -> Color:
        if zone == "critical":
            return self.palette.fuel_critical
        if zone == "danger":
            return self.palette.fuel_danger
        if zone == "warn":
            return self.palette.fuel_warn
        return self.palette.fuel_safe

    def _draw_label(self, pixels: bytearray, label: str, color: Color) -> None:
        self._draw_label_in_area(pixels, label, color, 3, self.width - 3)

    def _draw_gears(
        self,
        pixels: bytearray,
        snapshot: RaceSnapshot,
        gear_color: Color,
    ) -> None:
        current_label = _gear_label(snapshot.current_gear)
        suggested_label = _suggested_gear_label(
            snapshot.current_gear,
            snapshot.suggested_gear,
        )
        if self.config.gear_layout != "current_suggested":
            self._draw_label(pixels, current_label, gear_color)
            return

        split = max(1, int(self.width * 0.65))
        main_scale = self._draw_label_in_area(
            pixels,
            current_label,
            gear_color,
            1,
            split,
        )
        if suggested_label is None:
            return
        suggested_color = _scale_color(self.palette.gear, 0.45)
        suggested_max_scale = max(1, min(main_scale - 1, round(main_scale * 0.75)))
        self._draw_label_in_area(
            pixels,
            suggested_label,
            suggested_color,
            min(self.width - 1, split + 1),
            self.width - 1,
            max_scale=suggested_max_scale,
        )

    def _draw_label_in_area(
        self,
        pixels: bytearray,
        label: str,
        color: Color,
        x_min: int,
        x_max: int,
        *,
        max_scale: int | None = None,
    ) -> int:
        pattern = _compose_label_pattern(label)
        pattern_height = len(pattern)
        pattern_width = len(pattern[0])
        bar_height = max(1, self.height // 10)
        y_min = bar_height + 2 if self.config.rev_position == "top" else 2
        y_max = self.height - bar_height - 2 if self.config.rev_position == "bottom" else self.height - 2
        x_min = max(0, min(self.width - 1, x_min))
        x_max = max(x_min + 1, min(self.width, x_max))
        available_width = max(1, x_max - x_min)
        available_height = max(1, y_max - y_min)
        scale = max(1, min(available_width // pattern_width, available_height // pattern_height))
        if max_scale is not None:
            scale = max(1, min(scale, max_scale))
        draw_width = pattern_width * scale
        draw_height = pattern_height * scale
        x_start = x_min + max(0, (available_width - draw_width) // 2)
        y_start = max(y_min, y_min + (available_height - draw_height) // 2)
        for row_index, row in enumerate(pattern):
            for col_index, value in enumerate(row):
                if value != "1":
                    continue
                x0 = x_start + col_index * scale
                y0 = y_start + row_index * scale
                for y in range(y0, min(y0 + scale, self.height)):
                    for x in range(x0, min(x0 + scale, self.width)):
                        _set_pixel(pixels, self.width, x, y, color)
        return scale

    def _dim_scale(self) -> float:
        if self.config.brightness <= 0:
            return 0.2
        return _clamp(self.config.dim_brightness / self.config.brightness, 0.05, 1.0)


class PixelDisplayManager:
    def __init__(
        self,
        config: PixelDisplayConfig,
        *,
        snapshot_provider: Callable[[], RaceSnapshot] | None = None,
        client_factory: Callable[[str], PixelClient] | None = None,
        renderer: PixelDisplayRenderer | None = None,
    ):
        self.config = config
        self.snapshot_provider = snapshot_provider
        self.client_factory = client_factory or _default_client_factory
        self.renderer = renderer or PixelDisplayRenderer(config)
        self._task: asyncio.Task | None = None
        self._wake_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: PixelClient | None = None
        self._latest_snapshot = RaceSnapshot()
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
        self._task = asyncio.create_task(self._run(), name="pixel-display")

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

    def publish(self, snapshot: RaceSnapshot) -> None:
        if not self.config.enabled:
            return
        self._latest_snapshot = snapshot
        if self._loop is not None and self._wake_event is not None:
            self._loop.call_soon_threadsafe(self._wake_event.set)

    def status(self) -> dict:
        snapshot = self._current_snapshot()
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
            "rev_position": self.config.rev_position,
            "gear_layout": self.config.gear_layout,
            "color_theme": self.config.color_theme,
            "brightness": self.config.brightness,
            "rev": self.renderer.rev_diagnostics(snapshot),
            "fuel": self.renderer.fuel_diagnostics(snapshot),
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
                frame = self.renderer.render_snapshot(snapshot)
                await self._send_frame(frame)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)
                logger.warning("Pixel display update failed: %s", exc)
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
            raise RuntimeError("GT7ENG_PIXEL_DISPLAY_ADDRESS is not configured")
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
            self.renderer = PixelDisplayRenderer(
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
            logger.debug("Pixel display device info dimensions could not be overridden.")

    async def _send_shutdown_frame(self) -> None:
        if self._client is None or not self._connected:
            return
        try:
            frame = self.renderer.render_black()
            await self._client.send_image_hex(frame.to_png().hex(), ".png", resize_method="fit")
        except Exception as exc:
            logger.debug("Pixel display shutdown frame failed: %s", exc)

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
            logger.debug("Pixel display disconnect failed: %s", exc)


def palette_from_config(config: PixelDisplayConfig) -> PixelPalette:
    base = THEMES.get(config.color_theme, THEMES["simdt_blue"])
    values = dict(base)
    base_overrides = {
        "gear": config.gear_color,
        "rev_low": config.rev_low_color,
        "rev_mid": config.rev_mid_color,
        "rev_high": config.rev_high_color,
        "shift": config.shift_color,
    }
    for key, value in base_overrides.items():
        if value:
            values[key] = value
    if config.color_theme == "custom":
        values.update(
            {
                "fuel_safe": values["rev_low"],
                "fuel_warn": values["rev_mid"],
                "fuel_danger": values["rev_high"],
                "fuel_critical": values["shift"],
            }
        )
    fuel_overrides = {
        "fuel_safe": config.fuel_safe_color,
        "fuel_warn": config.fuel_warn_color,
        "fuel_danger": config.fuel_danger_color,
        "fuel_critical": config.fuel_critical_color,
    }
    for key, value in fuel_overrides.items():
        if value:
            values[key] = value
    return PixelPalette(
        gear=_hex_to_rgb(values["gear"]),
        rev_low=_hex_to_rgb(values["rev_low"]),
        rev_mid=_hex_to_rgb(values["rev_mid"]),
        rev_high=_hex_to_rgb(values["rev_high"]),
        shift=_hex_to_rgb(values["shift"]),
        fuel_safe=_hex_to_rgb(values["fuel_safe"]),
        fuel_warn=_hex_to_rgb(values["fuel_warn"]),
        fuel_danger=_hex_to_rgb(values["fuel_danger"]),
        fuel_critical=_hex_to_rgb(values["fuel_critical"]),
    )


def encode_png(width: int, height: int, pixels: bytes) -> bytes:
    if len(pixels) != width * height * 3:
        raise ValueError("RGB pixel buffer size does not match dimensions")
    rows = []
    row_size = width * 3
    for y in range(height):
        start = y * row_size
        rows.append(b"\x00" + pixels[start : start + row_size])
    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = binascii.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _default_client_factory(address: str) -> PixelClient:
    try:
        import pypixelcolor
    except ImportError as exc:
        raise RuntimeError(
            "pypixelcolor is not installed. Run `pip install -e '.[pixel-display]'`."
        ) from exc
    return pypixelcolor.AsyncClient(address)


def _snapshot_is_live(snapshot: RaceSnapshot) -> bool:
    return (
        snapshot.connected
        and snapshot.session_phase == "racing"
        and snapshot.current_gear is not None
    )


def _gear_label(gear: int | None) -> str:
    if gear is None:
        return "--"
    if gear <= 0:
        return "N"
    if 1 <= gear <= 9:
        return str(gear)
    return str(gear)[:2]


def _suggested_gear_label(current_gear: int | None, suggested_gear: int | None) -> str | None:
    if suggested_gear is None:
        return None
    if suggested_gear <= 0 or suggested_gear > 9:
        return None
    if suggested_gear == current_gear:
        return None
    return str(suggested_gear)


def _compose_label_pattern(label: str) -> list[str]:
    chars = [ch.upper() for ch in label[:2]]
    patterns = [GLYPHS.get(ch, GLYPHS["-"]) for ch in chars]
    if len(patterns) == 1:
        return patterns[0]
    composed = []
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


def _scale_color(color: Color, scale: float) -> Color:
    return (
        int(color[0] * scale),
        int(color[1] * scale),
        int(color[2] * scale),
    )


def _positive(value: float | None) -> float | None:
    if value is None:
        return None
    return value if value > 0 else None


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


def _redact_address(address: str) -> str:
    if not address:
        return ""
    if len(address) <= 8:
        return "***"
    return f"{address[:4]}...{address[-4:]}"
