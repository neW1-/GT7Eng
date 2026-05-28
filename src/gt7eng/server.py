import asyncio
import tempfile
from pathlib import Path
from typing import Any

from .config import AppConfig
from .service import RaceEngineerService
from .stt import STTUnavailableError, create_stt
from .telemetry import GTTelemTelemetrySource, ReplayTelemetrySource
from .tts import TTSUnavailableError, create_tts


def create_app(
    config: AppConfig | None = None,
    *,
    telemetry_mode: str = "none",
    replay_file: Path | None = None,
):
    try:
        from fastapi import FastAPI, Request, WebSocket
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

    @app.on_event("startup")
    async def startup() -> None:
        await service.start_pixel_display()
        if telemetry_mode == "live":
            await service.start_source(GTTelemTelemetrySource(app_config))
        elif telemetry_mode == "replay" and replay_file:
            await service.start_source(ReplayTelemetrySource(replay_file, realtime=True))

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await service.stop_source()
        await service.stop_pixel_display()
        service.stop_capture()

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        payload = service.status()
        payload["audio"] = {
            "tts": tts.status(),
            "stt": stt.status() if stt is not None else {
                "enabled": app_config.stt.enabled,
                "engine": app_config.stt.engine,
                "ready": False,
                "error": stt_error,
            },
        }
        return payload

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
