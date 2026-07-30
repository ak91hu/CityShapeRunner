"""OpenAI provider (GPT-4o family). SDK is imported lazily."""

from __future__ import annotations

from typing import Any

from .base import LLMError, LLMResponse, Message, to_dicts

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str = "", temperature: float = 0.2, max_tokens: int = 2048):
        if not api_key:
            raise LLMError("OpenAI provider requires an API key")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise LLMError("openai package not installed (pip install -e .[openai])") from e
        self._client = OpenAI(api_key=api_key)
        self._model = model or _DEFAULT_MODEL
        self._temperature = temperature
        self._max_tokens = max_tokens

    def is_available(self) -> bool:
        return True

    def complete(
        self,
        messages: list[Message],
        *,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        msgs: list[dict[str, str]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(to_dicts(messages))
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": msgs,
            "temperature": self._temperature if temperature is None else temperature,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"OpenAI call failed: {e}") from e
        choice = resp.choices[0].message.content or ""
        usage = {}
        if getattr(resp, "usage", None):
            usage = {"prompt": resp.usage.prompt_tokens, "completion": resp.usage.completion_tokens}
        return LLMResponse(text=choice, provider=self.name, model=self._model, usage=usage, raw=resp)
