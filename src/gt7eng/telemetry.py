from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import AsyncIterator, Protocol

from .config import AppConfig
from .models import TelemetryFrame


class TelemetrySource(Protocol):
    async def frames(self) -> AsyncIterator[TelemetryFrame]:
        ...


class ReplayTelemetrySource:
    def __init__(self, path: Path, realtime: bool = False):
        self.path = path
        self.realtime = realtime

    async def frames(self) -> AsyncIterator[TelemetryFrame]:
        previous_timestamp: float | None = None
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                frame = TelemetryFrame.from_dict(json.loads(line))
                if self.realtime and previous_timestamp is not None:
                    await asyncio.sleep(max(0.0, frame.timestamp - previous_timestamp))
                previous_timestamp = frame.timestamp
                yield frame


class GTTelemTelemetrySource:
    def __init__(self, config: AppConfig):
        self.config = config
        self._client = None
        self._queue: asyncio.Queue[TelemetryFrame] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def frames(self) -> AsyncIterator[TelemetryFrame]:
        try:
            from gt_telem import TurismoClient  # type: ignore
        except ImportError as exc:
            raise RuntimeError("gt-telem is not installed. Run `pip install -e .`.") from exc

        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=4)
        self._client = TurismoClient(
            ps_ip=self.config.ps_ip,
            heartbeat_type=self.config.heartbeat_type,
            max_callback_workers=2,
        )
        self._client.register_callback(GTTelemTelemetrySource._receive, [self])
        self._client.start()
        try:
            while True:
                yield await self._queue.get()
        finally:
            self._client.stop()

    @staticmethod
    def _receive(telemetry, context: "GTTelemTelemetrySource") -> None:
        frame = TelemetryFrame.from_gt_telem(telemetry)
        queue = context._queue
        loop = context._loop
        if queue is None or loop is None:
            return

        def enqueue() -> None:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(frame)

        loop.call_soon_threadsafe(enqueue)


class CaptureWriter:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def write(self, frame: TelemetryFrame) -> None:
        self._handle.write(frame.to_json() + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def synthetic_frame(**overrides) -> TelemetryFrame:
    now = overrides.pop("timestamp", time.time())
    data = {
        "timestamp": now,
        "source": "synthetic",
        "packet_id": 1,
        "speed_kph": 100.0,
        "engine_rpm": 7000.0,
        "current_gear": 3,
        "throttle": 80,
        "brake": 0,
        "current_lap": 1,
        "total_laps": 5,
        "last_lap_time_ms": -1,
        "best_lap_time_ms": -1,
        "current_position": 4,
        "total_cars": 16,
        "fuel_level": 80.0,
        "fuel_capacity": 100.0,
        "cars_on_track": True,
    }
    data.update(overrides)
    return TelemetryFrame.from_dict(data)
