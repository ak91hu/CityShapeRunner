"""Anthropic (Claude) provider. SDK is imported lazily."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from .base import ImageInput, LLMError, LLMResponse, Message, decode_data_url, to_dicts

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
        json_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
        images: list[ImageInput] | None = None,
    ) -> LLMResponse:
        # The provider-neutral Message role is validated by the intent/prompt
        # pipeline before it reaches this adapter.
        raw_messages: list[dict[str, Any]] = to_dicts(messages)
        if images:
            target = next(
                (i for i in range(len(raw_messages) - 1, -1, -1) if raw_messages[i]["role"] == "user"),
                None,
            )
            if target is None:
                target = len(raw_messages)
                raw_messages.append({"role": "user", "content": "Review the supplied image."})
            blocks: list[dict[str, Any]] = [
                {"type": "text", "text": raw_messages[target]["content"]}
            ]
            for image in images:
                media_type, data = decode_data_url(image.data_url)
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    }
                )
            raw_messages[target] = {"role": "user", "content": blocks}
        msgs = cast("list[MessageParam]", raw_messages)
        # Anthropic rejects a leading/standalone system role in messages; pass via system=.
        system_prompt = system or ""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "system": system_prompt,
            "messages": msgs,
            "temperature": self._temperature if temperature is None else temperature,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
        }
        # Anthropic structured outputs are available only on documented newer
        # model families. Older/custom models retain prompt-level JSON plus the
        # application's provider-independent parser and geometry validation.
        if json_schema is not None and _supports_structured_outputs(self._model):
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": json_schema}
            }
        try:
            resp = self._client.messages.create(
                **kwargs,
            )
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"Anthropic call failed: {e}") from e
        text_parts = [block.text for block in resp.content if block.type == "text"]
        text = "".join(text_parts)
        usage: dict[str, int] = {}
        if getattr(resp, "usage", None):
            usage = {"prompt": resp.usage.input_tokens, "completion": resp.usage.output_tokens}
        return LLMResponse(text=text, provider=self.name, model=self._model, usage=usage, raw=resp)


def _supports_structured_outputs(model: str) -> bool:
    """Conservatively gate Anthropic's model-specific JSON-schema feature."""
    normalized = model.casefold()
    if not normalized.startswith("claude-"):
        return False
    if re.search(r"-(?:opus|sonnet|haiku)-4-[5-9](?:-|$)", normalized):
        return True
    return bool(re.search(r"-(?:fable|mythos|opus|sonnet|haiku)-[5-9](?:-|$)", normalized))
