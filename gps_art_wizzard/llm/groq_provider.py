"""Groq text completions using the existing HTTP client dependency."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..workflow_runtime import publish_llm_call
from .base import ImageInput, LLMError, LLMResponse, Message, to_dicts


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, model: str, temperature: float, max_tokens: int):
        if not api_key:
            raise LLMError("Groq provider requires an API key")
        self._client = httpx.Client(
            base_url="https://api.groq.com/openai/v1/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        self._model = model or "openai/gpt-oss-120b"
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
            raise LLMError("Groq text model: image inputs unavailable")
        instruction = system or ""
        if json_schema is not None:
            instruction += "\nReturn only a JSON object matching this schema:\n" + json.dumps(json_schema)
        elif json_mode:
            instruction += "\nReturn only a JSON object."
        msgs = ([{"role": "system", "content": instruction}] if instruction else [])
        msgs.extend(to_dicts(messages))
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": msgs,
            "temperature": self._temperature if temperature is None else temperature,
            "max_completion_tokens": self._max_tokens if max_tokens is None else max_tokens,
        }
        if json_mode or json_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        try:
            publish_llm_call(self.name, self._model)
            response = self._client.post("chat/completions", json=payload)
            response.raise_for_status()
            raw = response.json()
            choice = raw["choices"][0]
            content = choice["message"]["content"]
            if choice.get("finish_reason") != "stop" or not isinstance(content, str) or not content.strip():
                raise LLMError("Groq response was incomplete or empty")
            usage = raw.get("usage") or {}
            return LLMResponse(content, self.name, self._model, {
                "prompt": int(usage.get("prompt_tokens", 0)),
                "completion": int(usage.get("completion_tokens", 0)),
            }, raw)
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"Groq call failed: HTTP {exc.response.status_code}") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("Groq call timed out") from exc
        except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMError("Groq call failed: transport or invalid response") from exc
