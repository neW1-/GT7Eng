from gt7eng.config import AppConfig
from gt7eng.llm import IntentRepair
from gt7eng.service import RaceEngineerService
from gt7eng.telemetry import synthetic_frame


def test_quiet_driver_accepts_strict_fuel_command():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(fuel_level=42.0))
    result = service.handle_command("how is my fuel")
    assert result["handled"] is True
    assert result["intent"] == "fuel_status"
    assert "42.0" in result["response"]
    assert "percent" in result["response"]
    assert "liter" not in result["response"].lower()


def test_discord_response_takes_priority_over_connection_alert():
    service = RaceEngineerService(AppConfig())
    service.snapshot
    service.update_frame(synthetic_frame(fuel_level=80.0))

    result = service.handle_transcript("how is my fuel", "discord")
    jobs = service.next_voice_jobs(limit=10)

    assert result["intent"] == "fuel_status"
    assert jobs[0]["text"] == result["response"]
    assert all(job["category"] != "system" for job in jobs)


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


def test_timed_race_lap_and_time_commands():
    config = AppConfig(race_duration_minutes=30)
    service = RaceEngineerService(config)
    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=1,
            total_laps=0,
            time_of_day_ms=18 * 60 * 60_000,
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=301.0,
            current_lap=1,
            total_laps=0,
            time_of_day_ms=18 * 60 * 60_000 + 5 * 60_000,
        )
    )

    laps = service.handle_command("how many laps")
    assert laps["intent"] == "laps_left"
    assert "Lap 1" in laps["response"]
    assert "25 minutes remaining" in laps["response"]
    assert "of 0" not in laps["response"]

    time_left = service.handle_command("how much time left")
    assert time_left["intent"] == "time_remaining"
    assert "25 minutes remaining" in time_left["response"]

    update = service.handle_command("give me an update")
    assert "lap 1" in update["response"]
    assert "25 minutes remaining" in update["response"]
    assert "of 0" not in update["response"]


def test_timed_race_lap_zero_uses_timed_race_phrase():
    service = RaceEngineerService(AppConfig(race_duration_minutes=40))
    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=0,
            total_laps=0,
            speed_kph=80.0,
            cars_on_track=True,
        )
    )

    laps = service.handle_command("how many laps")
    assert laps["intent"] == "laps_left"
    assert "Timed race" in laps["response"]
    assert "Lap 0" not in laps["response"]
    assert "40 minutes remaining" in laps["response"]


def test_race_duration_can_be_set_by_command():
    service = RaceEngineerService(AppConfig())
    result = service.handle_command("set race duration to 30 minutes")
    assert result["intent"] == "set_race_duration"
    assert service.config.race_duration_minutes == 30
    assert "30 minutes" in result["response"]


def test_quiet_driver_unknown_transcript_does_not_call_llm():
    service = RaceEngineerService(AppConfig())

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for unknown quiet-driver speech")

    service.llm.ask = fail_llm
    result = service.handle_transcript("tell me something interesting", "discord")
    assert result["ignored"] is True
    assert result["intent"] == "unknown_quiet_driver"


def test_quiet_driver_ai_unknown_transcript_can_fall_back_to_llm():
    config = AppConfig(voice_mode="quiet_driver_ai")
    service = RaceEngineerService(config)
    service.llm.ask = lambda *_args, **_kwargs: "Fuel burn is stable."

    result = service.handle_transcript("summarize my stint", "discord", confidence=0.7)

    assert result["handled"] is True
    assert result["intent"] == "llm_question"
    assert "stable" in result["response"]


def test_quiet_driver_ai_low_confidence_unknown_transcript_is_ignored():
    config = AppConfig(voice_mode="quiet_driver_ai")
    config.stt.min_confidence = 0.8
    service = RaceEngineerService(config)
    service.llm.ask = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("Low-confidence unknown speech should not use free-form LLM")
    )

    result = service.handle_transcript("summarize my stint", "discord", confidence=0.2)

    assert result["ignored"] is True
    assert result["intent"] == "low_confidence"


def test_quiet_driver_unknown_transcript_can_use_llm_intent_repair():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(current_position=7))
    service.llm.repair_intent = lambda *_args, **_kwargs: IntentRepair(
        "position", "what position am I", 0.84
    )
    service.llm.ask = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("Intent repair should not use free-form LLM answers")
    )

    result = service.handle_transcript("what spot did i get", "discord", confidence=0.7)

    assert result["handled"] is True
    assert result["intent"] == "position"
    assert result["repair"]["intent"] == "position"
    assert "P7" in result["response"]
    assert service.status()["voice"]["last"]["repair"]["intent"] == "position"


def test_low_confidence_llm_intent_repair_is_ignored():
    service = RaceEngineerService(AppConfig())
    service.llm.repair_intent = lambda *_args, **_kwargs: IntentRepair(
        "position", "what position am I", 0.2
    )

    result = service.handle_transcript("what spot did i get", "discord", confidence=0.7)

    assert result["ignored"] is True
    assert result["intent"] == "unknown_quiet_driver"


def test_fuel_burn_rate_question_uses_deterministic_percentage():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, fuel_level=80.0))
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            fuel_level=72.0,
            last_lap_time_ms=90_000,
        )
    )

    result = service.handle_command("what's my fuel burn rate")

    assert result["handled"] is True
    assert result["intent"] == "fuel_burn_rate"
    assert result["response"] == "Fuel burn is 8.0 percent per lap."


def test_last_lap_fuel_question_uses_deterministic_percentage():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, fuel_level=80.0))
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            fuel_level=72.0,
            last_lap_time_ms=90_000,
        )
    )

    result = service.handle_command("how much fuel did I use last lap")

    assert result["handled"] is True
    assert result["intent"] == "last_lap_fuel"
    assert result["response"] == "Last lap used 8.0 percent fuel."


def test_fuel_burn_question_needs_completed_lap():
    service = RaceEngineerService(AppConfig())

    result = service.handle_command("what is my fuel burn rate")

    assert result["handled"] is True
    assert result["intent"] == "fuel_burn_rate"
    assert result["response"] == "Need one completed lap for fuel burn."


def test_wake_phrase_unknown_transcript_can_fall_back_to_llm():
    config = AppConfig(voice_mode="wake_phrase", wake_phrase="engineer")
    service = RaceEngineerService(config)
    service.llm.ask = lambda *_args, **_kwargs: "Only current race state is available."

    result = service.handle_transcript("engineer summarize the stint", "discord")

    assert result["handled"] is True
    assert result["intent"] == "llm_question"
    assert "race state" in result["response"]


def test_low_confidence_known_command_is_handled():
    config = AppConfig()
    config.stt.min_confidence = 0.8
    service = RaceEngineerService(config)
    result = service.handle_transcript("how is my fuel", "discord", confidence=0.2)
    assert result["handled"] is True
    assert result["intent"] == "fuel_status"


def test_low_confidence_unknown_transcript_is_ignored():
    config = AppConfig()
    config.stt.min_confidence = 0.8
    service = RaceEngineerService(config)
    result = service.handle_transcript("something random", "discord", confidence=0.2)
    assert result["ignored"] is True
    assert result["intent"] == "low_confidence"


def test_low_confidence_unknown_transcript_can_use_llm_intent_repair():
    config = AppConfig()
    config.stt.min_confidence = 0.8
    service = RaceEngineerService(config)
    service.update_frame(synthetic_frame(current_position=4))
    service.llm.repair_intent = lambda *_args, **_kwargs: IntentRepair(
        "position", "what position am I", 0.9
    )

    result = service.handle_transcript("what spot", "discord", confidence=0.2)

    assert result["handled"] is True
    assert result["intent"] == "position"
    assert result["repair"]["intent"] == "position"
    assert "P4" in result["response"]
