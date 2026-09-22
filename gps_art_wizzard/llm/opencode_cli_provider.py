"""Zero-cost OpenCode transport through a local headless OpenCode server.

OpenCode's free models reject direct Console API use.  The official headless
server is therefore run beside the web application and accessed only over the
container loopback interface.  Free models currently do not provide reliable
image understanding, so image calls fail closed and the application uses its
deterministic visual/geometry fallback instead.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .base import ImageInput, LLMError, LLMResponse, Message, to_dicts

_DEFAULT_FREE_MODEL = "muse-spark-1.3-contributor-free"


class OpenCodeCLIProvider:
    """Provider adapter for ``opencode serve`` using a cost-zero model."""

    name = "opencode"
    supports_images = False

    def __init__(
        self,
        server_url: str,
        model: str = "",
        max_tokens: int = 2048,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._model = model.strip() or _DEFAULT_FREE_MODEL
        self._max_tokens = max_tokens
        self._client = client or httpx.Client(timeout=60.0)

    def is_available(self) -> bool:
        try:
            response = self._client.get(
                f"{self._server_url}/global/health",
                timeout=1.5,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

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
        del temperature  # OpenCode owns sampling for the hosted free model.
        if images:
            raise LLMError(
                "OpenCode free model image inputs unavailable; use deterministic review"
            )

        output_limit = self._max_tokens if max_tokens is None else max_tokens
        prompt = _prompt_text(
            messages,
            json_mode=json_mode,
            json_schema=json_schema,
            output_limit=output_limit,
        )
        session_id: str | None = None
        try:
            session_response = self._client.post(
                f"{self._server_url}/session",
                json={"title": "GPS Art structured request"},
                timeout=5.0,
            )
            session_response.raise_for_status()
            session_id = str(session_response.json()["id"])
            response = self._client.post(
                f"{self._server_url}/session/{session_id}/message",
                json={
                    "model": {
                        "providerID": "opencode",
                        "modelID": self._model,
                    },
                    "agent": "plan",
                    "system": system or "Return only the requested result.",
                    "parts": [{"type": "text", "text": prompt}],
                },
                timeout=60.0,
            )
            response.raise_for_status()
            payload = response.json()
            info = payload.get("info") or {}
            if info.get("error"):
                error_data = info["error"].get("data") or {}
                message = error_data.get("message") or info["error"].get("name")
                raise LLMError(f"OpenCode free-model call failed: {message}")
            text = "".join(
                str(part.get("text") or "")
                for part in payload.get("parts") or []
                if part.get("type") == "text"
            ).strip()
            if not text:
                raise LLMError("OpenCode free-model response was empty")
            raw_tokens = info.get("tokens") or {}
            usage = {
                "prompt": int(raw_tokens.get("input", 0) or 0),
                "completion": int(raw_tokens.get("output", 0) or 0),
            }
            return LLMResponse(
                text=text,
                provider=self.name,
                model=self._model,
                usage=usage,
                raw=payload,
            )
        except LLMError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMError(f"OpenCode local server call failed: {error}") from error
        finally:
            if session_id is not None:
                try:
                    self._client.delete(
                        f"{self._server_url}/session/{session_id}",
                        timeout=3.0,
                    )
                except httpx.HTTPError:
                    pass


def _prompt_text(
    messages: list[Message],
    *,
    json_mode: bool,
    json_schema: dict[str, Any] | None,
    output_limit: int,
) -> str:
    sections = [
        f"{message['role'].upper()}: {message['content']}"
        for message in to_dicts(messages)
    ]
    if json_schema is not None:
        sections.extend(
            (
                "Return exactly one JSON value with no markdown or commentary.",
                "It must satisfy this JSON Schema:",
                json.dumps(json_schema, ensure_ascii=False, separators=(",", ":")),
            )
        )
    elif json_mode:
        sections.append("Return exactly one valid JSON value with no markdown or commentary.")
    sections.append(f"Keep the complete response within {output_limit} output tokens.")
    return "\n\n".join(sections)
