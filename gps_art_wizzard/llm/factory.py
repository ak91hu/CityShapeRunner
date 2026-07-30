"""LLM factory: pick the first available provider and fall back on errors.

The chosen provider is *sticky* for the rest of the process so the pipeline
stays coherent (one agent's prompts won't flip providers mid-run).
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from ..config import LLMConfig, get_settings
from .base import LLMError, LLMProvider, NoProviderError

log = logging.getLogger(__name__)

# Module-level cache of the sticky provider chosen on first success.
_STICKY: LLMProvider | None = None
_UNAVAILABLE_UNTIL: dict[str, float] = {}
_PROBE_COOLDOWN_S = 30.0


def _probe_in_cooldown(provider_name: str) -> bool:
    retry_at = _UNAVAILABLE_UNTIL.get(provider_name)
    if retry_at is None:
        return False
    if retry_at <= time.monotonic():
        _UNAVAILABLE_UNTIL.pop(provider_name, None)
        return False
    return True


def _build(cfg: LLMConfig) -> list[LLMProvider]:
    """Instantiate every provider that *could* work, in fallback order."""
    candidates: list[LLMProvider] = []

    def add(name: str):
        try:
            if name == "opencode" and cfg.opencode_key:
                from .opencode_provider import OpenCodeProvider
                candidates.append(
                    OpenCodeProvider(
                        cfg.opencode_key, cfg.opencode_base_url, cfg.model, cfg.temperature, cfg.max_tokens
                    )
                )
            elif name == "openai" and cfg.openai_key:
                from .openai_provider import OpenAIProvider
                candidates.append(OpenAIProvider(cfg.openai_key, cfg.model, cfg.temperature, cfg.max_tokens))
            elif name == "anthropic" and cfg.anthropic_key:
                from .anthropic_provider import AnthropicProvider
                candidates.append(AnthropicProvider(cfg.anthropic_key, cfg.model, cfg.temperature, cfg.max_tokens))
            elif name == "ollama" and cfg.ollama_base_url:
                from .ollama_provider import OllamaProvider
                candidates.append(OllamaProvider(cfg.ollama_base_url, cfg.model, cfg.temperature, cfg.max_tokens))
        except LLMError as e:
            log.debug("provider %s unavailable: %s", name, e)

    for name in _provider_order(cfg):
        add(name)
    return candidates


def _provider_order(cfg: LLMConfig) -> list[str]:
    """Return a de-duplicated order with an explicit provider first.

    ``LLM_PROVIDER=auto`` follows ``LLM_FALLBACK`` unchanged. Selecting a
    provider prioritises it without disabling the configured fallbacks.
    """
    requested = cfg.provider.strip().lower()
    configured = [name.strip().lower() for name in cfg.fallback_order if name.strip()]
    ordered = configured if requested in {"", "auto"} else [requested, *configured]
    return list(dict.fromkeys(ordered))


@lru_cache(maxsize=1)
def available_providers() -> tuple[LLMProvider, ...]:
    return tuple(_build(get_settings().llm))


def get_llm() -> LLMProvider:
    """Return the sticky provider, building/trying candidates lazily.

    Raises :class:`NoProviderError` if none are configured.
    """
    global _STICKY
    if _STICKY is not None:
        return _STICKY

    for provider in available_providers():
        if _probe_in_cooldown(provider.name):
            continue
        if provider.is_available():
            _STICKY = provider
            log.info("LLM provider selected: %s", provider.name)
            return provider
        _UNAVAILABLE_UNTIL[provider.name] = time.monotonic() + _PROBE_COOLDOWN_S

    raise NoProviderError(
        "No LLM provider available. Set OPENCODE_API_KEY (Zen) / OPENAI_API_KEY / ANTHROPIC_API_KEY "
        "or run Ollama. Agents will use their deterministic fallbacks."
    )


def reset_sticky() -> None:
    """Reset provider health/stickiness state (mainly for tests)."""
    global _STICKY
    _STICKY = None
    _UNAVAILABLE_UNTIL.clear()


def try_complete(fallback_fn, **kwargs):
    """Run an LLM call with provider fallback.

    Tries the sticky provider; on :class:`LLMError` rotates to the next
    candidate. If all fail (or none configured), calls ``fallback_fn()``
    so the agent can degrade gracefully.
    """
    global _STICKY
    providers = list(available_providers())
    # If a sticky provider exists, try it first, then the rest.
    if _STICKY is not None and _STICKY in providers:
        providers.remove(_STICKY)
        providers.insert(0, _STICKY)

    last_err: Exception | None = None
    attempted = 0
    for provider in providers:
        if _probe_in_cooldown(provider.name):
            continue
        if not provider.is_available():
            _UNAVAILABLE_UNTIL[provider.name] = time.monotonic() + _PROBE_COOLDOWN_S
            continue
        attempted += 1
        try:
            resp = provider.complete(**kwargs)
            _STICKY = provider  # pin on success
            return resp
        except LLMError as e:
            last_err = e
            _UNAVAILABLE_UNTIL[provider.name] = time.monotonic() + _PROBE_COOLDOWN_S
            log.warning("provider %s failed (%s); trying next", provider.name, e)
            continue

    if attempted == 0:
        log.info("no reachable LLM provider — using deterministic fallback")
    else:
        log.warning("all LLM providers failed (%s) — using deterministic fallback", last_err)
    return fallback_fn()
