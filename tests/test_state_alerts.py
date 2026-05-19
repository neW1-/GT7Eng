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
    alerts = service.update_frame(
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

    messages = [alert.message for alert in alerts]
    assert any("Gained 1 place" in message for message in messages)
    assert any("Lap 1" in message for message in messages)

    snapshot = service.snapshot
    assert snapshot.laps_left == 2
    assert snapshot.fuel_per_lap == 10.0
    assert snapshot.fuel_laps_remaining == 2.0
    assert snapshot.fuel_margin_laps == 0.0


def test_position_loss_alert():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(current_lap=1, current_position=2))
    alerts = service.update_frame(synthetic_frame(current_lap=1, current_position=4))
    assert any("Lost 2 places" in alert.message for alert in alerts)


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
    service.update_frame(synthetic_frame(current_lap=1, current_position=4))
    service.update_frame(
        synthetic_frame(
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
