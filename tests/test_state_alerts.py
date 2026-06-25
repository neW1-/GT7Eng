from gt7eng.config import AppConfig
from gt7eng.alerts import AlertManager
from gt7eng.models import RaceSnapshot
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

    snapshot = service.state.snapshot
    assert snapshot.laps_left == 2
    assert snapshot.fuel_per_lap == 10.0
    assert snapshot.fuel_laps_remaining == 2.0
    assert snapshot.fuel_margin_laps == 0.0
    assert snapshot.fuel_unit == "percent"
    assert snapshot.best_lap_number == 1
    assert snapshot.to_dict()["best_lap_number"] == 1
    assert snapshot.to_dict()["fuel_level_percent"] == 20.0
    assert snapshot.to_dict()["fuel_per_lap_percent"] == 10.0


def test_fuel_short_does_not_force_box_this_lap_when_stint_has_range():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=1,
            total_laps=10,
            fuel_level=54.0,
            last_lap_time_ms=-1,
            best_lap_time_ms=-1,
        )
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=10,
            fuel_level=44.0,
            last_lap_time_ms=80_000,
            best_lap_time_ms=80_000,
        )
    )

    snapshot = service.snapshot
    assert round(snapshot.fuel_laps_remaining or 0, 1) == 4.4
    assert round(snapshot.fuel_margin_laps or 0, 1) == -4.6
    assert snapshot.pit_recommendation == "Pit required. Box within 3 laps."
    assert "Box this lap" not in snapshot.pit_recommendation
    assert any(
        alert.category == "fuel" and alert.message == "Pit required. Box within 3 laps."
        for alert in alerts
    )


def test_connection_alerts_do_not_spam_voice_on_flap():
    manager = AlertManager(AppConfig())

    assert manager.connection_alerts(RaceSnapshot(connected=True)) == []
    stale = manager.connection_alerts(RaceSnapshot(connected=False))
    connected = manager.connection_alerts(RaceSnapshot(connected=True))
    repeated_stale = manager.connection_alerts(RaceSnapshot(connected=False))

    assert len(stale) == 1
    assert stale[0].speak is True
    assert len(connected) == 1
    assert connected[0].message == "Telemetry connected."
    assert connected[0].speak is False
    assert repeated_stale == []


def test_fuel_low_boxes_this_lap_only_when_stint_is_almost_empty():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(timestamp=1.0, current_lap=1, total_laps=5, fuel_level=18.0)
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            fuel_level=8.0,
            last_lap_time_ms=80_000,
            best_lap_time_ms=80_000,
        )
    )

    assert round(service.snapshot.fuel_laps_remaining or 0, 1) == 0.8
    assert service.snapshot.pit_recommendation == "Box this lap."
    assert any(alert.message == "Fuel critical. Box this lap." for alert in alerts)


def test_fuel_can_finish_takes_precedence_over_short_stint_warning():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(timestamp=1.0, current_lap=1, total_laps=2, fuel_level=26.0)
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=2,
            fuel_level=16.0,
            last_lap_time_ms=80_000,
            best_lap_time_ms=80_000,
        )
    )

    assert round(service.snapshot.fuel_laps_remaining or 0, 1) == 1.6
    assert round(service.snapshot.fuel_margin_laps or 0, 1) == 0.6
    assert service.snapshot.pit_recommendation == "Fuel to the end is safe."
    assert not any("Box within 1 lap" in alert.message for alert in alerts)


def test_fuel_short_under_two_laps_warns_box_within_one_lap():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(timestamp=1.0, current_lap=1, total_laps=5, fuel_level=26.0)
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            fuel_level=16.0,
            last_lap_time_ms=80_000,
            best_lap_time_ms=80_000,
        )
    )

    assert round(service.snapshot.fuel_laps_remaining or 0, 1) == 1.6
    assert round(service.snapshot.fuel_margin_laps or 0, 1) == -2.4
    assert service.snapshot.pit_recommendation == "Box within 1 lap."
    assert any(alert.message == "Fuel low. Box within 1 lap." for alert in alerts)


def test_lap_rewind_resets_stale_fuel_history_before_new_race():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(timestamp=1.0, current_lap=1, total_laps=5, fuel_level=100.0)
    )
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            fuel_level=5.0,
            last_lap_time_ms=80_000,
            best_lap_time_ms=80_000,
        )
    )
    assert round(service.snapshot.fuel_per_lap or 0, 1) == 95.0

    service.update_frame(
        synthetic_frame(timestamp=10.0, current_lap=1, total_laps=5, fuel_level=100.0)
    )
    alerts = service.update_frame(
        synthetic_frame(
            timestamp=11.0,
            current_lap=2,
            total_laps=5,
            fuel_level=90.0,
            last_lap_time_ms=80_000,
            best_lap_time_ms=80_000,
        )
    )

    assert service.snapshot.fuel_sample_count == 1
    assert round(service.snapshot.fuel_per_lap or 0, 1) == 10.0
    assert round(service.snapshot.fuel_laps_remaining or 0, 1) == 9.0
    assert service.snapshot.pit_recommendation == "Fuel to the end is safe."
    assert not any("Box this lap" in alert.message for alert in alerts)


def test_high_fuel_single_unstable_projection_does_not_box_this_lap():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(timestamp=1.0, current_lap=1, total_laps=5, fuel_level=100.0)
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            fuel_level=70.0,
            last_lap_time_ms=80_000,
            best_lap_time_ms=80_000,
        )
    )

    assert service.snapshot.fuel_sample_count == 1
    assert round(service.snapshot.fuel_laps_remaining or 0, 1) == 2.3
    assert service.snapshot.pit_recommendation == "Pit required. Box within 1 lap."
    assert not any("Box this lap" in alert.message for alert in alerts)


def test_first_lap_alert_uses_spoken_time_without_best_delta():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=1,
            total_laps=5,
            last_lap_time_ms=-1,
            best_lap_time_ms=-1,
        )
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            last_lap_time_ms=82_999,
            best_lap_time_ms=82_999,
        )
    )

    lap_message = next(alert.message for alert in alerts if alert.category == "lap")
    assert lap_message.startswith("Lap 1: 1:23.")
    assert "to best" not in lap_message
    assert service.snapshot.to_dict()["last_lap_time"] == "1:22.999"


def test_slower_lap_alert_uses_rounded_spoken_delta_to_best():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, total_laps=5))
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            last_lap_time_ms=82_999,
            best_lap_time_ms=82_999,
        )
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=3,
            total_laps=5,
            last_lap_time_ms=84_100,
            best_lap_time_ms=82_999,
        )
    )

    lap_message = next(alert.message for alert in alerts if alert.category == "lap")
    assert lap_message.startswith("Lap 2: 1:24.")
    assert "About 1 second to best." in lap_message


def test_lap_alert_uses_lap_history_when_raw_best_is_missing_mid_lap():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, total_laps=5))
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            last_lap_time_ms=82_999,
            best_lap_time_ms=82_999,
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=2.5,
            current_lap=2,
            total_laps=5,
            last_lap_time_ms=82_999,
            best_lap_time_ms=-1,
        )
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=3,
            total_laps=5,
            last_lap_time_ms=84_100,
            best_lap_time_ms=84_100,
        )
    )

    lap_message = next(alert.message for alert in alerts if alert.category == "lap")
    assert lap_message.startswith("Lap 2: 1:24.")
    assert "About 1 second to best." in lap_message


def test_snapshot_best_lap_prefers_completed_lap_history():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, total_laps=5))
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            last_lap_time_ms=82_999,
            best_lap_time_ms=82_999,
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=3,
            total_laps=5,
            last_lap_time_ms=84_100,
            best_lap_time_ms=84_100,
        )
    )

    assert service.snapshot.best_lap_time_ms == 82_999
    assert service.snapshot.best_lap_number == 1
    assert service.snapshot.to_dict()["best_lap_time"] == "1:22.999"


def test_new_best_lap_alert_announces_improvement():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, total_laps=5))
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            last_lap_time_ms=82_999,
            best_lap_time_ms=82_999,
        )
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=3,
            total_laps=5,
            last_lap_time_ms=82_600,
            best_lap_time_ms=82_600,
        )
    )

    lap_message = next(alert.message for alert in alerts if alert.category == "lap")
    assert lap_message.startswith("Lap 2: 1:23.")
    assert "New best, improved by less than 1 second." in lap_message


def test_sub_half_second_slower_lap_says_less_than_one_second():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, current_lap=1, total_laps=5))
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=5,
            last_lap_time_ms=82_999,
            best_lap_time_ms=82_999,
        )
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=3,
            total_laps=5,
            last_lap_time_ms=83_300,
            best_lap_time_ms=82_999,
        )
    )

    lap_message = next(alert.message for alert in alerts if alert.category == "lap")
    assert "Less than 1 second to best." in lap_message


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


def test_timed_race_uses_time_remaining_instead_of_lap_zero():
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

    snapshot = service.state.snapshot
    assert snapshot.race_mode == "timed"
    assert snapshot.total_laps is None
    assert snapshot.laps_left is None
    assert snapshot.race_elapsed_time_ms == 300_000
    assert snapshot.race_time_remaining_ms == 25 * 60_000
    assert snapshot.to_dict()["race_duration"] == "30:00"
    assert snapshot.to_dict()["race_time_remaining"] == "25:00"


def test_timed_race_ignores_time_of_day_jumps_for_remaining_time():
    service = RaceEngineerService(AppConfig(race_duration_minutes=30))
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
            timestamp=2.0,
            current_lap=1,
            total_laps=0,
            time_of_day_ms=17 * 60 * 60_000,
        )
    )

    snapshot = service.state.snapshot
    assert snapshot.timer_mode == "app_elapsed"
    assert snapshot.race_elapsed_time_ms == 1000
    assert snapshot.race_time_remaining_ms == 30 * 60_000 - 1000


def test_timed_race_starts_when_gt7_reports_lap_zero_on_track():
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
    service.update_frame(
        synthetic_frame(
            timestamp=61.0,
            current_lap=0,
            total_laps=0,
            speed_kph=90.0,
            cars_on_track=True,
        )
    )

    snapshot = service.state.snapshot
    assert snapshot.race_mode == "timed"
    assert snapshot.race_elapsed_time_ms == 60_000
    assert snapshot.race_time_remaining_ms == 39 * 60_000


def test_timed_race_timer_freezes_while_paused():
    service = RaceEngineerService(AppConfig(race_duration_minutes=30))
    service.update_frame(
        synthetic_frame(
            timestamp=0.0,
            current_lap=1,
            total_laps=0,
            cars_on_track=True,
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=60.0,
            current_lap=1,
            total_laps=0,
            cars_on_track=True,
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=300.0,
            current_lap=1,
            total_laps=0,
            cars_on_track=True,
            is_paused=True,
        )
    )

    snapshot = service.state.snapshot
    assert snapshot.session_phase == "paused"
    assert snapshot.race_elapsed_time_ms == 60_000
    assert snapshot.race_time_remaining_ms == 29 * 60_000

    service.update_frame(
        synthetic_frame(
            timestamp=301.0,
            current_lap=1,
            total_laps=0,
            cars_on_track=True,
        )
    )

    snapshot = service.state.snapshot
    assert snapshot.session_phase == "racing"
    assert snapshot.race_elapsed_time_ms == 61_000
    assert snapshot.race_time_remaining_ms == 30 * 60_000 - 61_000


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


def test_finish_summary_alert_reports_position_and_best_lap_once():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=1,
            total_laps=3,
            current_position=5,
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=3,
            current_position=4,
            last_lap_time_ms=83_100,
            best_lap_time_ms=83_100,
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=3,
            total_laps=3,
            current_position=3,
            last_lap_time_ms=82_600,
            best_lap_time_ms=82_600,
        )
    )

    finish_alerts = service.update_frame(
        synthetic_frame(
            timestamp=4.0,
            current_lap=4,
            total_laps=3,
            current_position=3,
            last_lap_time_ms=84_000,
            best_lap_time_ms=82_600,
        )
    )
    repeat_alerts = service.update_frame(
        synthetic_frame(
            timestamp=5.0,
            current_lap=4,
            total_laps=3,
            current_position=3,
            last_lap_time_ms=84_000,
            best_lap_time_ms=82_600,
        )
    )

    assert [alert.message for alert in finish_alerts if alert.category == "lap"] == [
        "Race finished. P3. Best lap was 1:23 on lap 2."
    ]
    assert not [alert for alert in repeat_alerts if "Race finished" in alert.message]


def test_finish_summary_alert_uses_missing_data_fallbacks():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            current_lap=1,
            total_laps=1,
            current_position=None,
            last_lap_time_ms=-1,
            best_lap_time_ms=-1,
        )
    )

    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            current_lap=2,
            total_laps=1,
            current_position=None,
            last_lap_time_ms=-1,
            best_lap_time_ms=-1,
        )
    )

    assert [alert.message for alert in alerts if alert.category == "lap"] == [
        "Race finished. Position unavailable. Best lap unavailable."
    ]


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
    candidate_alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            speed_kph=30,
            tire_radius={"fl": 0.26, "fr": 0.33, "rl": 0.33, "rr": 0.33},
            wheel_rps={"fl": 4, "fr": 4, "rl": 4, "rr": 4},
        )
    )
    confirmed_alerts = service.update_frame(
        synthetic_frame(
            timestamp=5.1,
            speed_kph=30,
            tire_radius={"fl": 0.26, "fr": 0.33, "rl": 0.33, "rr": 0.33},
            wheel_rps={"fl": 4, "fr": 4, "rl": 4, "rr": 4},
        )
    )

    candidate_messages = [alert.message for alert in candidate_alerts]
    confirmed_messages = [alert.message for alert in confirmed_alerts]
    assert any("Estimated tire wear" in message for message in candidate_messages)
    assert not any("Possible impact" in message for message in candidate_messages)
    assert any("Possible impact" in message for message in confirmed_messages)


def test_pit_transition_cancels_pending_impact_alert():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, speed_kph=110))
    candidate_alerts = service.update_frame(synthetic_frame(timestamp=2.0, speed_kph=30))
    pit_alerts = service.update_frame(
        synthetic_frame(timestamp=3.0, speed_kph=20, is_paused=True)
    )
    resumed_alerts = service.update_frame(synthetic_frame(timestamp=5.5, speed_kph=20))

    assert not any("Possible impact" in alert.message for alert in candidate_alerts)
    assert not any("Possible impact" in alert.message for alert in pit_alerts)
    assert not any("Possible impact" in alert.message for alert in resumed_alerts)


def test_refuel_jump_cancels_pending_impact_alert():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, speed_kph=110, fuel_level=20.0))
    candidate_alerts = service.update_frame(
        synthetic_frame(timestamp=2.0, speed_kph=30, fuel_level=20.0)
    )
    refuel_alerts = service.update_frame(
        synthetic_frame(timestamp=3.0, speed_kph=30, fuel_level=60.0)
    )
    later_alerts = service.update_frame(
        synthetic_frame(timestamp=5.5, speed_kph=30, fuel_level=60.0)
    )

    assert not any("Possible impact" in alert.message for alert in candidate_alerts)
    assert not any("Possible impact" in alert.message for alert in refuel_alerts)
    assert not any("Possible impact" in alert.message for alert in later_alerts)


def test_real_impact_alerts_after_confirmation_window():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, speed_kph=110))
    candidate_alerts = service.update_frame(synthetic_frame(timestamp=2.0, speed_kph=30))
    early_alerts = service.update_frame(synthetic_frame(timestamp=4.0, speed_kph=30))
    confirmed_alerts = service.update_frame(synthetic_frame(timestamp=5.1, speed_kph=30))

    assert not any("Possible impact" in alert.message for alert in candidate_alerts)
    assert not any("Possible impact" in alert.message for alert in early_alerts)
    assert any("Possible impact" in alert.message for alert in confirmed_alerts)


def test_spin_alert_stays_immediate():
    service = RaceEngineerService(AppConfig())
    service.update_frame(synthetic_frame(timestamp=1.0, speed_kph=70))
    alerts = service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            speed_kph=70,
            angular_velocity={"z": 3.0},
        )
    )

    messages = [alert.message for alert in alerts]
    assert any("Possible spin" in message for message in messages)


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


def test_driving_alerts_use_completed_lap_instead_of_cumulative_wheelspin():
    config = AppConfig(preset="practice")
    config.set_preset("practice")
    service = RaceEngineerService(config)

    for timestamp in [1.0, 1.5, 2.0]:
        _send_wheelspin_event(service, timestamp, current_lap=1)
    first_lap_alerts = service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=2,
            throttle=0,
            last_lap_time_ms=98_000,
            best_lap_time_ms=98_000,
        )
    )

    assert any("Wheelspin" in alert.message for alert in first_lap_alerts)
    assert service.snapshot.lap_history[-1].driving_style.wheelspin_events == 3

    service.alerts._last_by_key["driving_style"] = 0
    for timestamp in [4.0, 4.5, 5.0, 5.5]:
        service.update_frame(
            synthetic_frame(timestamp=timestamp, current_lap=2, tcs_active=True)
        )
        service.update_frame(
            synthetic_frame(timestamp=timestamp + 0.1, current_lap=2, tcs_active=False)
        )
    second_lap_alerts = service.update_frame(
        synthetic_frame(
            timestamp=6.0,
            current_lap=3,
            throttle=0,
            tcs_active=False,
            last_lap_time_ms=98_000,
            best_lap_time_ms=98_000,
        )
    )

    completed_lap = service.snapshot.lap_history[-1]
    assert completed_lap.driving_style.wheelspin_events == 0
    assert completed_lap.driving_style.tcs_events == 4
    assert any("Traction control" in alert.message for alert in second_lap_alerts)
    assert not any("Wheelspin" in alert.message for alert in second_lap_alerts)


def test_cumulative_wheelspin_does_not_alert_when_completed_lap_is_clean():
    config = AppConfig(preset="practice")
    config.set_preset("practice")
    service = RaceEngineerService(config)

    for timestamp in [1.0, 1.5, 2.0]:
        _send_wheelspin_event(service, timestamp, current_lap=1)
    first_lap_alerts = service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=2,
            throttle=0,
            last_lap_time_ms=98_000,
            best_lap_time_ms=98_000,
        )
    )

    assert any("Wheelspin" in alert.message for alert in first_lap_alerts)

    service.alerts._last_by_key["driving_style"] = 0
    second_lap_alerts = service.update_frame(
        synthetic_frame(
            timestamp=4.0,
            current_lap=3,
            throttle=0,
            last_lap_time_ms=98_000,
            best_lap_time_ms=98_000,
        )
    )

    completed_lap = service.snapshot.lap_history[-1]
    assert service.snapshot.driving_style.wheelspin_events == 3
    assert completed_lap.driving_style.wheelspin_events == 0
    assert not any(alert.category == "driving" for alert in second_lap_alerts)


def _send_wheelspin_event(
    service: RaceEngineerService,
    timestamp: float,
    *,
    current_lap: int,
) -> None:
    service.update_frame(
        synthetic_frame(
            timestamp=timestamp,
            current_lap=current_lap,
            throttle=90,
            wheel_rps={"fl": 20, "fr": 20, "rl": 26, "rr": 26},
        )
    )
    service.update_frame(
        synthetic_frame(
            timestamp=timestamp + 0.1,
            current_lap=current_lap,
            throttle=0,
            wheel_rps={"fl": 20, "fr": 20, "rl": 20, "rr": 20},
        )
    )


def test_snapshot_includes_live_wheelspin_and_lockup_flags():
    service = RaceEngineerService(AppConfig())

    service.update_frame(
        synthetic_frame(
            timestamp=1.0,
            throttle=90,
            brake=0,
            speed_kph=80.0,
            wheel_rps={"fl": 20, "fr": 20, "rl": 26, "rr": 26},
        )
    )

    assert service.snapshot.wheelspin_active is True
    assert service.snapshot.lockup_active is False
    assert service.snapshot.driving_style.wheelspin_events == 1

    service.update_frame(
        synthetic_frame(
            timestamp=2.0,
            throttle=0,
            brake=200,
            speed_kph=80.0,
            wheel_rps={"fl": 20, "fr": 20, "rl": 20, "rr": 5},
        )
    )

    assert service.snapshot.wheelspin_active is False
    assert service.snapshot.lockup_active is True
    assert service.snapshot.driving_style.lockup_events == 1


def test_completed_lap_includes_per_lap_tc_and_asm_counts():
    service = RaceEngineerService(AppConfig())
    service.update_frame(
        synthetic_frame(timestamp=1.0, current_lap=1, tcs_active=True, asm_active=True)
    )
    service.update_frame(
        synthetic_frame(timestamp=1.5, current_lap=1, tcs_active=False, asm_active=False)
    )
    service.update_frame(
        synthetic_frame(timestamp=2.0, current_lap=1, tcs_active=True, asm_active=True)
    )
    service.update_frame(
        synthetic_frame(
            timestamp=3.0,
            current_lap=2,
            tcs_active=False,
            asm_active=False,
            last_lap_time_ms=98_000,
            best_lap_time_ms=98_000,
        )
    )

    lap = service.snapshot.lap_history[-1]
    assert lap.lap_number == 1
    assert lap.driving_style.tcs_events == 2
    assert lap.driving_style.asm_events == 2
    assert service.snapshot.driving_style.tcs_events == 2
    assert service.snapshot.driving_style.asm_events == 2


def test_snapshot_includes_gt_alert_rpm_range():
    service = RaceEngineerService(AppConfig())

    service.update_frame(
        synthetic_frame(
            engine_rpm=7350.0,
            min_alert_rpm=6200.0,
            max_alert_rpm=8100.0,
            suggested_gear=3,
        )
    )

    assert service.snapshot.engine_rpm == 7350.0
    assert service.snapshot.min_alert_rpm == 6200.0
    assert service.snapshot.max_alert_rpm == 8100.0
    assert service.snapshot.suggested_gear == 3
