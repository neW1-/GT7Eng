from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import shutil
import socket
import sys
from pathlib import Path

from .config import AppConfig, load_env_file
from .models import RaceSnapshot
from .pixel_display import PixelDisplayRenderer
from .server import run_server
from .service import RaceEngineerService
from .telemetry import CaptureWriter, GTTelemTelemetrySource, ReplayTelemetrySource


def main(argv: list[str] | None = None) -> int:
    load_env_file()

    parser = argparse.ArgumentParser(prog="gt7eng")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_parser = sub.add_parser("doctor", help="Check local setup.")
    doctor_parser.add_argument("--skip-ps", action="store_true")

    run_parser = sub.add_parser("run", help="Run the race engineer service and HUD.")
    run_parser.add_argument("--host", default=os.getenv("GT7ENG_HOST", "0.0.0.0"))
    run_parser.add_argument(
        "--port", type=int, default=int(os.getenv("GT7ENG_PORT", "8001"))
    )
    run_parser.add_argument("--telemetry", choices=["live", "none", "replay"], default="live")
    run_parser.add_argument("--replay-file", type=Path)

    replay_parser = sub.add_parser("replay", help="Replay a captured JSONL telemetry file.")
    replay_parser.add_argument("file", type=Path)
    replay_parser.add_argument("--realtime", action="store_true")

    capture_parser = sub.add_parser("capture", help="Capture live telemetry to JSONL.")
    capture_parser.add_argument("file", type=Path)

    preview_parser = sub.add_parser(
        "pixel-preview",
        help="Render a hardware-free pixel display preview PNG.",
    )
    preview_parser.add_argument("output", type=Path)
    preview_parser.add_argument("--gear", type=int, default=3)
    preview_parser.add_argument("--suggested-gear", type=int)
    preview_parser.add_argument("--rpm-percent", type=float, default=0.85)
    preview_parser.add_argument("--rpm", type=float)
    preview_parser.add_argument("--min-alert-rpm", type=float)
    preview_parser.add_argument("--max-alert-rpm", type=float)
    preview_parser.add_argument("--fuel-percent", type=float)
    preview_parser.add_argument("--shift", action="store_true")
    preview_parser.add_argument("--rev-limit", action="store_true")
    preview_parser.add_argument("--idle", action="store_true")
    preview_parser.add_argument("--width", type=int, default=64)
    preview_parser.add_argument("--height", type=int, default=64)
    preview_parser.add_argument(
        "--theme",
        choices=["simdt_blue", "warm_amber", "race_gyr", "custom"],
    )
    preview_parser.add_argument("--rev-position", choices=["top", "bottom"])

    args = parser.parse_args(argv)
    config = AppConfig.from_env()

    if args.command == "doctor":
        return _doctor(config, skip_ps=args.skip_ps)
    if args.command == "run":
        run_server(
            config,
            host=args.host,
            port=args.port,
            telemetry_mode=args.telemetry,
            replay_file=args.replay_file,
        )
        return 0
    if args.command == "replay":
        return asyncio.run(_replay(config, args.file, args.realtime))
    if args.command == "capture":
        return asyncio.run(_capture(config, args.file))
    if args.command == "pixel-preview":
        return _pixel_preview(
            config,
            args.output,
            gear=args.gear,
            suggested_gear=args.suggested_gear,
            rpm_percent=args.rpm_percent,
            rpm=args.rpm,
            min_alert_rpm=args.min_alert_rpm,
            max_alert_rpm=args.max_alert_rpm,
            fuel_percent=args.fuel_percent,
            shift=args.shift,
            rev_limit=args.rev_limit,
            idle=args.idle,
            width=args.width,
            height=args.height,
            theme=args.theme,
            rev_position=args.rev_position,
        )
    return 1


def _doctor(config: AppConfig, *, skip_ps: bool) -> int:
    checks = {
        "gt-telem": importlib.util.find_spec("gt_telem") is not None,
        "fastapi": importlib.util.find_spec("fastapi") is not None,
        "uvicorn": importlib.util.find_spec("uvicorn") is not None,
        "python-multipart": importlib.util.find_spec("multipart") is not None,
        "node": shutil.which("node") is not None,
        "npm": shutil.which("npm") is not None,
    }
    for name, ok in checks.items():
        print(f"{name:10} {'ok' if ok else 'missing'}")

    if config.llm.base_url:
        print(f"llm        configured: {config.llm.base_url} ({config.llm.model or 'no model'})")
    else:
        print("llm        not configured")

    print(f"udp 33740  {'bind ok' if _udp_bind_ok(33740) else 'unavailable'}")
    print(
        "discord   "
        + (
            f"configured channel={config.discord.voice_channel_id or 'not set'} "
            f"driver={config.discord.driver_user_id or 'not set'}"
            if config.discord.guild_id or config.discord.voice_channel_id
            else "not configured"
        )
    )
    print(
        f"tts        engine={config.tts.engine} "
        f"say={'ok' if shutil.which('say') else 'missing'} "
        f"piper_model={config.tts.piper_model or 'not set'}"
    )
    print(
        f"stt        {'enabled' if config.stt.enabled else 'disabled'} "
        f"engine={config.stt.engine} "
        f"model={config.stt.model} "
        f"package={'ok' if importlib.util.find_spec('faster_whisper') else 'missing'}"
    )
    pixel_ok = _doctor_pixel_display(config)
    wind_ok = _doctor_wind(config)

    if not skip_ps and checks["gt-telem"]:
        try:
            from gt_telem.net.device_discover import get_ps_ip_type  # type: ignore

            ip, ps_type = get_ps_ip_type()
            if ip:
                print(f"ps5        discovered {ps_type or 'PlayStation'} at {ip}")
            else:
                print("ps5        not discovered; manual GT7ENG_PS_IP can be used")
        except Exception as exc:
            print(f"ps5        discovery failed: {exc}")
    elif config.ps_ip:
        print(f"ps5        manual fallback configured: {config.ps_ip}")

    return 0 if all(checks.values()) and pixel_ok and wind_ok else 1


def _udp_bind_ok(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


async def _replay(config: AppConfig, path: Path, realtime: bool) -> int:
    service = RaceEngineerService(config)
    source = ReplayTelemetrySource(path, realtime=realtime)
    async for frame in source.frames():
        alerts = service.update_frame(frame)
        for alert in alerts:
            print(f"[{alert.category}] {alert.message}")
    snapshot = service.snapshot
    print(snapshot.to_dict())
    return 0


async def _capture(config: AppConfig, path: Path) -> int:
    service = RaceEngineerService(config)
    service.start_capture(CaptureWriter(path))
    source = GTTelemTelemetrySource(config)
    try:
        async for frame in source.frames():
            service.update_frame(frame)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop_capture()
    return 0


def _doctor_pixel_display(config: AppConfig) -> bool:
    pixel = config.pixel_display
    package_ok = importlib.util.find_spec("pypixelcolor") is not None
    if not pixel.enabled:
        print(
            f"pixel      disabled package={'ok' if package_ok else 'missing'} "
            f"theme={pixel.color_theme} layout={pixel.gear_layout} "
            f"scale={pixel.rev_scale} shift={pixel.shift_mode} "
            f"fuel={'on' if pixel.fuel_enabled else 'off'}"
        )
        return True
    if not pixel.address:
        print(
            f"pixel      enabled package={'ok' if package_ok else 'missing'} "
            f"address=missing fuel={'on' if pixel.fuel_enabled else 'off'}"
        )
        return False
    if not package_ok:
        print(
            "pixel      enabled package=missing "
            f"fuel={'on' if pixel.fuel_enabled else 'off'} "
            "install with: pip install -e '.[pixel-display]'"
        )
        return False
    try:
        info = asyncio.run(_pixel_display_probe(pixel.address))
    except Exception as exc:
        print(f"pixel      connection failed: {exc}")
        return False
    print(
        f"pixel      connected render={pixel.width}x{pixel.height} "
        f"reported={getattr(info, 'width', '?')}x{getattr(info, 'height', '?')} "
        f"theme={pixel.color_theme} layout={pixel.gear_layout} rev={pixel.rev_position} "
        f"scale={pixel.rev_scale} shift={pixel.shift_mode} "
        f"fuel={'on' if pixel.fuel_enabled else 'off'}"
    )
    return True


def _doctor_wind(config: AppConfig) -> bool:
    wind = config.wind
    if not wind.enabled:
        print(
            f"wind       disabled entity={wind.ha_entity_id} "
            f"off={wind.off_level} active={wind.min_active_level}-{wind.max_level} "
            f"update_hz={wind.update_hz:g}"
        )
        return True

    missing = []
    if not wind.ha_base_url:
        missing.append("base_url")
    if not wind.ha_token:
        missing.append("token")
    if not wind.ha_entity_id:
        missing.append("entity_id")
    if missing:
        print(f"wind       enabled missing={','.join(missing)}")
        return False

    print(
        f"wind       enabled base_url={wind.ha_base_url} entity={wind.ha_entity_id} "
        f"off={wind.off_level} active={wind.min_active_level}-{wind.max_level} "
        f"update_hz={wind.update_hz:g}"
    )
    return True


async def _pixel_display_probe(address: str):
    import pypixelcolor

    client = pypixelcolor.AsyncClient(address)
    try:
        await client.connect()
        return client.get_device_info()
    finally:
        await client.disconnect()


def _pixel_preview(
    config: AppConfig,
    output: Path,
    *,
    gear: int,
    rpm_percent: float,
    suggested_gear: int | None = None,
    rpm: float | None = None,
    min_alert_rpm: float | None = None,
    max_alert_rpm: float | None = None,
    fuel_percent: float | None = None,
    shift: bool = False,
    rev_limit: bool = False,
    idle: bool = False,
    width: int = 64,
    height: int = 64,
    theme: str | None = None,
    rev_position: str | None = None,
) -> int:
    if theme is not None:
        config.pixel_display.color_theme = theme  # type: ignore[assignment]
    if rev_position is not None:
        config.pixel_display.rev_position = rev_position  # type: ignore[assignment]
    if fuel_percent is not None:
        config.pixel_display.fuel_enabled = True
    renderer = PixelDisplayRenderer(config.pixel_display, width=width, height=height)
    if idle:
        snapshot = RaceSnapshot(connected=False, session_phase="stale")
    else:
        full_rpm = max_alert_rpm if max_alert_rpm is not None else 100.0
        start_rpm = _preview_start_rpm(
            config.pixel_display.rev_scale,
            config.pixel_display.rev_start_percent,
            full_rpm,
            min_alert_rpm,
        )
        engine_rpm = rpm
        if engine_rpm is None:
            percent = max(0.0, min(1.0, rpm_percent))
            engine_rpm = start_rpm + percent * (full_rpm - start_rpm)
        snapshot = RaceSnapshot(
            connected=True,
            session_phase="racing",
            engine_rpm=engine_rpm,
            min_alert_rpm=min_alert_rpm if min_alert_rpm is not None else start_rpm,
            max_alert_rpm=full_rpm,
            current_gear=gear,
            suggested_gear=suggested_gear,
            fuel_level=fuel_percent,
            rev_limit=shift or rev_limit,
        )
    frame = renderer.render_snapshot(snapshot)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(frame.to_png())
    print(f"pixel preview written: {output}")
    return 0


def _preview_start_rpm(
    rev_scale: str,
    rev_start_percent: float,
    full_rpm: float,
    min_alert_rpm: float | None,
) -> float:
    if rev_scale == "wide":
        return full_rpm * rev_start_percent
    return min_alert_rpm if min_alert_rpm is not None else 0.0


if __name__ == "__main__":
    sys.exit(main())
