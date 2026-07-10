from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from gt7eng.config import AppConfig, SecondDisplayConfig
from gt7eng.models import Alert, DrivingStyleStats, LapRecord, RaceSnapshot, WheelValues
from gt7eng.second_display import (
    ActiveFlags,
    SecondDisplayManager,
    SecondDisplayRenderer,
    _alert_category_label,
    _count_text,
    _driving_alert_text,
    _fuel_level_text,
    _fuel_used_text,
    _lap_label,
    _lap_time_text,
    _previous_lap_delta_text,
    _tire_age_text,
    palette_from_config,
)
from gt7eng.service import RaceEngineerService
from gt7eng.telemetry import synthetic_frame
from gt7eng.pixel_themes import PREBUILT_PIXEL_THEMES


def racing_snapshot(**overrides) -> RaceSnapshot:
    data = {
        "connected": True,
        "session_phase": "racing",
        "driving_style": DrivingStyleStats(
            tcs_events=3,
            asm_events=1,
            wheelspin_events=4,
            lockup_events=2,
        ),
    }
    data.update(overrides)
    return RaceSnapshot(**data)


def alert(category: str, message: str, priority: str = "important") -> Alert:
    return Alert(1, 0.0, category, priority, message)  # type: ignore[arg-type]


def non_black_pixels(frame) -> int:
    return sum(
        1
        for index in range(0, len(frame.pixels), 3)
        if frame.pixels[index : index + 3] != b"\x00\x00\x00"
    )


def contains_color(frame, color) -> bool:
    return any(
        frame.pixel(x, y) == color
        for y in range(frame.height)
        for x in range(frame.width)
    )


def test_renderer_draws_coaching_counts_and_active_flash():
    renderer = SecondDisplayRenderer(SecondDisplayConfig())
    snapshot = racing_snapshot(tcs_active=True, wheelspin_active=True)

    on_frame = renderer.render_snapshot(snapshot, now=0.0)
    off_frame = renderer.render_snapshot(snapshot, now=0.07)

    assert non_black_pixels(on_frame) > 0
    assert contains_color(on_frame, renderer.palette.active)
    assert contains_color(on_frame, renderer.palette.alert)
    assert on_frame.pixels != off_frame.pixels


def test_renderer_supports_32px_coaching_layout():
    renderer = SecondDisplayRenderer(SecondDisplayConfig(), width=32, height=32)

    frame = renderer.render_snapshot(
        racing_snapshot(
            driving_style=DrivingStyleStats(
                tcs_events=142,
                asm_events=1234,
                wheelspin_events=0,
                lockup_events=0,
            )
        ),
        now=0.0,
    )

    assert frame.width == 32
    assert frame.height == 32
    assert non_black_pixels(frame) > 40
    top_pixels = sum(
        1
        for y in range(0, 24)
        for x in range(frame.width)
        if frame.pixel(x, y) != (0, 0, 0)
    )
    bottom_pixels = sum(
        1
        for y in range(24, frame.height)
        for x in range(frame.width)
        if frame.pixel(x, y) != (0, 0, 0)
    )
    assert top_pixels > bottom_pixels


def test_count_text_keeps_large_tc_and_asm_counts_useful():
    assert _count_text(42) == "42"
    assert _count_text(1234) == "1234"
    assert _count_text(9999) == "9999"
    assert _count_text(12_345) == "12K"
    assert _count_text(999_999) == "999K"
    assert _count_text(1_000_000) == "1M+"


def test_renderer_tire_alert_uses_four_corner_temperature_colors():
    config = SecondDisplayConfig(
        tire_normal_color="00ff00",
        tire_warm_color="ffee00",
        tire_hot_color="ff0000",
        dim_color="101010",
    )
    renderer = SecondDisplayRenderer(config)
    snapshot = racing_snapshot(
        tire_temps=WheelValues(fl=90.0, fr=105.0, rl=116.0, rr=None)
    )

    frame = renderer.render_snapshot(
        snapshot,
        alert=alert("tires", "Tire temps are high. Look after them."),
    )

    assert frame.pixel(1, 1) == (0, 255, 0)
    assert frame.pixel(33, 1) == (255, 238, 0)
    assert frame.pixel(1, 33) == (255, 0, 0)
    assert frame.pixel(33, 33) == (16, 16, 16)


def test_renderer_tire_age_alert_shows_age_and_temperature_colors():
    config = SecondDisplayConfig(
        tire_normal_color="00ff00",
        tire_warm_color="ffee00",
        tire_hot_color="ff0000",
        dim_color="101010",
    )
    renderer = SecondDisplayRenderer(config, width=32, height=32)
    snapshot = racing_snapshot(
        tire_age_laps=3,
        tire_temps=WheelValues(fl=90.0, fr=105.0, rl=116.0, rr=None),
        lap_history=[
            LapRecord(
                lap_number=3,
                lap_time_ms=92_000,
                fuel_used=6.0,
                completed_at=10.0,
                tire_age_laps=3,
            )
        ],
    )

    frame = renderer.render_snapshot(
        snapshot,
        alert=alert("tires", "Tire age 3 laps."),
    )

    assert _tire_age_text(snapshot) == "3"
    assert contains_color(frame, renderer.palette.count)
    assert frame.pixel(0, 0) == (0, 255, 0)
    assert frame.pixel(31, 0) == (255, 238, 0)
    assert frame.pixel(0, 31) == (255, 0, 0)
    assert frame.pixel(31, 31) == (16, 16, 16)
    assert frame.pixel(16, 16) == renderer.palette.count


def test_tire_temperature_colors_are_theme_independent():
    expected = {
        "tire_normal": (0, 255, 0),
        "tire_warm": (255, 238, 0),
        "tire_hot": (255, 0, 0),
    }

    for theme in ("simdt_blue", "night_vision", "carbon_red", "fuji_sunset"):
        palette = palette_from_config(SecondDisplayConfig(color_theme=theme))
        assert palette.tire_normal == expected["tire_normal"]
        assert palette.tire_warm == expected["tire_warm"]
        assert palette.tire_hot == expected["tire_hot"]


def test_carbon_red_tire_age_alert_renders_normal_temps_green():
    renderer = SecondDisplayRenderer(
        SecondDisplayConfig(color_theme="carbon_red"),
        width=32,
        height=32,
    )
    snapshot = racing_snapshot(
        tire_age_laps=2,
        tire_temps=WheelValues(fl=90.0, fr=91.0, rl=92.0, rr=93.0),
    )

    frame = renderer.render_snapshot(
        snapshot,
        alert=alert("tires", "Tire age 2 laps."),
    )

    assert frame.pixel(0, 0) == (0, 255, 0)
    assert frame.pixel(31, 0) == (0, 255, 0)
    assert frame.pixel(0, 31) == (0, 255, 0)
    assert frame.pixel(31, 31) == (0, 255, 0)


def test_renderer_lap_alert_shows_lap_time_and_previous_lap_delta():
    renderer = SecondDisplayRenderer(SecondDisplayConfig(), width=32, height=32)
    snapshot = racing_snapshot(
        total_laps=5,
        lap_history=[
            LapRecord(
                lap_number=1,
                lap_time_ms=100_000,
                fuel_used=7.0,
                completed_at=1.0,
            ),
            LapRecord(
                lap_number=2,
                lap_time_ms=98_000,
                fuel_used=6.5,
                completed_at=2.0,
            ),
        ],
    )

    frame = renderer.render_snapshot(
        snapshot,
        alert=alert("lap", "Lap 2: 1:38. Two laps left."),
    )

    assert _lap_label(snapshot, alert("lap", "Lap 2: 1:38.")) == "L2/5"
    assert _lap_time_text(snapshot) == "1:38.0"
    assert _previous_lap_delta_text(snapshot) == "-2.0"
    assert contains_color(frame, renderer.palette.delta_good)
    assert contains_color(frame, renderer.palette.count)


def test_positive_delta_green_uses_night_vision_theme_green():
    renderer = SecondDisplayRenderer(
        SecondDisplayConfig(color_theme="night_vision"),
        width=32,
        height=32,
    )
    expected = PREBUILT_PIXEL_THEMES["night_vision"]["fuel_safe"]

    assert renderer.palette.delta_good == (86, 224, 0)
    assert expected == "56e000"


def test_fuel_lap_delta_green_uses_night_vision_theme_green():
    renderer = SecondDisplayRenderer(
        SecondDisplayConfig(color_theme="night_vision"),
        width=32,
        height=32,
    )
    snapshot = racing_snapshot(
        fuel_level=75.0,
        lap_history=[
            LapRecord(
                lap_number=1,
                lap_time_ms=92_000,
                fuel_used=7.0,
                completed_at=10.0,
            ),
            LapRecord(
                lap_number=2,
                lap_time_ms=91_000,
                fuel_used=6.5,
                completed_at=20.0,
            ),
        ],
    )

    frame = renderer.render_snapshot(
        snapshot,
        alert=alert("fuel_lap", "Lap fuel usage."),
    )

    assert renderer.palette.delta_good == (86, 224, 0)
    assert contains_color(frame, renderer.palette.delta_good)


def test_renderer_lap_alert_uses_red_for_slower_delta():
    renderer = SecondDisplayRenderer(SecondDisplayConfig(), width=32, height=32)
    snapshot = racing_snapshot(
        total_laps=5,
        lap_history=[
            LapRecord(
                lap_number=1,
                lap_time_ms=98_000,
                fuel_used=7.0,
                completed_at=1.0,
            ),
            LapRecord(
                lap_number=2,
                lap_time_ms=100_000,
                fuel_used=6.5,
                completed_at=2.0,
            ),
        ],
    )

    frame = renderer.render_snapshot(
        snapshot,
        alert=alert("lap", "Lap 2: 1:40. Three laps left."),
    )

    assert _previous_lap_delta_text(snapshot) == "+2.0"
    assert contains_color(frame, renderer.palette.delta_bad)


def test_lap_delta_handles_first_lap_and_lap_race_without_total():
    snapshot = racing_snapshot(
        total_laps=None,
        lap_history=[
            LapRecord(
                lap_number=1,
                lap_time_ms=83_450,
                fuel_used=5.0,
                completed_at=1.0,
            )
        ],
    )

    assert _lap_label(snapshot, alert("lap", "Lap 1: 1:23.")) == "L1"
    assert _lap_time_text(snapshot) == "1:23.4"
    assert _previous_lap_delta_text(snapshot) == "--"


def test_renderer_uses_compact_alert_pages_without_oil_or_water_pages():
    renderer = SecondDisplayRenderer(SecondDisplayConfig())
    snapshot = racing_snapshot(
        fuel_level=18.4,
        lap_history=[
            LapRecord(
                lap_number=3,
                lap_time_ms=92_000,
                fuel_used=6.5,
                completed_at=10.0,
            )
        ],
    )

    fuel = renderer.render_snapshot(
        snapshot,
        alert=alert("fuel", "Fuel critical. Box this lap.", "critical"),
    )
    baseline = renderer.render_snapshot(snapshot, now=0.0)
    car = renderer.render_snapshot(
        snapshot,
        alert=alert("car", "Water temperature is high.", "critical"),
        now=0.0,
    )

    assert contains_color(fuel, renderer.palette.alert)
    assert contains_color(fuel, renderer.palette.count)
    assert _fuel_level_text(snapshot) == "18"
    assert _fuel_used_text(snapshot) == "6.5"
    assert car.pixels == baseline.pixels


def test_renderer_fuel_lap_page_colors_used_fuel_against_previous_lap():
    renderer = SecondDisplayRenderer(
        SecondDisplayConfig(alert_color="0044ff"),
        width=32,
        height=32,
    )
    better_snapshot = racing_snapshot(
        fuel_level=75.0,
        lap_history=[
            LapRecord(
                lap_number=1,
                lap_time_ms=92_000,
                fuel_used=7.0,
                completed_at=10.0,
            ),
            LapRecord(
                lap_number=2,
                lap_time_ms=91_000,
                fuel_used=6.5,
                completed_at=20.0,
            ),
        ],
    )
    worse_snapshot = racing_snapshot(
        fuel_level=68.0,
        lap_history=[
            LapRecord(
                lap_number=2,
                lap_time_ms=91_000,
                fuel_used=6.5,
                completed_at=20.0,
            ),
            LapRecord(
                lap_number=3,
                lap_time_ms=90_000,
                fuel_used=7.2,
                completed_at=30.0,
            ),
        ],
    )

    better = renderer.render_snapshot(
        better_snapshot,
        alert=alert("fuel_lap", "Lap fuel usage."),
    )
    worse = renderer.render_snapshot(
        worse_snapshot,
        alert=alert("fuel_lap", "Lap fuel usage."),
    )

    assert contains_color(better, renderer.palette.delta_good)
    assert contains_color(worse, renderer.palette.delta_bad)


def test_alert_helpers_show_specific_values_instead_of_generic_alrt():
    snapshot = racing_snapshot(
        fuel_level=7.4,
        driving_style=DrivingStyleStats(
            tcs_events=142,
            asm_events=1234,
            wheelspin_events=0,
            lockup_events=0,
        ),
        lap_history=[
            LapRecord(
                lap_number=3,
                lap_time_ms=92_000,
                fuel_used=7.0,
                completed_at=10.0,
                driving_style=DrivingStyleStats(tcs_events=6, asm_events=9),
            )
        ],
    )

    assert _fuel_level_text(snapshot) == "7.4"
    assert _fuel_used_text(snapshot) == "7"
    assert _driving_alert_text(
        alert("driving", "Traction control is working often."),
        snapshot,
    ) == ("TC", "6")
    assert _driving_alert_text(
        alert("driving", "ASM is intervening often."),
        snapshot,
    ) == ("ASM", "9")
    assert _alert_category_label(alert("voice", "Command ignored.")) == "VOIC"


def test_manager_display_counts_follow_snapshot_reset():
    manager = SecondDisplayManager(SecondDisplayConfig(enabled=True))
    manager.publish(
        racing_snapshot(
            driving_style=DrivingStyleStats(
                tcs_events=12,
                asm_events=9,
                wheelspin_events=3,
                lockup_events=2,
            )
        )
    )

    assert manager.status()["display"]["counts"] == {
        "tc": 12,
        "asm": 9,
        "ws": 3,
        "lck": 2,
    }

    manager.publish(
        racing_snapshot(
            driving_style=DrivingStyleStats(
                tcs_events=0,
                asm_events=0,
                wheelspin_events=0,
                lockup_events=0,
            )
        )
    )

    assert manager.status()["display"]["counts"] == {
        "tc": 0,
        "asm": 0,
        "ws": 0,
        "lck": 0,
    }
    flags = manager._current_active_flags(manager._current_snapshot(), time.monotonic())
    assert flags == ActiveFlags()


def test_fuel_alert_used_value_handles_missing_lap_history():
    assert _fuel_used_text(racing_snapshot(fuel_level=12.3)) == "--"


def test_manager_queues_lap_and_driving_alerts_in_order():
    manager = SecondDisplayManager(
        SecondDisplayConfig(enabled=True, alert_hold_seconds=2.0)
    )
    lap_alert = alert("lap", "Lap 2: 1:38.")
    driving_alert = alert("driving", "Traction control is working often.")

    manager.publish_alert(lap_alert)
    manager.publish_alert(driving_alert)

    status = manager.status()
    assert status["alert"]["category"] == "lap"
    assert status["alert"]["queued"] == 1

    manager._active_alert_until = 0.0

    assert manager._current_alert(time.monotonic()).category == "driving"
    assert manager.status()["alert"]["category"] == "driving"


def test_service_queues_lap_fuel_and_tire_age_pages_after_each_completed_lap():
    config = AppConfig(second_display=SecondDisplayConfig(enabled=True))
    config.verbosity["fuel"] = "off"
    service = RaceEngineerService(config)

    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=1,
            total_laps=5,
            fuel_level=80.0,
            last_lap_time_ms=-1,
            best_lap_time_ms=-1,
        )
    )
    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            fuel_level=70.0,
            last_lap_time_ms=90_000,
            best_lap_time_ms=90_000,
        )
    )

    assert [alert.category for alert in alerts] == ["lap", "tires"]
    assert alerts[1].message == "Tire age 1 lap."
    assert service.second_display.status()["alert"]["category"] == "lap"
    assert service.second_display.status()["alert"]["queued"] == 2

    service.second_display._active_alert_until = 0.0

    assert service.second_display._current_alert(time.monotonic()).category == "fuel_lap"
    service.second_display._active_alert_until = 0.0

    next_alert = service.second_display._current_alert(time.monotonic())
    assert next_alert.category == "tires"
    assert next_alert.message == "Tire age 1 lap."


def test_service_skips_lap_fuel_page_when_fuel_stays_full():
    config = AppConfig(second_display=SecondDisplayConfig(enabled=True))
    config.verbosity["fuel"] = "off"
    service = RaceEngineerService(config)

    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=1,
            total_laps=5,
            fuel_level=100.0,
            last_lap_time_ms=-1,
            best_lap_time_ms=-1,
        )
    )
    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            fuel_level=100.0,
            last_lap_time_ms=90_000,
            best_lap_time_ms=90_000,
        )
    )

    assert [alert.category for alert in alerts] == ["lap", "tires"]
    assert service.snapshot.lap_history[-1].fuel_used == 0.0
    assert service.second_display.status()["alert"]["category"] == "lap"
    assert service.second_display.status()["alert"]["queued"] == 1

    service.second_display._active_alert_until = 0.0

    next_alert = service.second_display._current_alert(time.monotonic())
    assert next_alert.category == "tires"
    assert next_alert.message == "Tire age 1 lap."


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
async def test_manager_uses_separate_address_and_exposes_alert_status():
    config = SecondDisplayConfig(enabled=True, address="coach-device", update_hz=30)
    snapshot = racing_snapshot()
    fake = FakePixelClient(width=32, height=32)
    addresses: list[str] = []
    manager = SecondDisplayManager(
        config,
        snapshot_provider=lambda: snapshot,
        client_factory=lambda address: addresses.append(address) or fake,
    )

    await manager.start()
    manager.publish(snapshot)
    manager.publish_alert(alert("position", "Gained 1 place, now P3."))
    await asyncio_sleep()
    status = manager.status()
    await manager.stop()

    assert addresses == ["coach-device"]
    assert fake.connect_calls == 1
    assert fake.brightness == [60]
    assert fake.orientation == [0]
    assert fake.disconnect_calls == 1
    assert manager.renderer.width == 32
    assert manager.renderer.height == 32
    assert status["alert"]["category"] == "position"
    assert len(fake.sent) >= 2


def test_manager_ignores_car_alert_pages():
    manager = SecondDisplayManager(SecondDisplayConfig(enabled=True))

    manager.publish_alert(alert("car", "Oil temperature is high.", "critical"))

    assert manager.status()["alert"] is None


async def asyncio_sleep() -> None:
    import asyncio

    await asyncio.sleep(0.08)
