from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import LLMConfig
from .models import RaceSnapshot


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    def available(self) -> bool:
        return bool(self.config.base_url and self.config.model)

    def ask(self, question: str, snapshot: RaceSnapshot) -> str:
        if not self.available():
            return "LLM is not configured. I can still answer core race commands."

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a concise GT7 race engineer. Answer only from the "
                        "provided race_state. If data is unavailable, say it is "
                        "unavailable. Do not invent opponent gaps, nearby car data, "
                        "weather, tire wear, or strategy facts not present."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "race_state": snapshot.to_dict(),
                            "question": question,
                        },
                        separators=(",", ":"),
                    ),
                },
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": 0.2,
        }
        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return f"LLM request failed: {exc}"

        try:
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            return "LLM response was not in OpenAI-compatible format."
        return content[:800]

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers
