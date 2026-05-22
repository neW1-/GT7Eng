from gt7eng.config import AppConfig
from gt7eng.service import RaceEngineerService
from gt7eng.telemetry import synthetic_frame


def test_lap_position_and_fuel_projection_alerts():
    service = RaceEngineerService(AppConfig())

    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=1,
            total_laps=3,
            current_position=4,
            fuel_level=30.0,
            last_lap_time_ms=-1,
            best_lap_time_ms=-1,
        )
    )
    lap_alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=3,
            current_position=3,
            fuel_level=20.0,
            last_lap_time_ms=98_500,
            best_lap_time_ms=98_500,
        )
    )
    position_alerts = service.update_frame(
        synthetic_frame(
            timestamp=3.6,
            current_lap=2,
            total_laps=3,
            current_position=3,
            fuel_level=20.0,
            last_lap_time_ms=98_500,
            best_lap_time_ms=98_500,
        )
    )

    messages = [alert.message for alert in [*lap_alerts, *position_alerts]]
    assert any("Gained 1 place" in message for message in messages)
    assert any("Lap 1" in message for message in messages)

    snapshot = service.snapshot
    assert snapshot.laps_left == 2
    assert snapshot.fuel_per_lap == 10.0
    assert snapshot.fuel_laps_remaining == 2.0
    assert snapshot.fuel_margin_laps == 0.0
    assert snapshot.fuel_unit == "percent"
    assert snapshot.to_dict()["fuel_level_percent"] == 20.0
    assert snapshot.to_dict()["fuel_per_lap_percent"] == 10.0


def test_position_loss_alert():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, current_position=2))
    service.update_frame(synthetic_frame(timestamp=1.1, current_lap=1, current_position=4))
    alerts = service.update_frame(
        synthetic_frame(timestamp=2.7, current_lap=1, current_position=4)
    )
    assert any("Lost 2 places" in alert.message for alert in alerts)


def test_rapid_position_changes_are_coalesced():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, current_position=13))
    first = service.update_frame(
        synthetic_frame(timestamp=1.1, current_lap=1, current_position=12)
    )
    second = service.update_frame(
        synthetic_frame(timestamp=1.6, current_lap=1, current_position=11)
    )
    third = service.update_frame(
        synthetic_frame(timestamp=2.0, current_lap=1, current_position=10)
    )
    final = service.update_frame(
        synthetic_frame(timestamp=3.6, current_lap=1, current_position=10)
    )

    assert not [alert for alert in [*first, *second, *third] if alert.category == "position"]
    assert [alert.message for alert in final if alert.category == "position"] == [
        "Gained 3 places, now P10."
    ]


def test_fuel_threshold_uses_level_as_percentage_not_capacity_ratio():
    service = RaceEngineerService(AppConfig())
    alerts = service.update_frame(synthetic_frame(fuel_level=60.0, fuel_capacity=1000.0))
    assert not any("Fuel below" in alert.message for alert in alerts)
    assert service.snapshot.fuel_level == 60.0
    assert service.snapshot.fuel_capacity == 100.0


def test_tire_and_car_health_alerts():
    service = RaceEngineerService(AppConfig())
    frame = synthetic_frame(
        tire_temps={"fl": 116.0, "fr": 100.0, "rl": 101.0, "rr": 100.0},
        water_temp=112.0,
        oil_temp=132.0,
    )
    alerts = service.update_frame(frame)
    categories = {alert.category for alert in alerts}
    assert "tires" in categories
    assert "car" in categories


def test_spoken_alerts_queue_voice_jobs_once():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, current_position=4))
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            current_position=3,
            fuel_level=20.0,
            last_lap_time_ms=98_500,
            best_lap_time_ms=98_500,
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=3.6,
            current_lap=2,
            current_position=3,
            fuel_level=20.0,
            last_lap_time_ms=98_500,
            best_lap_time_ms=98_500,
        )
    )

    jobs = service.next_voice_jobs(limit=10)
    assert any("P3" in job["text"] for job in jobs)
    assert service.next_voice_jobs(limit=10) == []


def test_menu_phase_suppresses_race_alerts():
    service = RaceEngineerService(AppConfig())
    alerts = service.update_frame(
        synthetic_frame(cars_on_track=False, current_lap=0, current_position=3)
    )
    assert alerts == []
    assert service.snapshot.session_phase == "menu"


def test_tire_wear_and_incident_alerts():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            speed_kph=110,
            tire_radius={"fl": 0.33, "fr": 0.33, "rl": 0.33, "rr": 0.33},
            wheel_rps={"fl": 20, "fr": 20, "rl": 20, "rr": 20},
        )
    )
    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            speed_kph=30,
            tire_radius={"fl": 0.26, "fr": 0.33, "rl": 0.33, "rr": 0.33},
            wheel_rps={"fl": 4, "fr": 4, "rl": 4, "rr": 4},
        )
    )

    messages = [alert.message for alert in alerts]
    assert any("Estimated tire wear" in message for message in messages)
    assert any("Possible impact" in message for message in messages)


def test_practice_driving_style_alerts_on_lap_end():
    config = AppConfig(preset="practice")
    config.set_preset("practice")
    service = RaceEngineerService(config)
    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=1,
            throttle=90,
            wheel_rps={"fl": 20, "fr": 20, "rl": 26, "rr": 26},
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=1.5,
            current_lap=1,
            throttle=0,
            wheel_rps={"fl": 20, "fr": 20, "rl": 20, "rr": 20},
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=1,
            throttle=90,
            wheel_rps={"fl": 20, "fr": 20, "rl": 26, "rr": 26},
        )
    )
    alerts = service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=2,
            last_lap_time_ms=98_000,
            best_lap_time_ms=98_000,
        )
    )

    assert any("Wheelspin" in alert.message for alert in alerts)
