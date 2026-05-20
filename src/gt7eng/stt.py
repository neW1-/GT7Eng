from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import STTConfig


class STTUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class STTResult:
    text: str
    confidence: float = 1.0
    language: str | None = None


class DisabledSTT:
    def __init__(self, config: STTConfig):
        self.config = config

    def transcribe(self, path: Path) -> STTResult:
        raise STTUnavailableError("STT is disabled. Set GT7ENG_STT_ENABLED=true.")

    def status(self) -> dict:
        return {"enabled": False, "engine": self.config.engine, "ready": False}


class FasterWhisperSTT:
    def __init__(self, config: STTConfig):
        self.config = config
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:
            raise STTUnavailableError(
                "faster-whisper is not installed. Install gt7eng with the voice extra."
            ) from exc

        device = "auto" if config.device == "auto" else config.device
        self._model = WhisperModel(config.model, device=device, compute_type="int8")

    def transcribe(self, path: Path) -> STTResult:
        segments, info = self._model.transcribe(
            str(path),
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        parts: list[str] = []
        confidences: list[float] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                parts.append(text)
            avg_logprob = getattr(segment, "avg_logprob", None)
            if avg_logprob is not None:
                confidences.append(max(0.0, min(1.0, 1.0 + float(avg_logprob))))
        confidence = sum(confidences) / len(confidences) if confidences else 1.0
        return STTResult(
            text=" ".join(parts).strip(),
            confidence=confidence,
            language=getattr(info, "language", None),
        )

    def status(self) -> dict:
        return {
            "enabled": True,
            "engine": "faster-whisper",
            "model": self.config.model,
            "device": self.config.device,
            "ready": True,
        }


def create_stt(config: STTConfig):
    if not config.enabled:
        return DisabledSTT(config)
    if config.engine != "faster-whisper":
        raise STTUnavailableError(f"Unsupported STT engine: {config.engine}")
    return FasterWhisperSTT(config)
