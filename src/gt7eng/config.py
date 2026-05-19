from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

AlertCategory = Literal[
    "fuel",
    "pit",
    "lap",
    "position",
    "tires",
    "car",
    "system",
    "voice",
]
Verbosity = Literal["off", "critical", "balanced", "detailed"]
VoiceMode = Literal["wake_phrase", "quiet_driver"]


DEFAULT_VERBOSITY: dict[AlertCategory, Verbosity] = {
    "fuel": "balanced",
    "pit": "balanced",
    "lap": "balanced",
    "position": "balanced",
    "tires": "critical",
    "car": "critical",
    "system": "critical",
    "voice": "balanced",
}


PRESETS: dict[str, dict[AlertCategory, Verbosity]] = {
    "quick_race": {
        **DEFAULT_VERBOSITY,
        "fuel": "critical",
        "pit": "critical",
        "lap": "balanced",
        "position": "detailed",
    },
    "endurance": {
        **DEFAULT_VERBOSITY,
        "fuel": "detailed",
        "pit": "detailed",
        "lap": "balanced",
        "position": "balanced",
        "tires": "balanced",
        "car": "balanced",
    },
    "practice": {
        **DEFAULT_VERBOSITY,
        "fuel": "off",
        "pit": "off",
        "lap": "detailed",
        "position": "off",
        "tires": "balanced",
    },
    "custom": DEFAULT_VERBOSITY,
}


@dataclass(slots=True)
class LLMConfig:
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    timeout_seconds: float = 8.0
    max_tokens: int = 180


@dataclass(slots=True)
class DiscordConfig:
    api_url: str = "http://localhost:8765"
    driver_user_id: str = ""
    voice_channel_id: str = ""
    guild_id: str = ""


@dataclass(slots=True)
class AppConfig:
    preset: str = "endurance"
    ps_ip: str | None = None
    heartbeat_type: str = "B"
    fuel_safety_laps: float = 0.5
    stale_seconds: float = 3.0
    max_frame_buffer: int = 3_600
    voice_mode: VoiceMode = "quiet_driver"
    wake_phrase: str = "engineer"
    verbosity: dict[AlertCategory, Verbosity] = field(
        default_factory=lambda: dict(PRESETS["endurance"])
    )
    llm: LLMConfig = field(default_factory=LLMConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        preset = os.getenv("GT7ENG_PRESET", "endurance")
        verbosity = dict(PRESETS.get(preset, PRESETS["endurance"]))
        return cls(
            preset=preset,
            ps_ip=os.getenv("GT7ENG_PS_IP") or None,
            heartbeat_type=os.getenv("GT7ENG_HEARTBEAT", "B"),
            voice_mode=_voice_mode(os.getenv("GT7ENG_VOICE_MODE", "quiet_driver")),
            wake_phrase=os.getenv("GT7ENG_WAKE_PHRASE", "engineer").strip().lower(),
            verbosity=verbosity,
            llm=LLMConfig(
                base_url=os.getenv("GT7ENG_LLM_BASE_URL", ""),
                model=os.getenv("GT7ENG_LLM_MODEL", ""),
                api_key=os.getenv("GT7ENG_LLM_API_KEY", ""),
                timeout_seconds=float(os.getenv("GT7ENG_LLM_TIMEOUT", "8")),
                max_tokens=int(os.getenv("GT7ENG_LLM_MAX_TOKENS", "180")),
            ),
            discord=DiscordConfig(
                api_url=os.getenv("GT7ENG_API_URL", "http://localhost:8765"),
                driver_user_id=os.getenv("DISCORD_DRIVER_USER_ID", ""),
                voice_channel_id=os.getenv("DISCORD_VOICE_CHANNEL_ID", ""),
                guild_id=os.getenv("DISCORD_GUILD_ID", ""),
            ),
        )

    def set_preset(self, preset: str) -> None:
        self.preset = preset
        self.verbosity = dict(PRESETS.get(preset, PRESETS["endurance"]))

    def category_enabled(self, category: AlertCategory, minimum: Verbosity) -> bool:
        order = {"off": 0, "critical": 1, "balanced": 2, "detailed": 3}
        return order[self.verbosity.get(category, "off")] >= order[minimum]


def _voice_mode(value: str) -> VoiceMode:
    return "wake_phrase" if value == "wake_phrase" else "quiet_driver"
