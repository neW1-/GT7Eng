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
VoiceMode = Literal["wake_phrase", "quiet_driver", "quiet_driver_ai"]
PixelRevPosition = Literal["top", "bottom"]
PixelColorTheme = Literal["simdt_blue", "warm_amber", "race_gyr", "custom"]


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
class PixelDisplayConfig:
    enabled: bool = False
    address: str = ""
    update_hz: float = 10.0
    rev_position: PixelRevPosition = "bottom"
    brightness: int = 60
    dim_brightness: int = 12
    orientation: int = 0
    shift_percent: float = 0.96
    flash_hz: float = 8.0
    color_theme: PixelColorTheme = "simdt_blue"
    gear_color: str = ""
    rev_low_color: str = ""
    rev_mid_color: str = ""
    rev_high_color: str = ""
    shift_color: str = ""
    rpm_min: float | None = None
    rpm_max: float | None = None


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
    pixel_display: PixelDisplayConfig = field(default_factory=PixelDisplayConfig)

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
            pixel_display=PixelDisplayConfig(
                enabled=_bool(os.getenv("GT7ENG_PIXEL_DISPLAY_ENABLED"), False),
                address=os.getenv("GT7ENG_PIXEL_DISPLAY_ADDRESS", "").strip(),
                update_hz=_float_range(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_UPDATE_HZ"), 10.0, 1.0, 30.0
                ),
                rev_position=_rev_position(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_REV_POSITION", "bottom")
                ),
                brightness=_int_range(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_BRIGHTNESS"), 60, 0, 100
                ),
                dim_brightness=_int_range(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_DIM_BRIGHTNESS"), 12, 0, 100
                ),
                orientation=_int_range(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_ORIENTATION"), 0, 0, 3
                ),
                shift_percent=_float_range(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_SHIFT_PERCENT"), 0.96, 0.0, 1.0
                ),
                flash_hz=_float_range(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_FLASH_HZ"), 8.0, 1.0, 20.0
                ),
                color_theme=_color_theme(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_COLOR_THEME", "simdt_blue")
                ),
                gear_color=_hex_color_or_empty(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_GEAR_COLOR")
                ),
                rev_low_color=_hex_color_or_empty(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_REV_LOW_COLOR")
                ),
                rev_mid_color=_hex_color_or_empty(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_REV_MID_COLOR")
                ),
                rev_high_color=_hex_color_or_empty(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_REV_HIGH_COLOR")
                ),
                shift_color=_hex_color_or_empty(
                    os.getenv("GT7ENG_PIXEL_DISPLAY_SHIFT_COLOR")
                ),
                rpm_min=_float_or_none(os.getenv("GT7ENG_PIXEL_DISPLAY_RPM_MIN")),
                rpm_max=_float_or_none(os.getenv("GT7ENG_PIXEL_DISPLAY_RPM_MAX")),
            ),
        )

    def set_preset(self, preset: str) -> None:
        self.preset = preset
        self.verbosity = dict(PRESETS.get(preset, PRESETS["endurance"]))

    def category_enabled(self, category: AlertCategory, minimum: Verbosity) -> bool:
        order = {"off": 0, "critical": 1, "balanced": 2, "detailed": 3}
        return order[self.verbosity.get(category, "off")] >= order[minimum]


def _voice_mode(value: str) -> VoiceMode:
    if value in {"wake_phrase", "quiet_driver_ai"}:
        return value
    return "quiet_driver"


def _rev_position(value: str) -> PixelRevPosition:
    if value.strip().lower() == "top":
        return "top"
    return "bottom"


def _color_theme(value: str) -> PixelColorTheme:
    normalized = value.strip().lower()
    if normalized in {"warm_amber", "race_gyr", "custom"}:
        return normalized  # type: ignore[return-value]
    return "simdt_blue"


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


def _float_range(value: str | None, default: float, minimum: float, maximum: float) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    if parsed < minimum or parsed > maximum:
        return default
    return parsed


def _int_range(value: str | None, default: int, minimum: int, maximum: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed < minimum or parsed > maximum:
        return default
    return parsed


def _hex_color_or_empty(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.strip().lstrip("#").lower()
    if len(normalized) != 6:
        return ""
    if any(ch not in "0123456789abcdef" for ch in normalized):
        return ""
    return normalized


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
