import asyncio
from pathlib import Path
from typing import Any

from .config import AppConfig
from .service import RaceEngineerService
from .telemetry import GTTelemTelemetrySource, ReplayTelemetrySource
from .tts import MacSayTTS, TTSUnavailableError


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

    app_config = config or AppConfig.from_env()
    service = RaceEngineerService(app_config)
    tts = MacSayTTS()
    app = FastAPI(title="GT7 Race Engineer", version="0.1.0")
    static_dir = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.state.service = service

    @app.on_event("startup")
    async def startup() -> None:
        if telemetry_mode == "live":
            await service.start_source(GTTelemTelemetrySource(app_config))
        elif telemetry_mode == "replay" and replay_file:
            await service.start_source(ReplayTelemetrySource(replay_file, realtime=True))

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await service.stop_source()
        service.stop_capture()

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        return service.status()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/alerts")
    async def alerts(after: int = 0, speak_only: bool = False) -> list[dict]:
        return service.alerts_after(after, speak_only=speak_only)

    @app.post("/api/chat")
    async def chat(request: CommandRequest) -> dict:
        return service.handle_command(request.text, request.source)

    @app.post("/api/discord/transcript")
    async def discord_transcript(request: CommandRequest) -> dict:
        return service.handle_command(request.text, "discord")

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
            audio_file = tts.synthesize(text)
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
