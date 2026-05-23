import json

from gt7eng.config import LLMConfig
from gt7eng.llm import OpenAICompatibleClient
from gt7eng.models import RaceSnapshot


def test_ask_includes_request_context():
    client = OpenAICompatibleClient(
        LLMConfig(base_url="http://127.0.0.1:8000/v1", model="test-model")
    )
    captured = {}

    def fake_request(payload):
        captured["payload"] = payload
        return "ok"

    client._request_chat_completion = fake_request

    assert client.ask("what is the current date", RaceSnapshot()) == "ok"

    user_content = json.loads(captured["payload"]["messages"][1]["content"])
    assert user_content["question"] == "what is the current date"
    assert user_content["request_context"]["current_date"]
    assert user_content["request_context"]["current_time"]
