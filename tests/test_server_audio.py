from fastapi.testclient import TestClient

from gt7eng.config import AppConfig
from gt7eng.server import create_app


def test_discord_audio_endpoint_reports_disabled_stt():
    app = create_app(AppConfig(), telemetry_mode="none")
    client = TestClient(app)

    response = client.post("/api/discord/audio", content=b"not-a-real-wav")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "disabled" in payload["error"].lower()


def test_status_reports_audio_engines():
    app = create_app(AppConfig(), telemetry_mode="none")
    client = TestClient(app)

    payload = client.get("/api/status").json()

    assert payload["audio"]["stt"]["enabled"] is False
    assert "tts" in payload["audio"]
    assert "last" in payload["voice"]
    assert payload["config"]["llm"]["intent_repair_enabled"] is True
    assert payload["pixel_display"]["enabled"] is False
    assert payload["config"]["pixel_display"]["color_theme"] == "simdt_blue"


def test_discord_mode_endpoint_accepts_quiet_driver_ai():
    app = create_app(AppConfig(), telemetry_mode="none")
    client = TestClient(app)

    response = client.post("/discord/mode", json={"mode": "quiet_driver_ai"})

    assert response.status_code == 200
    assert response.json()["mode"] == "quiet_driver_ai"
    assert client.get("/api/status").json()["voice"]["mode"] == "quiet_driver_ai"
