from pathlib import Path

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
    assert payload["pixel_display"]["gear_layout"] == "current"
    assert payload["pixel_display"]["device_width"] is None
    assert payload["config"]["pixel_display"]["color_theme"] == "simdt_blue"
    assert payload["config"]["pixel_display"]["gear_layout"] == "current"
    assert payload["config"]["pixel_display"]["width"] == 64
    assert payload["config"]["pixel_display"]["height"] == 64
    assert payload["config"]["pixel_display"]["size_source"] == "auto"
    assert payload["config"]["pixel_display"]["rev_scale"] == "wide"
    assert payload["config"]["pixel_display"]["shift_mode"] == "rev_limit"
    assert payload["pixel_display"]["rev"]["percent"] == 0.0


def test_discord_mode_endpoint_accepts_quiet_driver_ai():
    app = create_app(AppConfig(), telemetry_mode="none")
    client = TestClient(app)

    response = client.post("/discord/mode", json={"mode": "quiet_driver_ai"})

    assert response.status_code == 200
    assert response.json()["mode"] == "quiet_driver_ai"
    assert client.get("/api/status").json()["voice"]["mode"] == "quiet_driver_ai"


def test_hud_pixel_status_uses_runtime_or_config_enabled_state():
    static_dir = Path(__file__).parents[1] / "src" / "gt7eng" / "static"
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    index_html = (static_dir / "index.html").read_text(encoding="utf-8")

    assert "pixel.enabled || pixelConfig.enabled" in app_js
    assert "pixel live" in app_js
    assert "pixel wait" in app_js
    assert "pixel warn" in app_js
    assert "suggestedGear.textContent = snap.suggested_gear" in app_js
    assert 'id="suggested-gear"' in index_html
    assert "suggested-gear-hud-1" in index_html
