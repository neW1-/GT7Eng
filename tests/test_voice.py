from gt7eng.config import AppConfig
from gt7eng.service import RaceEngineerService
from gt7eng.telemetry import synthetic_frame


def test_quiet_driver_accepts_strict_fuel_command():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(fuel_level=42.0))
    result = service.handle_command("how is my fuel")
    assert result["handled"] is True
    assert result["intent"] == "fuel_status"
    assert "42.0" in result["response"]


def test_wake_phrase_ignores_without_phrase():
    config = AppConfig(voice_mode="wake_phrase", wake_phrase="engineer")
    service = RaceEngineerService(config)
    service.update_frame(synthetic_frame(fuel_level=42.0))
    result = service.handle_command("how is my fuel")
    assert result["ignored"] is True


def test_wake_phrase_handles_with_phrase():
    config = AppConfig(voice_mode="wake_phrase", wake_phrase="engineer")
    service = RaceEngineerService(config)
    service.update_frame(synthetic_frame(current_position=5))
    result = service.handle_command("engineer what position am I")
    assert result["intent"] == "position"
    assert "P5" in result["response"]
