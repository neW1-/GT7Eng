from pathlib import Path

from fastapi.testclient import TestClient

from gt7eng.config import AppConfig, PIXEL_COLOR_THEMES
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
    assert payload["config"]["pixel_display"]["fuel_enabled"] is False
    assert payload["options"]["pixel"]["color_themes"] == list(PIXEL_COLOR_THEMES)
    assert len(payload["options"]["pixel"]["color_themes"]) >= 14
    assert payload["pixel_display"]["rev"]["percent"] == 0.0
    assert payload["pixel_display"]["fuel"]["enabled"] is False
    assert payload["pixel_display"]["fuel"]["visible"] is False
    assert payload["pixel_display"]["fuel"]["position"] == "top"
    assert payload["wind"]["enabled"] is False
    assert payload["wind"]["ha_entity_id"] == "number.zhimi_cpa4_cee4_favorite_level"
    assert payload["config"]["wind"]["enabled"] is False
    assert payload["config"]["wind"]["off_level"] == 0
    assert payload["config"]["wind"]["min_active_level"] == 0
    assert payload["config"]["wind"]["max_level"] == 14
    assert "ha_token" not in payload["wind"]
    assert "ha_token" not in payload["config"]["wind"]


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
    assert "control_allowed" in app_js
    assert "/api/control/settings" in app_js
    assert "/api/control/pixel-display" in app_js
    assert "/api/control/wind" in app_js
    assert "/api/control/wind/start" in app_js
    assert "/api/control/wind/stop" in app_js
    assert "wind live" in app_js
    assert "wind wait" in app_js
    assert "wind warn" in app_js
    assert "ha_token" not in app_js
    assert 'id="suggested-gear"' in index_html
    assert 'id="settings-form"' in index_html
    assert 'id="pixel-form"' in index_html
    assert 'id="wind-status"' in index_html
    assert 'id="wind-form"' in index_html
    assert 'id="wind-start"' in index_html
    assert 'id="wind-stop"' in index_html
    assert "GT7ENG_WIND_HA_TOKEN" not in index_html
    assert "control-plane-2" in index_html
