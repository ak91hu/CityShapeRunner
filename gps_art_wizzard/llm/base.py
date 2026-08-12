"""Core LLM abstractions: messages, responses, the provider protocol, errors."""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class ImageInput:
    """Provider-neutral inline image supplied to a multimodal LLM call."""

    data_url: str
    detail: str = "auto"


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


class LLMError(Exception):
    """Raised when an LLM call fails (network, auth, rate limit, bad output)."""


class NoProviderError(LLMError):
    """Raised when no LLM provider is configured and a fallback is unavailable."""


@runtime_checkable
class LLMProvider(Protocol):
    """Every provider implements this surface. Agents depend only on it."""

    name: str

    def is_available(self) -> bool: ...

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
    ) -> LLMResponse: ...


def to_dicts(messages: list) -> list[dict[str, str]]:
    """Normalise a list of ``Message`` or plain dicts to role/content dicts."""
    out: list[dict[str, str]] = []
    for m in messages:
        if isinstance(m, dict):
            out.append({"role": m["role"], "content": m["content"]})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def to_responses_input(
    messages: list,
    images: list[ImageInput] | None = None,
) -> list[dict[str, Any]]:
    """Build Responses-style messages and attach images to the final user turn."""

    out: list[dict[str, Any]] = list(to_dicts(messages))
    if not images:
        return out
    target = next(
        (index for index in range(len(out) - 1, -1, -1) if out[index]["role"] == "user"),
        None,
    )
    blocks: list[dict[str, Any]] = []
    if target is None:
        target = len(out)
        out.append({"role": "user", "content": "Review the supplied image."})
    text = out[target]["content"]
    blocks.append({"type": "input_text", "text": text})
    blocks.extend(
        {
            "type": "input_image",
            "image_url": image.data_url,
            "detail": image.detail,
        }
        for image in images
    )
    out[target] = {"role": "user", "content": blocks}
    return out


_DATA_URL = re.compile(r"^data:([^;,]+);base64,(.+)$", re.DOTALL)


def decode_data_url(data_url: str) -> tuple[str, str]:
    """Return ``(media_type, base64_payload)`` after validating an inline image."""

    match = _DATA_URL.match(data_url)
    if not match:
        raise LLMError("image input must be a base64 data URL")
    media_type, payload = match.groups()
    if not media_type.startswith("image/"):
        raise LLMError("data URL must contain an image")
    try:
        base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise LLMError("image input contains invalid base64 data") from exc
    return media_type, payload
