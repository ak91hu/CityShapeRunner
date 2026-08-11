"""OpenCode Zen provider.

OpenCode Zen (https://opencode.ai/docs/zen) is an OpenAI-compatible gateway.
Models reachable via ``/v1/chat/completions`` include GLM, Kimi, DeepSeek,
MiniMax, and Grok. The OpenAI SDK is reused with a custom ``base_url``; the
SDK is imported lazily so the package imports without it.
"""

from __future__ import annotations

from typing import Any

from .base import LLMError, LLMResponse, Message, to_dicts

_DEFAULT_MODEL = "glm-5.2"
_DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"


class OpenCodeProvider:
    name = "opencode"

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        model: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ):
        if not api_key:
            raise LLMError("OpenCode Zen provider requires an API key")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise LLMError("openai package not installed (pip install -e .[opencode])") from e
        self._client = OpenAI(api_key=api_key, base_url=base_url or _DEFAULT_BASE_URL)
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
        json_schema: dict[str, Any] | None = None,
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
        # Zen is OpenAI-compatible, but schema support varies by upstream
        # model. Keep its portable JSON mode and let the application perform
        # the same executable validation used for every provider.
        if json_mode or json_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"OpenCode Zen call failed: {e}") from e
        choice = resp.choices[0].message.content or ""
        usage: dict[str, int] = {}
        if getattr(resp, "usage", None):
            usage = {"prompt": resp.usage.prompt_tokens, "completion": resp.usage.completion_tokens}
        return LLMResponse(text=choice, provider=self.name, model=self._model, usage=usage, raw=resp)
