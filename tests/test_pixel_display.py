from __future__ import annotations

from types import SimpleNamespace

import pytest

from gt7eng.config import PixelDisplayConfig
from gt7eng.config import AppConfig
from gt7eng.cli import _pixel_preview
from gt7eng.cli import _doctor_pixel_display
from gt7eng.models import RaceSnapshot
from gt7eng.pixel_display import PixelDisplayManager, PixelDisplayRenderer, palette_from_config
from gt7eng.pixel_themes import PIXEL_COLOR_THEMES, PREBUILT_PIXEL_THEMES


def racing_snapshot(**overrides) -> RaceSnapshot:
    data = {
        "connected": True,
        "session_phase": "racing",
        "engine_rpm": 7500.0,
        "min_alert_rpm": 6000.0,
        "max_alert_rpm": 8000.0,
        "current_gear": 3,
        "rev_limit": False,
    }
    data.update(overrides)
    return RaceSnapshot(**data)


def non_black_pixels(frame) -> int:
    return sum(
        1
        for index in range(0, len(frame.pixels), 3)
        if frame.pixels[index : index + 3] != b"\x00\x00\x00"
    )


def non_black_pixels_in_gear_area(frame, *, x_min: int = 0, x_max: int | None = None) -> int:
    x_max = frame.width if x_max is None else x_max
    bar_height = max(1, frame.height // 10)
    y_max = frame.height - bar_height - 2
    return sum(
        1
        for y in range(0, y_max)
        for x in range(x_min, x_max)
        if frame.pixel(x, y) != (0, 0, 0)
    )


def first_non_black_x_in_gear_area(frame) -> int | None:
    bar_height = max(1, frame.height // 10)
    y_max = frame.height - bar_height - 2
    xs = [
        x
        for y in range(0, y_max)
        for x in range(frame.width)
        if frame.pixel(x, y) != (0, 0, 0)
    ]
    return min(xs) if xs else None


def non_black_pixels_in_row(frame, y: int) -> int:
    return sum(1 for x in range(frame.width) if frame.pixel(x, y) != (0, 0, 0))


def test_renderer_draws_bottom_rev_bar_by_default():
    renderer = PixelDisplayRenderer(PixelDisplayConfig())

    frame = renderer.render_snapshot(racing_snapshot())

    assert frame.width == 64
    assert frame.height == 64
    assert frame.pixel(0, 63) != (0, 0, 0)
    assert frame.pixel(0, 0) == (0, 0, 0)
    assert non_black_pixels(frame) > 200


def test_renderer_draws_top_rev_bar_when_configured():
    config = PixelDisplayConfig(rev_position="top")
    renderer = PixelDisplayRenderer(config)

    frame = renderer.render_snapshot(racing_snapshot())

    assert frame.pixel(0, 0) != (0, 0, 0)
    assert frame.pixel(0, 63) == (0, 0, 0)


def test_renderer_uses_warm_amber_theme():
    config = PixelDisplayConfig(color_theme="warm_amber")
    renderer = PixelDisplayRenderer(config)

    frame = renderer.render_snapshot(racing_snapshot())

    assert renderer.palette.gear == (255, 138, 36)
    assert any(
        frame.pixel(x, y) == renderer.palette.gear
        for y in range(frame.height)
        for x in range(frame.width)
    )


def test_all_prebuilt_pixel_themes_are_complete_and_render():
    required_keys = {
        "gear",
        "rev_low",
        "rev_mid",
        "rev_high",
        "shift",
        "fuel_safe",
        "fuel_warn",
        "fuel_danger",
        "fuel_critical",
    }

    allowed_keys = required_keys | {"suggested_gear"}

    assert len(PREBUILT_PIXEL_THEMES) >= 13
    assert PIXEL_COLOR_THEMES == (*PREBUILT_PIXEL_THEMES.keys(), "custom")
    for theme, colors in PREBUILT_PIXEL_THEMES.items():
        assert required_keys <= set(colors) <= allowed_keys
        assert all(len(value) == 6 for value in colors.values())

        renderer = PixelDisplayRenderer(
            PixelDisplayConfig(color_theme=theme, fuel_enabled=True)
        )
        frame = renderer.render_snapshot(racing_snapshot(fuel_level=75.0))

        assert frame.pixel(0, 0) == renderer.palette.fuel_safe
        assert non_black_pixels(frame) > 200


def test_user_tuned_themes_keep_expected_red_bias():
    def red_dominant(hex_color: str) -> bool:
        red = int(hex_color[0:2], 16)
        green = int(hex_color[2:4], 16)
        blue = int(hex_color[4:6], 16)
        return red > green and red > blue

    assert PREBUILT_PIXEL_THEMES["night_vision"]["shift"] == "ff2d2d"
    assert PREBUILT_PIXEL_THEMES["night_vision"]["rev_mid"] == "ff9f1c"
    assert PREBUILT_PIXEL_THEMES["night_vision"]["rev_high"] == PREBUILT_PIXEL_THEMES["night_vision"]["shift"]
    for theme in ("carbon_red", "fuji_sunset"):
        for key in ("gear", "rev_low", "rev_mid", "rev_high", "shift", "fuel_safe"):
            assert red_dominant(PREBUILT_PIXEL_THEMES[theme][key])


def test_gulf_classic_uses_orange_suggested_gear_and_shift_flash():
    renderer = PixelDisplayRenderer(
        PixelDisplayConfig(color_theme="gulf_classic", gear_layout="current_suggested")
    )

    frame = renderer.render_snapshot(
        racing_snapshot(current_gear=4, suggested_gear=3, rev_limit=False)
    )

    assert renderer.palette.suggested_gear == (255, 107, 53)
    assert renderer.palette.shift == (255, 107, 53)
    assert any(
        frame.pixel(x, y) == renderer.palette.suggested_gear
        for y in range(frame.height)
        for x in range(44, frame.width)
    )


def test_renderer_current_layout_ignores_suggested_gear():
    renderer = PixelDisplayRenderer(PixelDisplayConfig(gear_layout="current"))

    current = renderer.render_snapshot(racing_snapshot(current_gear=4))
    suggested = renderer.render_snapshot(
        racing_snapshot(current_gear=4, suggested_gear=3)
    )

    assert suggested.pixels == current.pixels


def test_renderer_current_suggested_layout_draws_larger_right_gear():
    renderer = PixelDisplayRenderer(PixelDisplayConfig(gear_layout="current_suggested"))

    current = renderer.render_snapshot(racing_snapshot(current_gear=4))
    suggested = renderer.render_snapshot(
        racing_snapshot(current_gear=4, suggested_gear=3)
    )

    assert first_non_black_x_in_gear_area(suggested) == first_non_black_x_in_gear_area(current)
    assert non_black_pixels_in_gear_area(current, x_min=44) == 0
    assert non_black_pixels_in_gear_area(suggested, x_min=44) > 0


def test_renderer_current_suggested_layout_keeps_suggested_visible_on_32px_display():
    renderer = PixelDisplayRenderer(
        PixelDisplayConfig(gear_layout="current_suggested"),
        width=32,
        height=32,
    )

    frame = renderer.render_snapshot(racing_snapshot(current_gear=4, suggested_gear=3))

    assert non_black_pixels_in_gear_area(frame, x_min=21) >= 40


@pytest.mark.parametrize("suggested_gear", [None, 0, 4, 10])
def test_renderer_hides_invalid_suggested_gear_values(suggested_gear):
    renderer = PixelDisplayRenderer(PixelDisplayConfig(gear_layout="current_suggested"))

    current = renderer.render_snapshot(racing_snapshot(current_gear=4))
    suggested = renderer.render_snapshot(
        racing_snapshot(current_gear=4, suggested_gear=suggested_gear)
    )

    assert suggested.pixels == current.pixels


def test_renderer_supports_custom_theme_overrides():
    config = PixelDisplayConfig(
        color_theme="custom",
        gear_color="ff8800",
        rev_low_color="123456",
        rev_mid_color="abcdef",
        rev_high_color="654321",
        shift_color="ff0000",
    )

    palette = palette_from_config(config)

    assert palette.gear == (255, 136, 0)
    assert palette.rev_low == (18, 52, 86)
    assert palette.fuel_safe == (18, 52, 86)
    assert palette.fuel_warn == (171, 205, 239)
    assert palette.fuel_danger == (101, 67, 33)
    assert palette.fuel_critical == (255, 0, 0)
    assert palette.shift == (255, 0, 0)


def test_renderer_supports_custom_fuel_color_overrides():
    config = PixelDisplayConfig(
        color_theme="custom",
        fuel_safe_color="00ff00",
        fuel_warn_color="ffee00",
        fuel_danger_color="ff6600",
        fuel_critical_color="ff0000",
    )

    palette = palette_from_config(config)

    assert palette.fuel_safe == (0, 255, 0)
    assert palette.fuel_warn == (255, 238, 0)
    assert palette.fuel_danger == (255, 102, 0)
    assert palette.fuel_critical == (255, 0, 0)


def test_renderer_uses_env_rpm_fallback_when_snapshot_lacks_alert_range():
    config = PixelDisplayConfig(rpm_min=1000.0, rpm_max=2000.0)
    renderer = PixelDisplayRenderer(config)

    percent = renderer.rev_percent(
        racing_snapshot(engine_rpm=1500.0, min_alert_rpm=None, max_alert_rpm=None)
    )

    assert percent == 0.5


def test_renderer_wide_scale_uses_max_alert_rpm_for_full_bar():
    renderer = PixelDisplayRenderer(PixelDisplayConfig())

    assert renderer.rev_percent(
        racing_snapshot(engine_rpm=5400.0, max_alert_rpm=9000.0)
    ) == 0.0
    assert renderer.rev_percent(
        racing_snapshot(engine_rpm=7200.0, max_alert_rpm=9000.0)
    ) == pytest.approx(0.5)
    assert renderer.rev_percent(
        racing_snapshot(engine_rpm=9000.0, max_alert_rpm=9000.0)
    ) == 1.0


def test_renderer_full_bar_reaches_last_pixel_at_max_alert_rpm():
    renderer = PixelDisplayRenderer(PixelDisplayConfig())

    frame = renderer.render_snapshot(racing_snapshot(engine_rpm=9000.0, max_alert_rpm=9000.0))

    assert frame.pixel(63, 63) != (0, 0, 0)


def test_renderer_rev_limit_forces_full_bar():
    renderer = PixelDisplayRenderer(PixelDisplayConfig())
    snapshot = racing_snapshot(engine_rpm=8100.0, max_alert_rpm=9000.0, rev_limit=True)

    frame = renderer.render_snapshot(snapshot)

    assert renderer.rev_percent(snapshot) == 1.0
    assert frame.pixel(63, 63) != (0, 0, 0)


@pytest.mark.parametrize("fuel_level", [None, 100.0, 120.0])
def test_renderer_hides_fuel_bar_without_active_fuel_usage(fuel_level):
    renderer = PixelDisplayRenderer(PixelDisplayConfig(fuel_enabled=True))

    frame = renderer.render_snapshot(racing_snapshot(fuel_level=fuel_level))

    assert renderer.fuel_state(racing_snapshot(fuel_level=fuel_level)).visible is False
    assert non_black_pixels_in_row(frame, 0) == 0


def test_renderer_draws_top_fuel_bar_when_rev_bar_is_bottom():
    renderer = PixelDisplayRenderer(PixelDisplayConfig(fuel_enabled=True))

    frame = renderer.render_snapshot(racing_snapshot(fuel_level=75.0))

    assert renderer.fuel_state(racing_snapshot(fuel_level=75.0)).position == "top"
    assert non_black_pixels_in_row(frame, 0) == 48
    assert frame.pixel(47, 0) == renderer.palette.fuel_safe
    assert frame.pixel(48, 0) == (0, 0, 0)
    assert non_black_pixels_in_row(frame, 1) == 0


def test_renderer_draws_bottom_fuel_bar_when_rev_bar_is_top():
    renderer = PixelDisplayRenderer(
        PixelDisplayConfig(fuel_enabled=True, rev_position="top"),
        width=32,
        height=32,
    )

    frame = renderer.render_snapshot(racing_snapshot(fuel_level=50.0))

    assert renderer.fuel_state(racing_snapshot(fuel_level=50.0)).position == "bottom"
    assert non_black_pixels_in_row(frame, 31) == 16
    assert frame.pixel(15, 31) == renderer.palette.fuel_warn
    assert frame.pixel(16, 31) == (0, 0, 0)
    assert frame.pixel(0, 30) == (0, 0, 0)


@pytest.mark.parametrize(
    ("fuel_level", "expected_width", "zone"),
    [
        (75.0, 48, "safe"),
        (50.0, 32, "warn"),
        (20.0, 13, "danger"),
        (10.0, 6, "critical"),
        (0.4, 1, "critical"),
    ],
)
def test_renderer_fuel_bar_width_and_warning_zones(fuel_level, expected_width, zone):
    renderer = PixelDisplayRenderer(PixelDisplayConfig(fuel_enabled=True))

    frame = renderer.render_snapshot(racing_snapshot(fuel_level=fuel_level))
    state = renderer.fuel_state(racing_snapshot(fuel_level=fuel_level))

    assert state.color_zone == zone
    assert non_black_pixels_in_row(frame, 0) == expected_width


@pytest.mark.parametrize(
    ("theme", "fuel_level", "expected_color"),
    [
        ("simdt_blue", 75.0, (38, 216, 255)),
        ("simdt_blue", 10.0, (255, 45, 45)),
        ("warm_amber", 50.0, (255, 138, 36)),
        ("race_gyr", 20.0, (255, 122, 31)),
        ("race_gyr", 10.0, (255, 45, 45)),
    ],
)
def test_renderer_fuel_bar_theme_colors(theme, fuel_level, expected_color):
    renderer = PixelDisplayRenderer(
        PixelDisplayConfig(fuel_enabled=True, color_theme=theme)
    )

    frame = renderer.render_snapshot(racing_snapshot(fuel_level=fuel_level))

    assert frame.pixel(0, 0) == expected_color


def test_renderer_fuel_bar_does_not_shift_existing_layout():
    without_fuel = PixelDisplayRenderer(PixelDisplayConfig())
    with_fuel = PixelDisplayRenderer(PixelDisplayConfig(fuel_enabled=True))

    base = without_fuel.render_snapshot(racing_snapshot(current_gear=4, fuel_level=75.0))
    fuel = with_fuel.render_snapshot(racing_snapshot(current_gear=4, fuel_level=75.0))

    for y in range(1, base.height):
        for x in range(base.width):
            assert fuel.pixel(x, y) == base.pixel(x, y)


def test_renderer_does_not_flash_before_rev_limit_by_default():
    renderer = PixelDisplayRenderer(PixelDisplayConfig())
    snapshot = racing_snapshot(engine_rpm=8856.0, max_alert_rpm=9000.0, rev_limit=False)

    first_frame = renderer.render_snapshot(snapshot, now=0.0)
    second_frame = renderer.render_snapshot(snapshot, now=0.1)

    assert renderer.rev_percent(snapshot) == pytest.approx(0.96)
    assert first_frame.pixels == second_frame.pixels


def test_renderer_percent_shift_mode_can_flash_before_rev_limit():
    config = PixelDisplayConfig(shift_mode="percent", shift_percent=0.96)
    renderer = PixelDisplayRenderer(config)
    snapshot = racing_snapshot(engine_rpm=8856.0, max_alert_rpm=9000.0, rev_limit=False)

    on_frame = renderer.render_snapshot(snapshot, now=0.0)
    off_frame = renderer.render_snapshot(snapshot, now=0.1)

    assert non_black_pixels(on_frame) > non_black_pixels(off_frame)


def test_renderer_idle_state_is_dim_unavailable_marker_without_rev_bar():
    renderer = PixelDisplayRenderer(PixelDisplayConfig())

    frame = renderer.render_snapshot(RaceSnapshot(connected=False, session_phase="stale"))

    assert frame.pixel(0, 63) == (0, 0, 0)
    assert non_black_pixels(frame) > 0


def test_renderer_shift_flash_toggles_gear_pixels():
    config = PixelDisplayConfig(flash_hz=8.0)
    renderer = PixelDisplayRenderer(config)
    snapshot = racing_snapshot(rev_limit=True)

    on_frame = renderer.render_snapshot(snapshot, now=0.0)
    off_frame = renderer.render_snapshot(snapshot, now=0.1)

    assert non_black_pixels(on_frame) > non_black_pixels(off_frame)


def test_renderer_shift_flash_toggles_suggested_gear_with_current_gear():
    config = PixelDisplayConfig(gear_layout="current_suggested", flash_hz=8.0)
    renderer = PixelDisplayRenderer(config)
    snapshot = racing_snapshot(current_gear=4, suggested_gear=3, rev_limit=True)

    on_frame = renderer.render_snapshot(snapshot, now=0.0)
    off_frame = renderer.render_snapshot(snapshot, now=0.1)

    assert non_black_pixels_in_gear_area(on_frame) > 0
    assert non_black_pixels_in_gear_area(off_frame) == 0


def test_pixel_preview_writes_png(tmp_path):
    output = tmp_path / "preview.png"

    result = _pixel_preview(
        AppConfig(),
        output,
        gear=4,
        suggested_gear=3,
        rpm_percent=0.8,
        fuel_percent=42.0,
        shift=False,
        idle=False,
        width=64,
        height=64,
        theme="warm_amber",
        rev_position="bottom",
    )

    assert result == 0
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_doctor_pixel_output_includes_fuel_state(capsys):
    config = AppConfig(pixel_display=PixelDisplayConfig(fuel_enabled=True))

    assert _doctor_pixel_display(config) is True

    assert "fuel=on" in capsys.readouterr().out


class FakePixelClient:
    def __init__(self, *, width: int = 64, height: int = 64):
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.brightness: list[int] = []
        self.orientation: list[int] = []
        self.sent: list[str | bytes] = []
        self.info = SimpleNamespace(width=width, height=height)
        self._session = SimpleNamespace(_device_info=self.info)

    async def connect(self) -> None:
        self.connect_calls += 1

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    def get_device_info(self):
        return self.info

    async def set_brightness(self, level: int) -> None:
        self.brightness.append(level)

    async def set_orientation(self, orientation: int) -> None:
        self.orientation.append(orientation)

    async def send_image_hex(
        self,
        hex_string: str | bytes,
        file_extension: str,
        resize_method: str = "fit",
        save_slot: int = 0,
    ) -> None:
        assert file_extension == ".png"
        assert resize_method == "fit"
        self.sent.append(hex_string)


@pytest.mark.asyncio
async def test_manager_keeps_one_connection_and_sends_deduped_frames():
    config = PixelDisplayConfig(enabled=True, address="device-uuid", update_hz=30)
    snapshot = racing_snapshot()
    fake = FakePixelClient()
    manager = PixelDisplayManager(
        config,
        snapshot_provider=lambda: snapshot,
        client_factory=lambda _address: fake,
    )

    await manager.start()
    manager.publish(snapshot)
    manager.publish(snapshot)
    await asyncio_sleep()
    await manager.stop()

    assert fake.connect_calls == 1
    assert fake.brightness == [60]
    assert fake.orientation == [0]
    assert fake.disconnect_calls == 1
    assert len(fake.sent) >= 2
    assert manager.status()["frames_sent"] == 1


@pytest.mark.asyncio
async def test_manager_auto_size_uses_reported_device_size():
    config = PixelDisplayConfig(enabled=True, address="device-uuid", width=64, height=64)
    snapshot = racing_snapshot()
    fake = FakePixelClient(width=32, height=32)
    manager = PixelDisplayManager(
        config,
        snapshot_provider=lambda: snapshot,
        client_factory=lambda _address: fake,
    )

    await manager.start()
    manager.publish(snapshot)
    await asyncio_sleep()
    status = manager.status()
    await manager.stop()

    assert manager.renderer.width == 32
    assert manager.renderer.height == 32
    assert status["device_width"] == 32
    assert status["device_height"] == 32
    assert status["reported_device_width"] == 32
    assert status["reported_device_height"] == 32
    assert fake.info.width == 32
    assert fake.info.height == 32


@pytest.mark.asyncio
async def test_manager_config_size_can_override_reported_device_size():
    config = PixelDisplayConfig(
        enabled=True,
        address="device-uuid",
        width=64,
        height=64,
        size_source="config",
    )
    snapshot = racing_snapshot()
    fake = FakePixelClient(width=32, height=32)
    manager = PixelDisplayManager(
        config,
        snapshot_provider=lambda: snapshot,
        client_factory=lambda _address: fake,
    )

    await manager.start()
    manager.publish(snapshot)
    await asyncio_sleep()
    status = manager.status()
    await manager.stop()

    assert manager.renderer.width == 64
    assert manager.renderer.height == 64
    assert status["device_width"] == 64
    assert status["device_height"] == 64
    assert status["reported_device_width"] == 32
    assert status["reported_device_height"] == 32
    assert fake.info.width == 64
    assert fake.info.height == 64


async def asyncio_sleep() -> None:
    import asyncio

    await asyncio.sleep(0.08)
