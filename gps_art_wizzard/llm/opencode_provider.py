"""OpenCode Zen provider.

OpenCode Zen (https://opencode.ai/docs/zen) is an OpenAI-compatible gateway.
Models reachable via ``/v1/chat/completions`` include GLM, Kimi, DeepSeek,
MiniMax, and Grok. The OpenAI SDK is reused with a custom ``base_url``; the
SDK is imported lazily so the package imports without it.
"""

from __future__ import annotations

from typing import Any

from .base import ImageInput, LLMError, LLMResponse, Message, to_dicts, to_responses_input

_DEFAULT_MODEL = "glm-5.2"
_DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
_DEFAULT_STRUCTURED_MODEL = "gpt-5.4-mini"
_STRUCTURED_TIMEOUT_S = 30.0
_LARGE_STRUCTURED_TIMEOUT_S = 45.0
_MAX_STRUCTURED_RETRY_TOKENS = 16_384


def _is_timeout_error(error: Exception) -> bool:
    message = str(error).casefold()
    return isinstance(error, TimeoutError) or "timed out" in message or "timeout" in message


class OpenCodeProvider:
    name = "opencode"

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        model: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        *,
        structured_model: str = _DEFAULT_STRUCTURED_MODEL,
    ):
        if not api_key:
            raise LLMError("OpenCode Zen provider requires an API key")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise LLMError("openai package not installed (pip install -e .[opencode])") from e
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url or _DEFAULT_BASE_URL,
            timeout=30.0,
            max_retries=0,
        )
        self._model = model or _DEFAULT_MODEL
        self._structured_model = structured_model.strip()
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
        msgs: list[dict[str, Any]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(to_responses_input(messages, images) if images else to_dicts(messages))

        # Zen exposes current OpenAI models through /v1/responses. Its
        # OpenAI-compatible chat models accept JSON mode, but reasoning models
        # may spend the complete output budget on prose before emitting JSON.
        # A Responses model with strict text.format keeps structured agent
        # calls bounded and makes malformed/truncated geometry exceptional.
        if (json_schema is not None or images) and self._structured_model:
            return self._complete_structured(
                msgs,
                json_schema=json_schema,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )

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

    def _complete_structured(
        self,
        messages: list[dict[str, Any]],
        *,
        json_schema: dict[str, Any] | None,
        max_tokens: int | None,
        json_mode: bool = False,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._structured_model,
            "input": messages,
            "max_output_tokens": self._max_tokens if max_tokens is None else max_tokens,
            # Geometry/repair schemas are much larger than intent or review
            # JSON. Give only those calls a little more transport time; the
            # workflow call/deadline budgets still bound the complete run.
            "timeout": (
                _LARGE_STRUCTURED_TIMEOUT_S
                if (self._max_tokens if max_tokens is None else max_tokens) > 4096
                else _STRUCTURED_TIMEOUT_S
            ),
        }
        if json_schema is not None:
            kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "gps_art_structured_response",
                    "strict": True,
                    "schema": json_schema,
                }
            }
        elif json_mode:
            kwargs["text"] = {"format": {"type": "json_object"}}
        if self._structured_model.casefold().startswith("gpt-5"):
            kwargs["reasoning"] = {"effort": "low"}
        timeout_retried = False

        def create_response():
            nonlocal timeout_retried
            try:
                return self._client.responses.create(**kwargs)
            except Exception as error:  # noqa: BLE001
                if timeout_retried or not _is_timeout_error(error):
                    raise
                # A single transport timeout does not establish provider
                # unavailability. Retry this exact strict-schema request once
                # with the larger bounded timeout; factory-level provider
                # rotation remains available if the second attempt also fails.
                timeout_retried = True
                kwargs["timeout"] = _LARGE_STRUCTURED_TIMEOUT_S
                return self._client.responses.create(**kwargs)

        try:
            resp = create_response()
            status = getattr(resp, "status", None)
            details = getattr(resp, "incomplete_details", None)
            reason = getattr(details, "reason", "unknown")
            output_budget = int(kwargs["max_output_tokens"])
            if (
                status == "incomplete"
                and reason == "max_output_tokens"
                and output_budget < _MAX_STRUCTURED_RETRY_TOKENS
            ):
                kwargs["max_output_tokens"] = min(
                    _MAX_STRUCTURED_RETRY_TOKENS,
                    output_budget * 2,
                )
                kwargs["timeout"] = _LARGE_STRUCTURED_TIMEOUT_S
                resp = create_response()
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"OpenCode Zen structured call failed: {e}") from e

        status = getattr(resp, "status", None)
        choice = getattr(resp, "output_text", "") or ""
        if status == "incomplete":
            details = getattr(resp, "incomplete_details", None)
            reason = getattr(details, "reason", "unknown")
            raise LLMError(f"OpenCode Zen structured response was incomplete: {reason}")
        if not choice.strip():
            raise LLMError("OpenCode Zen structured response was empty")

        usage: dict[str, int] = {}
        raw_usage = getattr(resp, "usage", None)
        if raw_usage is not None:
            usage = {
                "prompt": int(getattr(raw_usage, "input_tokens", 0) or 0),
                "completion": int(getattr(raw_usage, "output_tokens", 0) or 0),
            }
        return LLMResponse(
            text=choice,
            provider=self.name,
            model=self._structured_model,
            usage=usage,
            raw=resp,
        )
