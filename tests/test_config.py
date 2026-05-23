import os

from gt7eng.config import load_env_file
from gt7eng.config import AppConfig


def test_load_env_file_sets_missing_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "GT7ENG_LLM_MODEL=Qwen3.5-9B-OptiQ-4bit",
                'GT7ENG_LLM_BASE_URL="http://127.0.0.1:8000/v1"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("GT7ENG_LLM_MODEL", raising=False)
    monkeypatch.delenv("GT7ENG_LLM_BASE_URL", raising=False)

    load_env_file(env_file)

    assert os.environ["GT7ENG_LLM_MODEL"] == "Qwen3.5-9B-OptiQ-4bit"
    assert os.environ["GT7ENG_LLM_BASE_URL"] == "http://127.0.0.1:8000/v1"


def test_load_env_file_does_not_override_environment(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GT7ENG_LLM_MODEL=from-file", encoding="utf-8")
    monkeypatch.setenv("GT7ENG_LLM_MODEL", "from-shell")

    load_env_file(env_file)

    assert os.environ["GT7ENG_LLM_MODEL"] == "from-shell"


def test_llm_disable_thinking_env(monkeypatch):
    monkeypatch.setenv("GT7ENG_LLM_DISABLE_THINKING", "true")

    config = AppConfig.from_env()

    assert config.llm.disable_thinking is True


def test_voice_mode_env_accepts_quiet_driver_ai(monkeypatch):
    monkeypatch.setenv("GT7ENG_VOICE_MODE", "quiet_driver_ai")

    config = AppConfig.from_env()

    assert config.voice_mode == "quiet_driver_ai"


def test_unknown_voice_mode_env_falls_back_to_quiet_driver(monkeypatch):
    monkeypatch.setenv("GT7ENG_VOICE_MODE", "wake_word")

    config = AppConfig.from_env()

    assert config.voice_mode == "quiet_driver"
