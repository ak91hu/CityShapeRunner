"""Anthropic (Claude) provider. SDK is imported lazily."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from .base import LLMError, LLMResponse, Message, to_dicts

if TYPE_CHECKING:
    from anthropic.types import MessageParam

_DEFAULT_MODEL = "claude-3-5-sonnet-latest"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "", temperature: float = 0.2, max_tokens: int = 2048):
        if not api_key:
            raise LLMError("Anthropic provider requires an API key")
        try:
            from anthropic import Anthropic  # type: ignore
        except ImportError as e:
            raise LLMError("anthropic package not installed (pip install -e .[anthropic])") from e
        self._client = Anthropic(api_key=api_key)
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
        # The provider-neutral Message role is validated by the intent/prompt
        # pipeline before it reaches this adapter.
        msgs = cast("list[MessageParam]", to_dicts(messages))
        # Anthropic rejects a leading/standalone system role in messages; pass via system=.
        system_prompt = system or ""
        try:
            resp = self._client.messages.create(
                model=self._model,
                system=system_prompt,
                messages=msgs,
                temperature=self._temperature if temperature is None else temperature,
                max_tokens=self._max_tokens if max_tokens is None else max_tokens,
            )
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"Anthropic call failed: {e}") from e
        text_parts = [block.text for block in resp.content if block.type == "text"]
        text = "".join(text_parts)
        usage: dict[str, int] = {}
        if getattr(resp, "usage", None):
            usage = {"prompt": resp.usage.input_tokens, "completion": resp.usage.output_tokens}
        return LLMResponse(text=text, provider=self.name, model=self._model, usage=usage, raw=resp)
