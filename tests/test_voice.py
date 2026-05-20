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


def test_quiet_driver_unknown_transcript_does_not_call_llm():
    service = RaceEngineerService(AppConfig())

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for unknown quiet-driver speech")

    service.llm.ask = fail_llm
    result = service.handle_transcript("tell me something interesting", "discord")
    assert result["ignored"] is True
    assert result["intent"] == "unknown_quiet_driver"


def test_wake_phrase_unknown_transcript_can_fall_back_to_llm():
    config = AppConfig(voice_mode="wake_phrase", wake_phrase="engineer")
    service = RaceEngineerService(config)
    service.llm.ask = lambda *_args, **_kwargs: "Only current race state is available."

    result = service.handle_transcript("engineer summarize the stint", "discord")

    assert result["handled"] is True
    assert result["intent"] == "llm_question"
    assert "race state" in result["response"]


def test_low_confidence_transcript_is_ignored():
    config = AppConfig()
    config.stt.min_confidence = 0.8
    service = RaceEngineerService(config)
    result = service.handle_transcript("how is my fuel", "discord", confidence=0.2)
    assert result["ignored"] is True
    assert result["intent"] == "low_confidence"
