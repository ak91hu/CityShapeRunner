"""Core LLM abstractions: messages, responses, the provider protocol, errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


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
        temperature: float | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
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
