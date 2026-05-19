import asyncio
from pathlib import Path

from gt7eng.config import AppConfig
from gt7eng.service import RaceEngineerService
from gt7eng.telemetry import ReplayTelemetrySource


def test_replay_source_drives_service():
    async def run():
        service = RaceEngineerService(AppConfig())
        source = ReplayTelemetrySource(Path("tests/fixtures/simple_race.jsonl"))
        async for frame in source.frames():
            service.update_frame(frame)
        return service.snapshot

    snapshot = asyncio.run(run())
    assert snapshot.current_lap == 3
    assert snapshot.current_position == 3
    assert len(snapshot.lap_history) == 2
    assert snapshot.fuel_per_lap == 10.0
