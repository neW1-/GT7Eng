import os

from gt7eng.config import load_env_file
from gt7eng.config import AppConfig


PIXEL_ENV_KEYS = [
    "GT7ENG_PIXEL_DISPLAY_ENABLED",
    "GT7ENG_PIXEL_DISPLAY_ADDRESS",
    "GT7ENG_PIXEL_DISPLAY_UPDATE_HZ",
    "GT7ENG_PIXEL_DISPLAY_REV_POSITION",
    "GT7ENG_PIXEL_DISPLAY_BRIGHTNESS",
    "GT7ENG_PIXEL_DISPLAY_DIM_BRIGHTNESS",
    "GT7ENG_PIXEL_DISPLAY_ORIENTATION",
    "GT7ENG_PIXEL_DISPLAY_SIZE_SOURCE",
    "GT7ENG_PIXEL_DISPLAY_WIDTH",
    "GT7ENG_PIXEL_DISPLAY_HEIGHT",
    "GT7ENG_PIXEL_DISPLAY_GEAR_LAYOUT",
    "GT7ENG_PIXEL_DISPLAY_REV_SCALE",
    "GT7ENG_PIXEL_DISPLAY_REV_START_PERCENT",
    "GT7ENG_PIXEL_DISPLAY_SHIFT_MODE",
    "GT7ENG_PIXEL_DISPLAY_SHIFT_PERCENT",
    "GT7ENG_PIXEL_DISPLAY_FLASH_HZ",
    "GT7ENG_PIXEL_DISPLAY_COLOR_THEME",
    "GT7ENG_PIXEL_DISPLAY_GEAR_COLOR",
    "GT7ENG_PIXEL_DISPLAY_REV_LOW_COLOR",
    "GT7ENG_PIXEL_DISPLAY_REV_MID_COLOR",
    "GT7ENG_PIXEL_DISPLAY_REV_HIGH_COLOR",
    "GT7ENG_PIXEL_DISPLAY_SHIFT_COLOR",
    "GT7ENG_PIXEL_DISPLAY_FUEL_ENABLED",
    "GT7ENG_PIXEL_DISPLAY_FUEL_SAFE_COLOR",
    "GT7ENG_PIXEL_DISPLAY_FUEL_WARN_COLOR",
    "GT7ENG_PIXEL_DISPLAY_FUEL_DANGER_COLOR",
    "GT7ENG_PIXEL_DISPLAY_FUEL_CRITICAL_COLOR",
    "GT7ENG_PIXEL_DISPLAY_RPM_MIN",
    "GT7ENG_PIXEL_DISPLAY_RPM_MAX",
]

SECOND_DISPLAY_ENV_KEYS = [
    "GT7ENG_SECOND_DISPLAY_ENABLED",
    "GT7ENG_SECOND_DISPLAY_ADDRESS",
    "GT7ENG_SECOND_DISPLAY_UPDATE_HZ",
    "GT7ENG_SECOND_DISPLAY_BRIGHTNESS",
    "GT7ENG_SECOND_DISPLAY_DIM_BRIGHTNESS",
    "GT7ENG_SECOND_DISPLAY_ORIENTATION",
    "GT7ENG_SECOND_DISPLAY_SIZE_SOURCE",
    "GT7ENG_SECOND_DISPLAY_WIDTH",
    "GT7ENG_SECOND_DISPLAY_HEIGHT",
    "GT7ENG_SECOND_DISPLAY_ALERT_HOLD_SECONDS",
    "GT7ENG_SECOND_DISPLAY_FLASH_HOLD_SECONDS",
    "GT7ENG_SECOND_DISPLAY_COLOR_THEME",
    "GT7ENG_SECOND_DISPLAY_LABEL_COLOR",
    "GT7ENG_SECOND_DISPLAY_COUNT_COLOR",
    "GT7ENG_SECOND_DISPLAY_ACTIVE_COLOR",
    "GT7ENG_SECOND_DISPLAY_ALERT_COLOR",
    "GT7ENG_SECOND_DISPLAY_DIM_COLOR",
    "GT7ENG_SECOND_DISPLAY_TIRE_NORMAL_COLOR",
    "GT7ENG_SECOND_DISPLAY_TIRE_WARM_COLOR",
    "GT7ENG_SECOND_DISPLAY_TIRE_HOT_COLOR",
]

WIND_ENV_KEYS = [
    "GT7ENG_WIND_ENABLED",
    "GT7ENG_WIND_HA_BASE_URL",
    "GT7ENG_WIND_HA_TOKEN",
    "GT7ENG_WIND_HA_ENTITY_ID",
    "GT7ENG_WIND_UPDATE_HZ",
    "GT7ENG_WIND_MAX_SPEED_KPH",
    "GT7ENG_WIND_CURVE_EXPONENT",
    "GT7ENG_WIND_DEADBAND_KPH",
    "GT7ENG_WIND_OFF_LEVEL",
    "GT7ENG_WIND_MIN_ACTIVE_LEVEL",
    "GT7ENG_WIND_MIN_LEVEL",
    "GT7ENG_WIND_MAX_LEVEL",
    "GT7ENG_WIND_SMOOTHING_SECONDS",
    "GT7ENG_WIND_HYSTERESIS_LEVELS",
    "GT7ENG_WIND_TIMEOUT_SECONDS",
]


def test_load_env_file_sets_missing_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "GT7ENG_LLM_MODEL=Qwen3.5-9B-OptiQ-4bit",
                'GT7ENG_LLM_BASE_URL="http://127.0.0.1:8000/v1"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("GT7ENG_LLM_MODEL", raising=False)
    monkeypatch.delenv("GT7ENG_LLM_BASE_URL", raising=False)

    load_env_file(env_file)

    assert os.environ["GT7ENG_LLM_MODEL"] == "Qwen3.5-9B-OptiQ-4bit"
    assert os.environ["GT7ENG_LLM_BASE_URL"] == "http://127.0.0.1:8000/v1"


def test_load_env_file_does_not_override_environment(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GT7ENG_LLM_MODEL=from-file", encoding="utf-8")
    monkeypatch.setenv("GT7ENG_LLM_MODEL", "from-shell")

    load_env_file(env_file)

    assert os.environ["GT7ENG_LLM_MODEL"] == "from-shell"


def test_llm_disable_thinking_env(monkeypatch):
    monkeypatch.setenv("GT7ENG_LLM_DISABLE_THINKING", "true")

    config = AppConfig.from_env()

    assert config.llm.disable_thinking is True


def test_voice_mode_env_accepts_quiet_driver_ai(monkeypatch):
    monkeypatch.setenv("GT7ENG_VOICE_MODE", "quiet_driver_ai")

    config = AppConfig.from_env()

    assert config.voice_mode == "quiet_driver_ai"


def test_unknown_voice_mode_env_falls_back_to_quiet_driver(monkeypatch):
    monkeypatch.setenv("GT7ENG_VOICE_MODE", "wake_word")

    config = AppConfig.from_env()

    assert config.voice_mode == "quiet_driver"


def test_engineer_muted_and_verbosity_overrides_from_env(monkeypatch):
    monkeypatch.setenv("GT7ENG_PRESET", "endurance")
    monkeypatch.setenv("GT7ENG_ENGINEER_MUTED", "true")
    monkeypatch.setenv("GT7ENG_VERBOSITY_FUEL", "off")
    monkeypatch.setenv("GT7ENG_VERBOSITY_LAP", "detailed")

    config = AppConfig.from_env()

    assert config.engineer_muted is True
    assert config.verbosity["fuel"] == "off"
    assert config.verbosity["lap"] == "detailed"


def test_pixel_display_env_defaults(monkeypatch):
    for key in PIXEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    config = AppConfig.from_env()

    assert config.pixel_display.enabled is False
    assert config.pixel_display.address == ""
    assert config.pixel_display.update_hz == 10.0
    assert config.pixel_display.rev_position == "bottom"
    assert config.pixel_display.width == 64
    assert config.pixel_display.height == 64
    assert config.pixel_display.size_source == "auto"
    assert config.pixel_display.gear_layout == "current"
    assert config.pixel_display.rev_scale == "wide"
    assert config.pixel_display.rev_start_percent == 0.60
    assert config.pixel_display.shift_mode == "rev_limit"
    assert config.pixel_display.color_theme == "simdt_blue"
    assert config.pixel_display.fuel_enabled is False
    assert config.pixel_display.fuel_safe_color == ""
    assert config.pixel_display.fuel_warn_color == ""
    assert config.pixel_display.fuel_danger_color == ""
    assert config.pixel_display.fuel_critical_color == ""


def test_pixel_display_env_accepts_theme_and_custom_colors(monkeypatch):
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_ENABLED", "true")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_ADDRESS", "30:E1:AF:BD:5F:D0")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_COLOR_THEME", "warm_amber")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_REV_POSITION", "top")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_WIDTH", "64")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_HEIGHT", "64")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_SIZE_SOURCE", "config")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_GEAR_LAYOUT", "current_suggested")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_REV_SCALE", "alert_window")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_REV_START_PERCENT", "0.55")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_SHIFT_MODE", "percent")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_GEAR_COLOR", "#ff8800")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_REV_LOW_COLOR", "not-a-color")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_FUEL_ENABLED", "true")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_FUEL_SAFE_COLOR", "#00ff00")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_FUEL_WARN_COLOR", "ffee00")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_FUEL_DANGER_COLOR", "#ff6600")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_FUEL_CRITICAL_COLOR", "f00000")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_RPM_MIN", "6000")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_RPM_MAX", "8000")

    config = AppConfig.from_env()

    assert config.pixel_display.enabled is True
    assert config.pixel_display.address == "30:E1:AF:BD:5F:D0"
    assert config.pixel_display.color_theme == "warm_amber"
    assert config.pixel_display.rev_position == "top"
    assert config.pixel_display.width == 64
    assert config.pixel_display.height == 64
    assert config.pixel_display.size_source == "config"
    assert config.pixel_display.gear_layout == "current_suggested"
    assert config.pixel_display.rev_scale == "alert_window"
    assert config.pixel_display.rev_start_percent == 0.55
    assert config.pixel_display.shift_mode == "percent"
    assert config.pixel_display.gear_color == "ff8800"
    assert config.pixel_display.rev_low_color == ""
    assert config.pixel_display.fuel_enabled is True
    assert config.pixel_display.fuel_safe_color == "00ff00"
    assert config.pixel_display.fuel_warn_color == "ffee00"
    assert config.pixel_display.fuel_danger_color == "ff6600"
    assert config.pixel_display.fuel_critical_color == "f00000"
    assert config.pixel_display.rpm_min == 6000
    assert config.pixel_display.rpm_max == 8000


def test_pixel_display_invalid_env_falls_back(monkeypatch):
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_UPDATE_HZ", "999")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_ORIENTATION", "8")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_WIDTH", "2")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_HEIGHT", "9999")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_SIZE_SOURCE", "manual")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_SHIFT_PERCENT", "2")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_GEAR_LAYOUT", "combined")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_REV_SCALE", "narrow")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_REV_START_PERCENT", "1")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_SHIFT_MODE", "suggested")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_COLOR_THEME", "purple")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_REV_POSITION", "side")
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_FUEL_SAFE_COLOR", "blue")

    config = AppConfig.from_env()

    assert config.pixel_display.update_hz == 10.0
    assert config.pixel_display.orientation == 0
    assert config.pixel_display.width == 64
    assert config.pixel_display.height == 64
    assert config.pixel_display.size_source == "auto"
    assert config.pixel_display.shift_percent == 0.96
    assert config.pixel_display.gear_layout == "current"
    assert config.pixel_display.rev_scale == "wide"
    assert config.pixel_display.rev_start_percent == 0.60
    assert config.pixel_display.shift_mode == "rev_limit"
    assert config.pixel_display.color_theme == "simdt_blue"
    assert config.pixel_display.rev_position == "bottom"
    assert config.pixel_display.fuel_safe_color == ""


def test_second_display_env_defaults(monkeypatch):
    for key in SECOND_DISPLAY_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    config = AppConfig.from_env()

    assert config.second_display.enabled is False
    assert config.second_display.address == ""
    assert config.second_display.update_hz == 10.0
    assert config.second_display.width == 64
    assert config.second_display.height == 64
    assert config.second_display.size_source == "auto"
    assert config.second_display.alert_hold_seconds == 4.0
    assert config.second_display.flash_hold_seconds == 1.5
    assert config.second_display.color_theme == "simdt_blue"
    assert config.second_display.active_color == ""
    assert config.second_display.tire_hot_color == ""


def test_second_display_env_accepts_overrides(monkeypatch):
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_COLOR_THEME", "warm_amber")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_ENABLED", "true")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_ADDRESS", "coach-device")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_UPDATE_HZ", "12")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_BRIGHTNESS", "41")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_DIM_BRIGHTNESS", "9")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_ORIENTATION", "2")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_WIDTH", "32")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_HEIGHT", "32")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_SIZE_SOURCE", "config")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_ALERT_HOLD_SECONDS", "3.5")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_FLASH_HOLD_SECONDS", "1.2")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_COLOR_THEME", "warm_amber")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_ACTIVE_COLOR", "#ffee00")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_TIRE_HOT_COLOR", "ff0000")

    config = AppConfig.from_env()

    assert config.second_display.enabled is True
    assert config.second_display.address == "coach-device"
    assert config.second_display.update_hz == 12.0
    assert config.second_display.brightness == 41
    assert config.second_display.dim_brightness == 9
    assert config.second_display.orientation == 2
    assert config.second_display.width == 32
    assert config.second_display.height == 32
    assert config.second_display.size_source == "config"
    assert config.second_display.alert_hold_seconds == 3.5
    assert config.second_display.flash_hold_seconds == 1.2
    assert config.second_display.color_theme == "warm_amber"
    assert config.second_display.active_color == "ffee00"
    assert config.second_display.tire_hot_color == "ff0000"


def test_second_display_theme_follows_primary_theme(monkeypatch):
    monkeypatch.setenv("GT7ENG_PIXEL_DISPLAY_COLOR_THEME", "warm_amber")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_COLOR_THEME", "night_vision")

    config = AppConfig.from_env()

    assert config.pixel_display.color_theme == "warm_amber"
    assert config.second_display.color_theme == "warm_amber"


def test_second_display_invalid_env_falls_back(monkeypatch):
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_UPDATE_HZ", "999")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_BRIGHTNESS", "101")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_DIM_BRIGHTNESS", "-1")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_ORIENTATION", "8")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_WIDTH", "2")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_HEIGHT", "9999")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_SIZE_SOURCE", "manual")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_ALERT_HOLD_SECONDS", "99")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_FLASH_HOLD_SECONDS", "0")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_COLOR_THEME", "purple")
    monkeypatch.setenv("GT7ENG_SECOND_DISPLAY_ACTIVE_COLOR", "yellow")

    config = AppConfig.from_env()

    assert config.second_display.update_hz == 10.0
    assert config.second_display.brightness == 60
    assert config.second_display.dim_brightness == 12
    assert config.second_display.orientation == 0
    assert config.second_display.width == 64
    assert config.second_display.height == 64
    assert config.second_display.size_source == "auto"
    assert config.second_display.alert_hold_seconds == 4.0
    assert config.second_display.flash_hold_seconds == 1.5
    assert config.second_display.color_theme == "simdt_blue"
    assert config.second_display.active_color == ""


def test_home_assistant_wind_env_defaults(monkeypatch):
    for key in WIND_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    config = AppConfig.from_env()

    assert config.wind.enabled is False
    assert config.wind.ha_base_url == ""
    assert config.wind.ha_token == ""
    assert config.wind.ha_entity_id == "number.zhimi_cpa4_cee4_favorite_level"
    assert config.wind.update_hz == 2.0
    assert config.wind.max_speed_kph == 280.0
    assert config.wind.curve_exponent == 1.6
    assert config.wind.deadband_kph == 10.0
    assert config.wind.off_level == 0
    assert config.wind.min_active_level == 0
    assert config.wind.max_level == 14
    assert config.wind.smoothing_seconds == 1.0
    assert config.wind.hysteresis_levels == 1
    assert config.wind.timeout_seconds == 2.0


def test_home_assistant_wind_env_accepts_overrides(monkeypatch):
    monkeypatch.setenv("GT7ENG_WIND_ENABLED", "true")
    monkeypatch.setenv("GT7ENG_WIND_HA_BASE_URL", "http://ha.local:8123/")
    monkeypatch.setenv("GT7ENG_WIND_HA_TOKEN", "secret-token")
    monkeypatch.setenv("GT7ENG_WIND_HA_ENTITY_ID", "number.rig_fan_level")
    monkeypatch.setenv("GT7ENG_WIND_UPDATE_HZ", "1")
    monkeypatch.setenv("GT7ENG_WIND_MAX_SPEED_KPH", "320")
    monkeypatch.setenv("GT7ENG_WIND_CURVE_EXPONENT", "2")
    monkeypatch.setenv("GT7ENG_WIND_DEADBAND_KPH", "5")
    monkeypatch.setenv("GT7ENG_WIND_OFF_LEVEL", "0")
    monkeypatch.setenv("GT7ENG_WIND_MIN_ACTIVE_LEVEL", "2")
    monkeypatch.setenv("GT7ENG_WIND_MAX_LEVEL", "10")
    monkeypatch.setenv("GT7ENG_WIND_SMOOTHING_SECONDS", "0.5")
    monkeypatch.setenv("GT7ENG_WIND_HYSTERESIS_LEVELS", "2")
    monkeypatch.setenv("GT7ENG_WIND_TIMEOUT_SECONDS", "3")

    config = AppConfig.from_env()

    assert config.wind.enabled is True
    assert config.wind.ha_base_url == "http://ha.local:8123"
    assert config.wind.ha_token == "secret-token"
    assert config.wind.ha_entity_id == "number.rig_fan_level"
    assert config.wind.update_hz == 1.0
    assert config.wind.max_speed_kph == 320.0
    assert config.wind.curve_exponent == 2.0
    assert config.wind.deadband_kph == 5.0
    assert config.wind.off_level == 0
    assert config.wind.min_active_level == 2
    assert config.wind.max_level == 10
    assert config.wind.smoothing_seconds == 0.5
    assert config.wind.hysteresis_levels == 2
    assert config.wind.timeout_seconds == 3.0


def test_home_assistant_wind_invalid_env_falls_back(monkeypatch):
    monkeypatch.setenv("GT7ENG_WIND_UPDATE_HZ", "99")
    monkeypatch.setenv("GT7ENG_WIND_MAX_SPEED_KPH", "0")
    monkeypatch.setenv("GT7ENG_WIND_CURVE_EXPONENT", "9")
    monkeypatch.setenv("GT7ENG_WIND_DEADBAND_KPH", "999")
    monkeypatch.setenv("GT7ENG_WIND_OFF_LEVEL", "999")
    monkeypatch.setenv("GT7ENG_WIND_MIN_ACTIVE_LEVEL", "-1")
    monkeypatch.setenv("GT7ENG_WIND_MIN_LEVEL", "-1")
    monkeypatch.setenv("GT7ENG_WIND_MAX_LEVEL", "999")
    monkeypatch.setenv("GT7ENG_WIND_SMOOTHING_SECONDS", "-1")
    monkeypatch.setenv("GT7ENG_WIND_HYSTERESIS_LEVELS", "-1")
    monkeypatch.setenv("GT7ENG_WIND_TIMEOUT_SECONDS", "99")

    config = AppConfig.from_env()

    assert config.wind.update_hz == 2.0
    assert config.wind.max_speed_kph == 280.0
    assert config.wind.curve_exponent == 1.6
    assert config.wind.deadband_kph == 10.0
    assert config.wind.off_level == 0
    assert config.wind.min_active_level == 0
    assert config.wind.max_level == 14
    assert config.wind.smoothing_seconds == 1.0
    assert config.wind.hysteresis_levels == 1
    assert config.wind.timeout_seconds == 2.0


def test_home_assistant_wind_legacy_min_level_sets_off_and_active(monkeypatch):
    for key in WIND_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GT7ENG_WIND_MIN_LEVEL", "3")

    config = AppConfig.from_env()

    assert config.wind.off_level == 3
    assert config.wind.min_active_level == 3


def test_home_assistant_wind_new_level_keys_override_legacy_min_level(monkeypatch):
    for key in WIND_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GT7ENG_WIND_OFF_LEVEL", "0")
    monkeypatch.setenv("GT7ENG_WIND_MIN_ACTIVE_LEVEL", "2")
    monkeypatch.setenv("GT7ENG_WIND_MIN_LEVEL", "3")

    config = AppConfig.from_env()

    assert config.wind.off_level == 0
    assert config.wind.min_active_level == 2
