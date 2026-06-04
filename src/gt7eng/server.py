import asyncio
import tempfile
from pathlib import Path
from typing import Any

from .config import DEFAULT_VERBOSITY, PRESETS, AppConfig, PixelDisplayConfig, WindConfig
from .control import DiscordBridgeManager, EnvFile, is_local_host
from .models import RaceSnapshot
from .pixel_display import PixelDisplayRenderer
from .service import RaceEngineerService
from .stt import STTUnavailableError, create_stt
from .telemetry import GTTelemTelemetrySource, ReplayTelemetrySource
from .tts import TTSUnavailableError, create_tts


VERBOSITY_LEVELS = ["off", "critical", "balanced", "detailed"]
VOICE_MODES = ["wake_phrase", "quiet_driver", "quiet_driver_ai"]
STT_DEVICES = ["auto", "cpu", "cuda"]

ROOT_STT_KEYS = {
    "enabled": "GT7ENG_STT_ENABLED",
    "model": "GT7ENG_STT_MODEL",
    "device": "GT7ENG_STT_DEVICE",
    "min_confidence": "GT7ENG_STT_MIN_CONFIDENCE",
}

PIXEL_ENV_KEYS = {
    "enabled": "GT7ENG_PIXEL_DISPLAY_ENABLED",
    "address": "GT7ENG_PIXEL_DISPLAY_ADDRESS",
    "update_hz": "GT7ENG_PIXEL_DISPLAY_UPDATE_HZ",
    "rev_position": "GT7ENG_PIXEL_DISPLAY_REV_POSITION",
    "brightness": "GT7ENG_PIXEL_DISPLAY_BRIGHTNESS",
    "dim_brightness": "GT7ENG_PIXEL_DISPLAY_DIM_BRIGHTNESS",
    "orientation": "GT7ENG_PIXEL_DISPLAY_ORIENTATION",
    "size_source": "GT7ENG_PIXEL_DISPLAY_SIZE_SOURCE",
    "width": "GT7ENG_PIXEL_DISPLAY_WIDTH",
    "height": "GT7ENG_PIXEL_DISPLAY_HEIGHT",
    "gear_layout": "GT7ENG_PIXEL_DISPLAY_GEAR_LAYOUT",
    "rev_scale": "GT7ENG_PIXEL_DISPLAY_REV_SCALE",
    "rev_start_percent": "GT7ENG_PIXEL_DISPLAY_REV_START_PERCENT",
    "shift_mode": "GT7ENG_PIXEL_DISPLAY_SHIFT_MODE",
    "shift_percent": "GT7ENG_PIXEL_DISPLAY_SHIFT_PERCENT",
    "flash_hz": "GT7ENG_PIXEL_DISPLAY_FLASH_HZ",
    "color_theme": "GT7ENG_PIXEL_DISPLAY_COLOR_THEME",
    "gear_color": "GT7ENG_PIXEL_DISPLAY_GEAR_COLOR",
    "rev_low_color": "GT7ENG_PIXEL_DISPLAY_REV_LOW_COLOR",
    "rev_mid_color": "GT7ENG_PIXEL_DISPLAY_REV_MID_COLOR",
    "rev_high_color": "GT7ENG_PIXEL_DISPLAY_REV_HIGH_COLOR",
    "shift_color": "GT7ENG_PIXEL_DISPLAY_SHIFT_COLOR",
    "fuel_enabled": "GT7ENG_PIXEL_DISPLAY_FUEL_ENABLED",
    "fuel_safe_color": "GT7ENG_PIXEL_DISPLAY_FUEL_SAFE_COLOR",
    "fuel_warn_color": "GT7ENG_PIXEL_DISPLAY_FUEL_WARN_COLOR",
    "fuel_danger_color": "GT7ENG_PIXEL_DISPLAY_FUEL_DANGER_COLOR",
    "fuel_critical_color": "GT7ENG_PIXEL_DISPLAY_FUEL_CRITICAL_COLOR",
    "rpm_min": "GT7ENG_PIXEL_DISPLAY_RPM_MIN",
    "rpm_max": "GT7ENG_PIXEL_DISPLAY_RPM_MAX",
}

WIND_ENV_KEYS = {
    "enabled": "GT7ENG_WIND_ENABLED",
    "ha_base_url": "GT7ENG_WIND_HA_BASE_URL",
    "ha_entity_id": "GT7ENG_WIND_HA_ENTITY_ID",
    "update_hz": "GT7ENG_WIND_UPDATE_HZ",
    "max_speed_kph": "GT7ENG_WIND_MAX_SPEED_KPH",
    "curve_exponent": "GT7ENG_WIND_CURVE_EXPONENT",
    "deadband_kph": "GT7ENG_WIND_DEADBAND_KPH",
    "off_level": "GT7ENG_WIND_OFF_LEVEL",
    "min_active_level": "GT7ENG_WIND_MIN_ACTIVE_LEVEL",
    "max_level": "GT7ENG_WIND_MAX_LEVEL",
    "smoothing_seconds": "GT7ENG_WIND_SMOOTHING_SECONDS",
    "hysteresis_levels": "GT7ENG_WIND_HYSTERESIS_LEVELS",
    "timeout_seconds": "GT7ENG_WIND_TIMEOUT_SECONDS",
}


def _bool_value(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _enum_value(value: Any, choices: list[str], name: str) -> str:
    normalized = str(value).strip()
    if normalized not in choices:
        raise ValueError(f"{name} must be one of: {', '.join(choices)}")
    return normalized


def _int_range_value(value: Any, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _float_range_value(value: Any, name: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
    return parsed


def _optional_positive_float(value: Any, name: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _hex_color_value(value: Any, name: str) -> str:
    normalized = str(value or "").strip().lstrip("#").lower()
    if not normalized:
        return ""
    if len(normalized) != 6 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{name} must be a six-digit hex color")
    return normalized


def _verbosity_env_key(category: str) -> str:
    return f"GT7ENG_VERBOSITY_{category.upper()}"


def _all_verbosity_env(config: AppConfig) -> dict[str, str]:
    return {
        _verbosity_env_key(category): config.verbosity[category]
        for category in DEFAULT_VERBOSITY
    }


def _apply_pixel_payload(pixel: PixelDisplayConfig, payload: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}

    def set_value(name: str, value: Any) -> None:
        setattr(pixel, name, value)
        updates[PIXEL_ENV_KEYS[name]] = "" if value is None else value

    if "enabled" in payload:
        set_value("enabled", _bool_value(payload["enabled"], "enabled"))
    if "address" in payload:
        set_value("address", str(payload["address"]).strip())
    if "update_hz" in payload:
        set_value("update_hz", _float_range_value(payload["update_hz"], "update_hz", 1.0, 30.0))
    if "rev_position" in payload:
        set_value("rev_position", _enum_value(payload["rev_position"], ["top", "bottom"], "rev_position"))
    if "brightness" in payload:
        set_value("brightness", _int_range_value(payload["brightness"], "brightness", 0, 100))
    if "dim_brightness" in payload:
        set_value("dim_brightness", _int_range_value(payload["dim_brightness"], "dim_brightness", 0, 100))
    if "orientation" in payload:
        set_value("orientation", _int_range_value(payload["orientation"], "orientation", 0, 3))
    if "size_source" in payload:
        set_value("size_source", _enum_value(payload["size_source"], ["auto", "config"], "size_source"))
    if "width" in payload:
        set_value("width", _int_range_value(payload["width"], "width", 8, 512))
    if "height" in payload:
        set_value("height", _int_range_value(payload["height"], "height", 8, 512))
    if "gear_layout" in payload:
        set_value("gear_layout", _enum_value(payload["gear_layout"], ["current", "current_suggested"], "gear_layout"))
    if "rev_scale" in payload:
        set_value("rev_scale", _enum_value(payload["rev_scale"], ["wide", "alert_window"], "rev_scale"))
    if "rev_start_percent" in payload:
        set_value("rev_start_percent", _float_range_value(payload["rev_start_percent"], "rev_start_percent", 0.0, 0.95))
    if "shift_mode" in payload:
        set_value("shift_mode", _enum_value(payload["shift_mode"], ["rev_limit", "percent"], "shift_mode"))
    if "shift_percent" in payload:
        set_value("shift_percent", _float_range_value(payload["shift_percent"], "shift_percent", 0.0, 1.0))
    if "flash_hz" in payload:
        set_value("flash_hz", _float_range_value(payload["flash_hz"], "flash_hz", 1.0, 20.0))
    if "color_theme" in payload:
        set_value("color_theme", _enum_value(payload["color_theme"], ["simdt_blue", "warm_amber", "race_gyr", "custom"], "color_theme"))
    for color_name in [
        "gear_color",
        "rev_low_color",
        "rev_mid_color",
        "rev_high_color",
        "shift_color",
        "fuel_safe_color",
        "fuel_warn_color",
        "fuel_danger_color",
        "fuel_critical_color",
    ]:
        if color_name in payload:
            set_value(color_name, _hex_color_value(payload[color_name], color_name))
    if "fuel_enabled" in payload:
        set_value("fuel_enabled", _bool_value(payload["fuel_enabled"], "fuel_enabled"))
    if "rpm_min" in payload:
        set_value("rpm_min", _optional_positive_float(payload["rpm_min"], "rpm_min"))
    if "rpm_max" in payload:
        set_value("rpm_max", _optional_positive_float(payload["rpm_max"], "rpm_max"))

    return updates


def _apply_wind_payload(wind: WindConfig, payload: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}

    def set_value(name: str, value: Any) -> None:
        setattr(wind, name, value)
        updates[WIND_ENV_KEYS[name]] = value

    if "ha_token" in payload:
        raise ValueError("ha_token must be configured in .env, not through the HUD")
    if "enabled" in payload:
        set_value("enabled", _bool_value(payload["enabled"], "enabled"))
    if "ha_base_url" in payload:
        set_value("ha_base_url", str(payload["ha_base_url"]).strip().rstrip("/"))
    if "ha_entity_id" in payload:
        entity_id = str(payload["ha_entity_id"]).strip()
        if not entity_id:
            raise ValueError("ha_entity_id is required")
        set_value("ha_entity_id", entity_id)
    if "update_hz" in payload:
        set_value("update_hz", _float_range_value(payload["update_hz"], "update_hz", 0.1, 10.0))
    if "max_speed_kph" in payload:
        set_value("max_speed_kph", _float_range_value(payload["max_speed_kph"], "max_speed_kph", 1.0, 600.0))
    if "curve_exponent" in payload:
        set_value("curve_exponent", _float_range_value(payload["curve_exponent"], "curve_exponent", 0.1, 5.0))
    if "deadband_kph" in payload:
        set_value("deadband_kph", _float_range_value(payload["deadband_kph"], "deadband_kph", 0.0, 100.0))
    min_active_payload_key = (
        "min_active_level"
        if "min_active_level" in payload
        else "min_level"
        if "min_level" in payload
        else None
    )
    next_off_level = (
        _int_range_value(payload["off_level"], "off_level", 0, 100)
        if "off_level" in payload
        else wind.off_level
    )
    next_min_active_level = (
        _int_range_value(
            payload[min_active_payload_key],
            "min_active_level",
            0,
            100,
        )
        if min_active_payload_key is not None
        else wind.min_active_level
    )
    next_max_level = (
        _int_range_value(payload["max_level"], "max_level", 0, 100)
        if "max_level" in payload
        else wind.max_level
    )
    if next_max_level < next_min_active_level:
        raise ValueError("max_level must be greater than or equal to min_active_level")
    if next_max_level < next_off_level:
        raise ValueError("max_level must be greater than or equal to off_level")
    if "off_level" in payload:
        set_value("off_level", next_off_level)
    if min_active_payload_key is not None:
        set_value("min_active_level", next_min_active_level)
    if "max_level" in payload:
        set_value("max_level", next_max_level)
    if "smoothing_seconds" in payload:
        set_value("smoothing_seconds", _float_range_value(payload["smoothing_seconds"], "smoothing_seconds", 0.0, 10.0))
    if "hysteresis_levels" in payload:
        set_value("hysteresis_levels", _int_range_value(payload["hysteresis_levels"], "hysteresis_levels", 0, 100))
    if "timeout_seconds" in payload:
        set_value("timeout_seconds", _float_range_value(payload["timeout_seconds"], "timeout_seconds", 0.1, 30.0))

    return updates


def create_app(
    config: AppConfig | None = None,
    *,
    telemetry_mode: str = "none",
    replay_file: Path | None = None,
    project_root: Path | None = None,
):
    try:
        from fastapi import FastAPI, HTTPException, Request, Response, WebSocket
        from fastapi.responses import FileResponse, HTMLResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for the web HUD. Run `pip install -e .`.") from exc

    class CommandRequest(BaseModel):
        text: str
        source: str = "text"
        user_id: str | None = None
        confidence: float | None = None

    project_root_path = Path.cwd() if project_root is None else project_root
    root_env = EnvFile(project_root_path / ".env")
    bridge_env = EnvFile(project_root_path / "bridge" / "discord" / ".env")
    bridge_manager = DiscordBridgeManager(project_root_path)
    app_config = config or AppConfig.from_env()
    service = RaceEngineerService(app_config)
    tts = create_tts(app_config.tts)
    stt_error = None
    try:
        stt = create_stt(app_config.stt)
    except STTUnavailableError as exc:
        stt = None
        stt_error = str(exc)
    app = FastAPI(title="GT7 Race Engineer", version="0.1.0")
    static_dir = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.state.service = service
    app.state.bridge_manager = bridge_manager

    def stt_status() -> dict:
        if stt is not None:
            status = stt.status()
        else:
            status = {
                "enabled": app_config.stt.enabled,
                "engine": app_config.stt.engine,
                "ready": False,
                "error": stt_error,
            }
        status.setdefault("model", app_config.stt.model)
        status.setdefault("device", app_config.stt.device)
        status["min_confidence"] = app_config.stt.min_confidence
        return status

    def reload_stt() -> dict:
        nonlocal stt, stt_error
        try:
            stt = create_stt(app_config.stt)
            stt_error = None
        except STTUnavailableError as exc:
            stt = None
            stt_error = str(exc)
        return stt_status()

    def local_control_allowed(request: Request) -> bool:
        return is_local_host(request.client.host if request.client else None)

    def require_local_control(request: Request) -> None:
        if not local_control_allowed(request):
            raise HTTPException(
                status_code=403,
                detail="HUD controls are available only from localhost.",
            )

    def control_payload(request: Request) -> dict:
        allowed = local_control_allowed(request)
        return {
            "allowed": allowed,
            "reason": "local" if allowed else "HUD controls are available only from localhost.",
        }

    def options_payload() -> dict:
        return {
            "presets": sorted(PRESETS.keys()),
            "verbosity_categories": list(DEFAULT_VERBOSITY.keys()),
            "verbosity_levels": VERBOSITY_LEVELS,
            "voice_modes": VOICE_MODES,
            "stt_devices": STT_DEVICES,
            "pixel": {
                "rev_positions": ["top", "bottom"],
                "size_sources": ["auto", "config"],
                "gear_layouts": ["current", "current_suggested"],
                "rev_scales": ["wide", "alert_window"],
                "shift_modes": ["rev_limit", "percent"],
                "color_themes": ["simdt_blue", "warm_amber", "race_gyr", "custom"],
            },
        }

    def status_payload(request: Request) -> dict[str, Any]:
        payload = service.status()
        root_values = root_env.read_values()
        control = control_payload(request)
        payload["control"] = control
        payload["control_allowed"] = control["allowed"]
        payload["options"] = options_payload()
        payload["config"]["discord_stt_enabled"] = root_values.get(
            "DISCORD_STT_ENABLED",
            "false",
        ).lower() in {"1", "true", "yes", "on"}
        payload["audio"] = {
            "tts": tts.status(),
            "stt": stt_status(),
        }
        payload["discord_bridge"] = bridge_manager.status()
        return payload

    @app.on_event("startup")
    async def startup() -> None:
        await service.start_pixel_display()
        await service.start_wind()
        if telemetry_mode == "live":
            await service.start_source(GTTelemTelemetrySource(app_config))
        elif telemetry_mode == "replay" and replay_file:
            await service.start_source(ReplayTelemetrySource(replay_file, realtime=True))

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await service.stop_source()
        await service.stop_pixel_display()
        await service.stop_wind()
        service.stop_capture()

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/api/status")
    async def status(request: Request) -> dict[str, Any]:
        return status_payload(request)

    @app.patch("/api/control/settings")
    async def control_settings(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        require_local_control(request)
        root_updates: dict[str, Any] = {}
        bridge_updates: dict[str, Any] = {}

        try:
            if "preset" in payload:
                preset = _enum_value(str(payload["preset"]), sorted(PRESETS.keys()), "preset")
                app_config.set_preset(preset)
                root_updates["GT7ENG_PRESET"] = preset

            if "verbosity" in payload:
                verbosity = payload["verbosity"]
                if not isinstance(verbosity, dict):
                    raise ValueError("verbosity must be an object")
                for category, level in verbosity.items():
                    if category not in DEFAULT_VERBOSITY:
                        raise ValueError(f"Unknown verbosity category: {category}")
                    app_config.verbosity[category] = _enum_value(
                        level,
                        VERBOSITY_LEVELS,
                        f"verbosity.{category}",
                    )  # type: ignore[index]

            if "preset" in payload or "verbosity" in payload:
                root_updates.update(_all_verbosity_env(app_config))

            if "voice_mode" in payload:
                mode = _enum_value(payload["voice_mode"], VOICE_MODES, "voice_mode")
                service.set_voice_mode(mode)
                root_updates["GT7ENG_VOICE_MODE"] = mode
                root_updates["DEFAULT_AUDIO_MODE"] = mode
                bridge_updates["DEFAULT_AUDIO_MODE"] = mode

            if "muted" in payload:
                muted = _bool_value(payload["muted"], "muted")
                service.set_muted(muted)
                root_updates["GT7ENG_ENGINEER_MUTED"] = muted
                root_updates["DEFAULT_ENGINEER_MUTED"] = muted
                bridge_updates["DEFAULT_ENGINEER_MUTED"] = muted
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if root_updates:
            root_env.update(root_updates)
        if bridge_updates:
            bridge_env.update(bridge_updates)
            bridge_manager.mark_restart_required()
        return {"ok": True, "status": status_payload(request)}

    @app.patch("/api/control/stt")
    async def control_stt(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        require_local_control(request)
        root_updates: dict[str, Any] = {}
        bridge_updates: dict[str, Any] = {}

        try:
            if "enabled" in payload:
                app_config.stt.enabled = _bool_value(payload["enabled"], "enabled")
                root_updates[ROOT_STT_KEYS["enabled"]] = app_config.stt.enabled
            if "model" in payload:
                app_config.stt.model = str(payload["model"]).strip() or "tiny.en"
                root_updates[ROOT_STT_KEYS["model"]] = app_config.stt.model
            if "device" in payload:
                app_config.stt.device = _enum_value(payload["device"], STT_DEVICES, "device")
                root_updates[ROOT_STT_KEYS["device"]] = app_config.stt.device
            if "min_confidence" in payload:
                app_config.stt.min_confidence = _float_range_value(
                    payload["min_confidence"],
                    "min_confidence",
                    0.0,
                    1.0,
                )
                root_updates[ROOT_STT_KEYS["min_confidence"]] = app_config.stt.min_confidence
            if "discord_enabled" in payload:
                discord_enabled = _bool_value(payload["discord_enabled"], "discord_enabled")
                root_updates["DISCORD_STT_ENABLED"] = discord_enabled
                bridge_updates["DISCORD_STT_ENABLED"] = discord_enabled
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if root_updates:
            root_env.update(root_updates)
        if bridge_updates:
            bridge_env.update(bridge_updates)
            bridge_manager.mark_restart_required()
        return {"ok": True, "stt": reload_stt(), "status": status_payload(request)}

    @app.patch("/api/control/pixel-display")
    async def control_pixel_display(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        require_local_control(request)
        try:
            updates = _apply_pixel_payload(app_config.pixel_display, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if updates:
            root_env.update(updates)
        await service.reconfigure_pixel_display()
        if app_config.pixel_display.enabled:
            await service.start_pixel_display()
        return {"ok": True, "status": status_payload(request)}

    @app.post("/api/control/pixel-display/start")
    async def control_pixel_start(request: Request) -> dict[str, Any]:
        require_local_control(request)
        app_config.pixel_display.enabled = True
        root_env.update({"GT7ENG_PIXEL_DISPLAY_ENABLED": True})
        await service.start_pixel_display()
        return {"ok": True, "status": status_payload(request)}

    @app.post("/api/control/pixel-display/stop")
    async def control_pixel_stop(request: Request) -> dict[str, Any]:
        require_local_control(request)
        app_config.pixel_display.enabled = False
        root_env.update({"GT7ENG_PIXEL_DISPLAY_ENABLED": False})
        await service.stop_pixel_display()
        return {"ok": True, "status": status_payload(request)}

    @app.patch("/api/control/wind")
    async def control_wind(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        require_local_control(request)
        try:
            updates = _apply_wind_payload(app_config.wind, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if updates:
            root_env.update(updates)
        await service.reconfigure_wind()
        if app_config.wind.enabled:
            await service.start_wind()
        return {"ok": True, "status": status_payload(request)}

    @app.post("/api/control/wind/start")
    async def control_wind_start(request: Request) -> dict[str, Any]:
        require_local_control(request)
        app_config.wind.enabled = True
        root_env.update({"GT7ENG_WIND_ENABLED": True})
        await service.start_wind()
        return {"ok": True, "status": status_payload(request)}

    @app.post("/api/control/wind/stop")
    async def control_wind_stop(request: Request) -> dict[str, Any]:
        require_local_control(request)
        app_config.wind.enabled = False
        root_env.update({"GT7ENG_WIND_ENABLED": False})
        await service.stop_wind()
        return {"ok": True, "status": status_payload(request)}

    @app.post("/api/control/discord-bridge/start")
    async def control_bridge_start(request: Request) -> dict[str, Any]:
        require_local_control(request)
        try:
            result = await asyncio.to_thread(bridge_manager.start)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "discord_bridge": result}

    @app.post("/api/control/discord-bridge/stop")
    async def control_bridge_stop(request: Request) -> dict[str, Any]:
        require_local_control(request)
        result = await asyncio.to_thread(bridge_manager.stop)
        return {"ok": True, "discord_bridge": result}

    @app.post("/api/control/discord-bridge/restart")
    async def control_bridge_restart(request: Request) -> dict[str, Any]:
        require_local_control(request)
        try:
            result = await asyncio.to_thread(bridge_manager.restart)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "discord_bridge": result}

    @app.get("/api/control/pixel-display/preview.png")
    async def control_pixel_preview(request: Request) -> Response:
        require_local_control(request)
        renderer = PixelDisplayRenderer(app_config.pixel_display)
        frame = renderer.render_snapshot(
            RaceSnapshot(
                connected=True,
                session_phase="racing",
                engine_rpm=7500.0,
                min_alert_rpm=6000.0,
                max_alert_rpm=9000.0,
                current_gear=4,
                suggested_gear=3,
                fuel_level=42.0,
            )
        )
        return Response(content=frame.to_png(), media_type="image/png")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/alerts")
    async def alerts(after: int = 0, speak_only: bool = False) -> list[dict]:
        return service.alerts_after(after, speak_only=speak_only)

    @app.post("/api/chat")
    async def chat(request: CommandRequest) -> dict:
        return await asyncio.to_thread(
            service.handle_command,
            request.text,
            request.source,
        )

    @app.post("/api/discord/transcript")
    async def discord_transcript(request: CommandRequest) -> dict:
        return await asyncio.to_thread(
            service.handle_transcript,
            request.text,
            "discord",
            1.0 if request.confidence is None else request.confidence,
        )

    @app.post("/api/discord/audio")
    async def discord_audio(request: Request) -> dict:
        if not app_config.stt.enabled:
            return {"ok": False, "error": "STT is disabled. Set GT7ENG_STT_ENABLED=true."}
        if stt is None:
            return {"ok": False, "error": stt_error or "STT is unavailable."}

        data, meta = await _read_audio_request(request)
        if not data:
            return {"ok": False, "error": "audio is required"}

        tmp_path = _write_temp_audio(data)
        try:
            result = await asyncio.to_thread(stt.transcribe, tmp_path)
        except STTUnavailableError as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            if not app_config.stt.keep_audio:
                tmp_path.unlink(missing_ok=True)

        command = await asyncio.to_thread(
            service.handle_transcript,
            result.text if result.text else "",
            "discord",
            result.confidence if result.text else 0.0,
        )
        return {
            "ok": True,
            "user_id": meta.get("user_id"),
            "started_at": meta.get("started_at"),
            "ended_at": meta.get("ended_at"),
            "transcript": result.text,
            "confidence": result.confidence,
            "language": result.language,
            "command": command,
        }

    @app.get("/api/discord/events")
    async def discord_events(after: int = 0) -> list[dict]:
        return service.alerts_after(after, speak_only=True)

    @app.post("/api/discord/bridge-status")
    async def discord_bridge_status(payload: dict[str, Any]) -> dict[str, bool]:
        bridge_manager.heartbeat.update(payload)
        return {"ok": True}

    @app.post("/api/discord/radio-check")
    async def radio_check() -> dict:
        return service.handle_command("radio check", "discord")

    @app.get("/discord/voice/jobs")
    async def discord_voice_jobs(limit: int = 1) -> dict:
        return {"jobs": service.next_voice_jobs(limit)}

    @app.post("/discord/voice/jobs/{job_id}/ack")
    async def discord_voice_job_ack(job_id: str, payload: dict[str, Any]) -> dict:
        service.acknowledge_voice_job(job_id, str(payload.get("status", "played")))
        return {"ok": True}

    @app.post("/discord/tts")
    async def discord_tts(request: Request, payload: dict[str, Any]) -> dict:
        text = str(payload.get("text", "")).strip()
        if not text:
            return {"error": "text is required"}
        try:
            audio_file = await asyncio.to_thread(tts.synthesize, text)
        except TTSUnavailableError as exc:
            return {"error": str(exc)}
        return {
            "audio_url": str(request.url_for("audio", filename=audio_file.name)),
            "audio_file": str(audio_file),
        }

    @app.get("/audio/{filename}")
    async def audio(filename: str):
        path = tts.cache_dir / filename
        return FileResponse(path)

    @app.post("/discord/engineer/mute")
    async def discord_mute(payload: dict[str, Any]) -> dict:
        service.set_muted(bool(payload.get("muted", False)))
        return {"ok": True, "muted": bool(payload.get("muted", False))}

    @app.post("/discord/mode")
    async def discord_mode(payload: dict[str, Any]) -> dict:
        mode = str(payload.get("mode", "quiet_driver"))
        service.set_voice_mode(mode)
        return {"ok": True, "mode": service.config.voice_mode}

    @app.websocket("/ws/hud")
    async def hud_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(service.status())
                await asyncio.sleep(1)
        except Exception:
            return

    return app


async def _read_audio_request(request) -> tuple[bytes, dict[str, str]]:
    content_type = request.headers.get("content-type", "")
    meta: dict[str, str] = {}
    if "multipart/form-data" in content_type:
        form = await request.form()
        for key in ["user_id", "started_at", "ended_at", "sample_rate", "channels"]:
            value = form.get(key)
            if value is not None:
                meta[key] = str(value)
        audio = form.get("audio")
        if hasattr(audio, "read"):
            return await audio.read(), meta
        if isinstance(audio, bytes):
            return audio, meta
        return b"", meta

    meta.update({key: value for key, value in request.query_params.items()})
    return await request.body(), meta


def _write_temp_audio(data: bytes) -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="gt7eng-stt-", suffix=".wav", delete=False)
    try:
        handle.write(data)
        return Path(handle.name)
    finally:
        handle.close()


def run_server(
    config: AppConfig,
    *,
    host: str,
    port: int,
    telemetry_mode: str,
    replay_file: Path | None = None,
) -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is required. Run `pip install -e .`.") from exc

    app = create_app(config, telemetry_mode=telemetry_mode, replay_file=replay_file)
    uvicorn.run(app, host=host, port=port)
