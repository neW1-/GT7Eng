from pathlib import Path

from fastapi.testclient import TestClient

from gt7eng.config import AppConfig
from gt7eng.control import DiscordBridgeManager, EnvFile
from gt7eng.server import create_app


def test_env_file_updates_existing_keys_and_appends_missing(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# keep this comment",
                "GT7ENG_PRESET=endurance",
                "",
                "OTHER=value",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    EnvFile(env_path).update(
        {
            "GT7ENG_PRESET": "practice",
            "GT7ENG_VOICE_MODE": "quiet_driver_ai",
        }
    )

    assert env_path.read_text(encoding="utf-8").splitlines() == [
        "# keep this comment",
        "GT7ENG_PRESET=practice",
        "",
        "OTHER=value",
        "",
        "GT7ENG_VOICE_MODE=quiet_driver_ai",
    ]


def test_control_settings_updates_runtime_and_env(tmp_path):
    app = create_app(AppConfig(), telemetry_mode="none", project_root=tmp_path)
    client = TestClient(app)

    response = client.patch(
        "/api/control/settings",
        json={
            "preset": "practice",
            "verbosity": {"fuel": "off", "lap": "detailed"},
            "voice_mode": "quiet_driver_ai",
            "muted": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["status"]
    assert payload["config"]["preset"] == "practice"
    assert payload["config"]["verbosity"]["fuel"] == "off"
    assert payload["voice"]["mode"] == "quiet_driver_ai"
    assert payload["voice"]["muted"] is True
    values = EnvFile(tmp_path / ".env").read_values()
    assert values["GT7ENG_PRESET"] == "practice"
    assert values["GT7ENG_VERBOSITY_FUEL"] == "off"
    assert values["GT7ENG_VERBOSITY_LAP"] == "detailed"
    assert values["GT7ENG_VOICE_MODE"] == "quiet_driver_ai"
    assert values["GT7ENG_ENGINEER_MUTED"] == "true"


def test_control_endpoints_reject_non_local_clients(tmp_path):
    app = create_app(AppConfig(), telemetry_mode="none", project_root=tmp_path)
    client = TestClient(app, client=("192.168.1.50", 50000))

    response = client.patch("/api/control/settings", json={"preset": "practice"})

    assert response.status_code == 403
    response = client.patch("/api/control/wind", json={"enabled": True})
    assert response.status_code == 403


def test_stt_control_persists_python_and_discord_settings(tmp_path):
    app = create_app(AppConfig(), telemetry_mode="none", project_root=tmp_path)
    client = TestClient(app)

    response = client.patch(
        "/api/control/stt",
        json={
            "enabled": False,
            "model": "base.en",
            "device": "cpu",
            "min_confidence": 0.45,
            "discord_enabled": True,
        },
    )

    assert response.status_code == 200
    status = response.json()["status"]
    assert status["audio"]["stt"]["enabled"] is False
    assert status["audio"]["stt"]["model"] == "base.en"
    assert status["audio"]["stt"]["device"] == "cpu"
    assert status["config"]["discord_stt_enabled"] is True
    root_values = EnvFile(tmp_path / ".env").read_values()
    bridge_values = EnvFile(tmp_path / "bridge" / "discord" / ".env").read_values()
    assert root_values["GT7ENG_STT_MODEL"] == "base.en"
    assert root_values["GT7ENG_STT_DEVICE"] == "cpu"
    assert root_values["GT7ENG_STT_MIN_CONFIDENCE"] == "0.45"
    assert root_values["DISCORD_STT_ENABLED"] == "true"
    assert bridge_values["DISCORD_STT_ENABLED"] == "true"


def test_pixel_control_persists_runtime_config_and_preview(tmp_path):
    app = create_app(AppConfig(), telemetry_mode="none", project_root=tmp_path)
    client = TestClient(app)

    response = client.patch(
        "/api/control/pixel-display",
        json={
            "enabled": False,
            "address": "device-uuid",
            "brightness": 42,
            "color_theme": "warm_amber",
            "gear_layout": "current_suggested",
            "fuel_enabled": True,
            "fuel_warn_color": "#ffee00",
        },
    )

    assert response.status_code == 200
    pixel = response.json()["status"]["config"]["pixel_display"]
    assert pixel["address"] == "device-uuid"
    assert pixel["brightness"] == 42
    assert pixel["color_theme"] == "warm_amber"
    assert pixel["gear_layout"] == "current_suggested"
    assert pixel["fuel_enabled"] is True
    assert pixel["fuel_warn_color"] == "ffee00"
    values = EnvFile(tmp_path / ".env").read_values()
    assert values["GT7ENG_PIXEL_DISPLAY_ADDRESS"] == "device-uuid"
    assert values["GT7ENG_PIXEL_DISPLAY_BRIGHTNESS"] == "42"
    assert values["GT7ENG_PIXEL_DISPLAY_FUEL_WARN_COLOR"] == "ffee00"

    preview = client.get("/api/control/pixel-display/preview.png")

    assert preview.status_code == 200
    assert preview.content.startswith(b"\x89PNG")


def test_wind_control_persists_runtime_config_and_env_without_token(tmp_path):
    config = AppConfig()
    config.wind.ha_token = "secret-token"
    app = create_app(config, telemetry_mode="none", project_root=tmp_path)
    client = TestClient(app)

    response = client.patch(
        "/api/control/wind",
        json={
            "enabled": False,
            "ha_base_url": "http://ha.local:8123/",
            "ha_entity_id": "number.rig_fan_level",
            "update_hz": 1,
            "max_speed_kph": 320,
            "curve_exponent": 2,
            "deadband_kph": 5,
            "min_level": 0,
            "max_level": 14,
            "smoothing_seconds": 0.5,
            "hysteresis_levels": 2,
            "timeout_seconds": 3,
        },
    )

    assert response.status_code == 200
    text = response.text
    assert "secret-token" not in text
    assert "GT7ENG_WIND_HA_TOKEN" not in text
    status = response.json()["status"]
    wind = status["config"]["wind"]
    assert wind["enabled"] is False
    assert wind["ha_base_url"] == "http://ha.local:8123"
    assert wind["ha_entity_id"] == "number.rig_fan_level"
    assert wind["update_hz"] == 1
    assert wind["max_speed_kph"] == 320
    assert wind["curve_exponent"] == 2
    assert wind["deadband_kph"] == 5
    assert wind["smoothing_seconds"] == 0.5
    assert wind["hysteresis_levels"] == 2
    assert wind["timeout_seconds"] == 3
    assert status["wind"]["ha_entity_id"] == "number.rig_fan_level"
    assert "ha_token" not in status["config"]["wind"]
    assert "ha_token" not in status["wind"]
    values = EnvFile(tmp_path / ".env").read_values()
    assert values["GT7ENG_WIND_HA_BASE_URL"] == "http://ha.local:8123"
    assert values["GT7ENG_WIND_HA_ENTITY_ID"] == "number.rig_fan_level"
    assert values["GT7ENG_WIND_UPDATE_HZ"] == "1.0"
    assert "GT7ENG_WIND_HA_TOKEN" not in values


def test_discord_bridge_status_accepts_heartbeat(tmp_path):
    app = create_app(AppConfig(), telemetry_mode="none", project_root=tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/discord/bridge-status",
        json={"voiceChannelId": "channel-1", "driverAudioPackets": 12, "pid": 123},
    )

    assert response.status_code == 200
    bridge = client.get("/api/status").json()["discord_bridge"]
    assert bridge["heartbeat"]["payload"]["voiceChannelId"] == "channel-1"
    assert bridge["heartbeat"]["payload"]["driverAudioPackets"] == 12


def test_discord_bridge_manager_reports_missing_setup_and_stale_pid(tmp_path):
    manager = DiscordBridgeManager(tmp_path)

    assert manager.status()["state"] == "stopped"

    manager.pid_file.parent.mkdir(parents=True)
    manager.pid_file.write_text("999999", encoding="utf-8")

    assert manager.status()["state"] == "stale_pid"
    try:
        manager.start()
    except RuntimeError as exc:
        assert "Missing bridge/discord/.env" in str(exc)
    else:
        raise AssertionError("manager.start() should fail without bridge .env")
