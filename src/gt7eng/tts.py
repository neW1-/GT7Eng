from __future__ import annotations

import hashlib
import math
import shutil
import subprocess
import wave
from pathlib import Path

from .config import TTSConfig


class TTSUnavailableError(RuntimeError):
    pass


class MacSayTTS:
    engine = "say"

    def __init__(self, cache_dir: Path | str | None = None):
        self.cache_dir = Path(cache_dir or "/private/tmp/gt7eng-tts")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def synthesize(self, text: str) -> Path:
        if not shutil.which("say"):
            raise TTSUnavailableError("macOS `say` command is not available.")
        path = self.cache_dir / f"say-{_digest(text)}.aiff"
        if path.exists():
            return path
        subprocess.run(
            ["say", "-o", str(path), text],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return path

    def status(self) -> dict:
        return {"engine": self.engine, "ready": shutil.which("say") is not None}


class PiperTTS:
    engine = "piper"

    def __init__(self, model_path: str, cache_dir: Path | str | None = None):
        if not model_path:
            raise TTSUnavailableError("GT7ENG_PIPER_MODEL is required for Piper TTS.")
        self.model_path = Path(model_path)
        self.cache_dir = Path(cache_dir or "/private/tmp/gt7eng-tts")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def synthesize(self, text: str) -> Path:
        path = self.cache_dir / f"piper-{_digest(text)}.wav"
        if path.exists():
            return path
        if shutil.which("piper"):
            subprocess.run(
                ["piper", "--model", str(self.model_path), "--output_file", str(path)],
                input=text,
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return path
        try:
            from piper.voice import PiperVoice  # type: ignore
        except ImportError as exc:
            raise TTSUnavailableError(
                "Piper is not installed and the `piper` CLI is not available."
            ) from exc
        voice = PiperVoice.load(str(self.model_path))
        with wave.open(str(path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        return path

    def status(self) -> dict:
        python_package = _module_available("piper.voice")
        return {
            "engine": self.engine,
            "ready": self.model_path.exists()
            and (shutil.which("piper") is not None or python_package),
            "model": str(self.model_path),
        }


class RadioTTSWrapper:
    def __init__(self, base):
        self.base = base
        self.engine = f"{base.engine}+radio"
        self.cache_dir = base.cache_dir

    def synthesize(self, text: str) -> Path:
        source = self.base.synthesize(text)
        if source.suffix.lower() != ".wav":
            return source
        path = self.cache_dir / f"radio-{_digest(text)}.wav"
        if path.exists():
            return path
        try:
            _wrap_wav_with_tones(source, path)
        except (wave.Error, OSError):
            return source
        return path

    def status(self) -> dict:
        data = self.base.status()
        data["engine"] = self.engine
        data["radio_effects"] = True
        return data


def create_tts(config: TTSConfig):
    if config.engine == "piper":
        base = PiperTTS(config.piper_model, config.cache_dir)
    elif config.engine == "auto" and config.piper_model:
        try:
            base = PiperTTS(config.piper_model, config.cache_dir)
        except TTSUnavailableError:
            base = MacSayTTS(config.cache_dir)
    else:
        base = MacSayTTS(config.cache_dir)
    return RadioTTSWrapper(base) if config.radio_effects else base


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _wrap_wav_with_tones(source: Path, target: Path) -> None:
    with wave.open(str(source), "rb") as src:
        params = src.getparams()
        if params.sampwidth != 2:
            raise wave.Error("Only 16-bit WAV radio wrapping is supported.")
        frames = src.readframes(params.nframes)

    start = _tone(params.framerate, params.nchannels, 880, 0.09)
    end = _tone(params.framerate, params.nchannels, 420, 0.08)
    gap = b"\x00" * int(params.framerate * params.nchannels * params.sampwidth * 0.035)
    with wave.open(str(target), "wb") as dst:
        dst.setparams(params)
        dst.writeframes(start + gap + frames + gap + end)


def _tone(sample_rate: int, channels: int, frequency: int, duration_seconds: float) -> bytes:
    samples = int(sample_rate * duration_seconds)
    out = bytearray()
    for i in range(samples):
        amplitude = math.sin((2 * math.pi * frequency * i) / sample_rate) * 0.22
        value = int(max(-1.0, min(1.0, amplitude)) * 32767)
        frame = value.to_bytes(2, "little", signed=True)
        out.extend(frame * channels)
    return bytes(out)
