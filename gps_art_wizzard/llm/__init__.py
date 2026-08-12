"""Provider-agnostic LLM interface.

Usage::

    from gps_art_wizzard.llm import get_llm
    llm = get_llm()                # picks the first available provider
    resp = llm.complete([{"role": "user", "content": "hi"}])
    print(resp.text)

If no provider is configured, ``get_llm`` raises :class:`NoProviderError` —
agents catch this and use their rule-based fallback.
"""

from __future__ import annotations

import json
from typing import Any

from .base import ImageInput, LLMError, LLMProvider, LLMResponse, Message, NoProviderError
from .factory import available_providers, get_llm, reset_sticky, try_complete

__all__ = [
    "LLMError",
    "ImageInput",
    "LLMProvider",
    "LLMResponse",
    "Message",
    "NoProviderError",
    "available_providers",
    "get_llm",
    "reset_sticky",
    "try_complete",
]


def extract_json(text: str) -> Any:
    """Best-effort extraction of a JSON object/array from an LLM string.

    Handles ```json fenced blocks and trailing prose.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if "```" in cleaned[3:] else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    # Find the first balanced { or [ ... matching close.
    for start_ch in ("{", "["):
        idx = cleaned.find(start_ch)
        if idx < 0:
            continue
        opener = cleaned[idx]
        closer = "}" if opener == "{" else "]"
        depth = 0
        for i, ch in enumerate(cleaned[idx:], start=idx):
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[idx : i + 1])
                    except json.JSONDecodeError:
                        break
    # Last resort: try the whole thing.
    return json.loads(cleaned)
