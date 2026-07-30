"""Ollama provider via the REST API (no SDK dependency, works offline).

Calls ``{base_url}/api/chat``. ``json_mode`` is emulated by asking the model
in the system prompt to reply with JSON only — Ollama has no native JSON mode.
"""

from __future__ import annotations

from typing import Any

import httpx

from .base import LLMError, LLMResponse, Message, to_dicts

_DEFAULT_MODEL = "llama3.1"


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str = "", temperature: float = 0.2, max_tokens: int = 2048):
        if not base_url:
            raise LLMError("Ollama provider requires a base URL")
        self._base_url = base_url.rstrip("/")
        self._model = model or _DEFAULT_MODEL
        self._temperature = temperature
        self._max_tokens = max_tokens

    def is_available(self) -> bool:
        try:
            httpx.get(f"{self._base_url}/api/tags", timeout=3.0)
            return True
        except Exception:  # noqa: BLE001
            return False

    def complete(
        self,
        messages: list[Message],
        *,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        msgs = to_dicts(messages)
        if system:
            msgs = [{"role": "system", "content": system}, *msgs]
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": msgs,
            "stream": False,
            "options": {
                "temperature": self._temperature if temperature is None else temperature,
                "num_predict": self._max_tokens if max_tokens is None else max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"
        try:
            r = httpx.post(f"{self._base_url}/api/chat", json=payload, timeout=120.0)
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"Ollama call failed: {e}") from e
        text = data.get("message", {}).get("content", "")
        usage = {
            "prompt": data.get("prompt_eval_count", 0),
            "completion": data.get("eval_count", 0),
        }
        return LLMResponse(text=text, provider=self.name, model=self._model, usage=usage, raw=data)
