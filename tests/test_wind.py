from __future__ import annotations

import pytest

from gt7eng.config import WindConfig
from gt7eng.models import RaceSnapshot
from gt7eng.wind import HomeAssistantWindManager


def snapshot(**overrides) -> RaceSnapshot:
    data = {
        "connected": True,
        "session_phase": "racing",
        "speed_kph": 100.0,
    }
    data.update(overrides)
    return RaceSnapshot(**data)


class FakeWindClient:
    def __init__(self):
        self.levels: list[int] = []
        self.fail_next = False

    async def set_level(self, level: int) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("HA unavailable")
        self.levels.append(level)


def wind_config(**overrides) -> WindConfig:
    data = {
        "enabled": True,
        "ha_base_url": "http://ha.local:8123",
        "ha_token": "secret-token",
        "ha_entity_id": "number.zhimi_cpa4_cee4_favorite_level",
        "smoothing_seconds": 0.0,
    }
    data.update(overrides)
    return WindConfig(**data)


def manager_for(config: WindConfig, fake: FakeWindClient) -> HomeAssistantWindManager:
    return HomeAssistantWindManager(config, client_factory=lambda _config: fake)


def test_target_level_maps_speed_curve_and_clamps():
    manager = manager_for(wind_config(), FakeWindClient())

    assert manager.target_level(snapshot(speed_kph=0.0)) == 0
    assert manager.target_level(snapshot(speed_kph=9.9)) == 0
    assert manager.target_level(snapshot(speed_kph=10.0)) == 1
    assert manager.target_level(snapshot(speed_kph=100.0)) == 3
    assert manager.target_level(snapshot(speed_kph=280.0)) == 14
    assert manager.target_level(snapshot(speed_kph=400.0)) == 14
    assert manager.target_level(snapshot(connected=False, session_phase="stale")) == 0
    assert manager.target_level(snapshot(session_phase="paused")) == 0


@pytest.mark.asyncio
async def test_manager_sends_deduped_levels():
    fake = FakeWindClient()
    manager = manager_for(wind_config(), fake)

    manager.publish(snapshot(speed_kph=100.0))
    await manager.update_once(now=0.0)
    manager.publish(snapshot(speed_kph=200.0))
    await manager.update_once(now=0.25)
    await manager.update_once(now=0.5)
    manager.publish(snapshot(speed_kph=200.0))
    await manager.update_once(now=1.0)

    assert fake.levels == [3, 8]
    assert manager.status()["last_sent_level"] == 8
    assert manager.status()["commands_sent"] == 2


@pytest.mark.asyncio
async def test_manager_ramps_to_off_level_when_not_racing():
    fake = FakeWindClient()
    manager = manager_for(wind_config(), fake)

    manager.publish(snapshot(speed_kph=280.0))
    await manager.update_once(now=0.0)
    manager.publish(snapshot(session_phase="paused", speed_kph=280.0))
    await manager.update_once(now=0.5)

    assert fake.levels == [14, 0]
    assert manager.status()["target_level"] == 0


@pytest.mark.asyncio
async def test_manager_applies_smoothing_before_sending_large_changes():
    fake = FakeWindClient()
    config = wind_config(smoothing_seconds=1.0)
    manager = manager_for(config, fake)

    manager.publish(snapshot(speed_kph=280.0))
    await manager.update_once(now=0.0)
    await manager.update_once(now=0.5)

    assert fake.levels == [7, 10]
    assert manager.status()["target_level"] == 14


@pytest.mark.asyncio
async def test_manager_backs_off_after_home_assistant_error():
    fake = FakeWindClient()
    manager = manager_for(wind_config(), fake)
    fake.fail_next = True

    manager.publish(snapshot(speed_kph=100.0))
    await manager.update_once(now=0.0)
    await manager.update_once(now=0.5)
    await manager.update_once(now=1.1)

    assert fake.levels == [3]
    status = manager.status()
    assert status["connected"] is True
    assert status["last_error"] == ""


@pytest.mark.asyncio
async def test_unconfigured_manager_records_error_without_network_call():
    fake = FakeWindClient()
    manager = manager_for(wind_config(ha_token=""), fake)

    manager.publish(snapshot(speed_kph=100.0))
    await manager.update_once(now=0.0)

    assert fake.levels == []
    assert manager.status()["connected"] is False
    assert "not fully configured" in manager.status()["last_error"]
