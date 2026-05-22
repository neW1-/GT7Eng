from pathlib import Path
from types import SimpleNamespace

from gt7eng.config import STTConfig
from gt7eng.stt import FasterWhisperSTT


def test_faster_whisper_retries_short_commands_without_vad():
    calls = []

    class FakeModel:
        def transcribe(self, _path, **kwargs):
            calls.append(kwargs)
            info = SimpleNamespace(language="en")
            if kwargs["vad_filter"]:
                return [], info
            return [SimpleNamespace(text=" fuel level ", avg_logprob=-0.1)], info

    stt = FasterWhisperSTT.__new__(FasterWhisperSTT)
    stt.config = STTConfig()
    stt._model = FakeModel()

    result = stt.transcribe(Path("unused.wav"))

    assert result.text == "fuel level"
    assert result.confidence == 0.9
    assert [call["vad_filter"] for call in calls] == [True, False]
    assert calls[0]["language"] == "en"
    assert "fuel level" in calls[0]["initial_prompt"]
