from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

AlertCategory = Literal[
    "fuel",
    "pit",
    "lap",
    "position",
    "tires",
    "incident",
    "driving",
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
    "incident": "balanced",
    "driving": "off",
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
        "incident": "balanced",
    },
    "endurance": {
        **DEFAULT_VERBOSITY,
        "fuel": "detailed",
        "pit": "detailed",
        "lap": "balanced",
        "position": "balanced",
        "tires": "balanced",
        "incident": "balanced",
        "car": "balanced",
    },
    "practice": {
        **DEFAULT_VERBOSITY,
        "fuel": "off",
        "pit": "off",
        "lap": "detailed",
        "position": "off",
        "tires": "balanced",
        "incident": "balanced",
        "driving": "detailed",
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
    disable_thinking: bool = False
    intent_repair_enabled: bool = True
    intent_repair_min_confidence: float = 0.55


@dataclass(slots=True)
class DiscordConfig:
    api_url: str = "http://localhost:8001"
    driver_user_id: str = ""
    voice_channel_id: str = ""
    guild_id: str = ""


@dataclass(slots=True)
class STTConfig:
    enabled: bool = False
    engine: str = "faster-whisper"
    model: str = "tiny.en"
    device: str = "auto"
    keep_audio: bool = False
    min_confidence: float = 0.55


@dataclass(slots=True)
class TTSConfig:
    engine: str = "auto"
    piper_model: str = ""
    radio_effects: bool = False
    cache_dir: str = "/private/tmp/gt7eng-tts"


@dataclass(slots=True)
class AppConfig:
    preset: str = "endurance"
    ps_ip: str | None = None
    heartbeat_type: str = "B"
    fuel_safety_laps: float = 0.5
    stale_seconds: float = 3.0
    position_coalesce_seconds: float = 1.5
    race_duration_minutes: float | None = None
    max_frame_buffer: int = 3_600
    voice_mode: VoiceMode = "quiet_driver"
    wake_phrase: str = "engineer"
    verbosity: dict[AlertCategory, Verbosity] = field(
        default_factory=lambda: dict(PRESETS["endurance"])
    )
    llm: LLMConfig = field(default_factory=LLMConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        preset = os.getenv("GT7ENG_PRESET", "endurance")
        verbosity = dict(PRESETS.get(preset, PRESETS["endurance"]))
        return cls(
            preset=preset,
            ps_ip=os.getenv("GT7ENG_PS_IP") or None,
            heartbeat_type=os.getenv("GT7ENG_HEARTBEAT", "B"),
            position_coalesce_seconds=float(
                os.getenv("GT7ENG_POSITION_COALESCE_SECONDS", "1.5")
            ),
            race_duration_minutes=_float_or_none(
                os.getenv("GT7ENG_RACE_DURATION_MINUTES")
            ),
            voice_mode=_voice_mode(os.getenv("GT7ENG_VOICE_MODE", "quiet_driver")),
            wake_phrase=os.getenv("GT7ENG_WAKE_PHRASE", "engineer").strip().lower(),
            verbosity=verbosity,
            llm=LLMConfig(
                base_url=os.getenv("GT7ENG_LLM_BASE_URL", ""),
                model=os.getenv("GT7ENG_LLM_MODEL", ""),
                api_key=os.getenv("GT7ENG_LLM_API_KEY", ""),
                timeout_seconds=float(os.getenv("GT7ENG_LLM_TIMEOUT", "8")),
                max_tokens=int(os.getenv("GT7ENG_LLM_MAX_TOKENS", "180")),
                disable_thinking=_bool(os.getenv("GT7ENG_LLM_DISABLE_THINKING"), False),
                intent_repair_enabled=_bool(
                    os.getenv("GT7ENG_LLM_INTENT_REPAIR"), True
                ),
                intent_repair_min_confidence=float(
                    os.getenv("GT7ENG_LLM_INTENT_REPAIR_MIN_CONFIDENCE", "0.55")
                ),
            ),
            discord=DiscordConfig(
                api_url=os.getenv("GT7ENG_API_URL", "http://localhost:8001"),
                driver_user_id=os.getenv("DISCORD_DRIVER_USER_ID", ""),
                voice_channel_id=os.getenv("DISCORD_VOICE_CHANNEL_ID", ""),
                guild_id=os.getenv("DISCORD_GUILD_ID", ""),
            ),
            stt=STTConfig(
                enabled=_bool(os.getenv("GT7ENG_STT_ENABLED"), False),
                engine=os.getenv("GT7ENG_STT_ENGINE", "faster-whisper"),
                model=os.getenv("GT7ENG_STT_MODEL", "tiny.en"),
                device=os.getenv("GT7ENG_STT_DEVICE", "auto"),
                keep_audio=_bool(os.getenv("GT7ENG_KEEP_AUDIO"), False),
                min_confidence=float(os.getenv("GT7ENG_STT_MIN_CONFIDENCE", "0.55")),
            ),
            tts=TTSConfig(
                engine=os.getenv("GT7ENG_TTS_ENGINE", "auto"),
                piper_model=os.getenv("GT7ENG_PIPER_MODEL", ""),
                radio_effects=_bool(os.getenv("GT7ENG_RADIO_EFFECTS"), False),
                cache_dir=os.getenv("GT7ENG_TTS_CACHE_DIR", "/private/tmp/gt7eng-tts"),
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


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float_or_none(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def load_env_file(path: str | os.PathLike[str] = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
