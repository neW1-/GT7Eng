from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


class TTSUnavailableError(RuntimeError):
    pass


class MacSayTTS:
    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path("/private/tmp/gt7eng-tts")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def synthesize(self, text: str) -> Path:
        if not shutil.which("say"):
            raise TTSUnavailableError("macOS `say` command is not available.")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        path = self.cache_dir / f"{digest}.aiff"
        if path.exists():
            return path
        subprocess.run(
            ["say", "-o", str(path), text],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return path
