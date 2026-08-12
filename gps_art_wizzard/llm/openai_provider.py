"""OpenAI provider (GPT-4o family). SDK is imported lazily."""

from __future__ import annotations

from typing import Any

from .base import ImageInput, LLMError, LLMResponse, Message, to_dicts, to_responses_input

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
        json_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
        images: list[ImageInput] | None = None,
    ) -> LLMResponse:
        if images:
            return self._complete_with_images(
                messages,
                images=images,
                json_mode=json_mode,
                json_schema=json_schema,
                max_tokens=max_tokens,
                system=system,
            )
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
        if json_schema is not None and _supports_structured_outputs(self._model):
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "gps_art_structured_response",
                    "strict": True,
                    "schema": json_schema,
                },
            }
        elif json_mode or json_schema is not None:
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

    def _complete_with_images(
        self,
        messages: list[Message],
        *,
        images: list[ImageInput],
        json_mode: bool,
        json_schema: dict[str, Any] | None,
        max_tokens: int | None,
        system: str | None,
    ) -> LLMResponse:
        inputs = to_responses_input(messages, images)
        if system:
            inputs.insert(0, {"role": "system", "content": system})
        kwargs: dict[str, Any] = {
            "model": self._model,
            "input": inputs,
            "max_output_tokens": self._max_tokens if max_tokens is None else max_tokens,
        }
        if json_schema is not None and _supports_structured_outputs(self._model):
            kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "gps_art_visual_verification",
                    "strict": True,
                    "schema": json_schema,
                }
            }
        elif json_mode or json_schema is not None:
            kwargs["text"] = {"format": {"type": "json_object"}}
        try:
            resp = self._client.responses.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"OpenAI vision call failed: {exc}") from exc
        status = getattr(resp, "status", None)
        choice = getattr(resp, "output_text", "") or ""
        if status == "incomplete" or not choice.strip():
            raise LLMError("OpenAI vision response was incomplete or empty")
        raw_usage = getattr(resp, "usage", None)
        usage = (
            {
                "prompt": int(getattr(raw_usage, "input_tokens", 0) or 0),
                "completion": int(getattr(raw_usage, "output_tokens", 0) or 0),
            }
            if raw_usage is not None
            else {}
        )
        return LLMResponse(choice, self.name, self._model, usage, resp)


def _supports_structured_outputs(model: str) -> bool:
    """Use strict schemas only for documented modern OpenAI model families."""
    normalized = model.casefold()
    return normalized.startswith(("gpt-4o", "gpt-4.1", "gpt-5", "o1", "o3", "o4"))
