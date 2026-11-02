"""LLM factory: pick the first available provider and fall back on errors.

The chosen provider is *sticky* within the request context so the pipeline
stays coherent (one agent's prompts won't flip providers mid-run).
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache

from ..config import LLMConfig, get_settings
from ..workflow_runtime import active_workflow_runtime
from .base import LLMError, LLMProvider, NoProviderError

log = logging.getLogger(__name__)

_STICKY: ContextVar[LLMProvider | None] = ContextVar("llm_provider", default=None)
_GROQ_VISITOR: ContextVar[bool] = ContextVar("groq_visitor", default=False)
_UNAVAILABLE_UNTIL: dict[str, float] = {}
_PROBE_COOLDOWN_S = 30.0


@contextmanager
def visitor_scope(visitor_id: str):
    """Split browsers evenly between OpenCode and Groq across requests/replicas."""
    cohort_token = _GROQ_VISITOR.set(int(visitor_id, 16) % 2 == 0)
    sticky_token = _STICKY.set(None)
    try:
        yield
    finally:
        _STICKY.reset(sticky_token)
        _GROQ_VISITOR.reset(cohort_token)


def _request_providers() -> list[LLMProvider]:
    providers = [
        provider for provider in available_providers()
        if provider.name != "groq" or _GROQ_VISITOR.get()
    ]
    if _GROQ_VISITOR.get():
        providers.sort(key=lambda provider: provider.name != "groq")
    return providers


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
    provider_order = _provider_order(cfg)
    if cfg.groq_key and "groq" not in provider_order:
        provider_order.append("groq")
    primary_provider = provider_order[0] if provider_order else ""

    def model_for(name: str) -> str:
        explicit = {
            "opencode": cfg.opencode_model,
            "openai": cfg.openai_model,
            "anthropic": cfg.anthropic_model,
            "ollama": cfg.ollama_model,
            "groq": cfg.groq_model,
        }[name]
        if explicit:
            return explicit
        return cfg.model if name == primary_provider else ""

    def add(name: str):
        try:
            if name == "opencode" and cfg.opencode_key:
                if cfg.opencode_transport == "cli":
                    if not cfg.opencode_server_autostart:
                        return
                    from .opencode_cli_provider import OpenCodeCLIProvider
                    candidates.append(
                        OpenCodeCLIProvider(
                            cfg.opencode_server_url,
                            model_for("opencode"),
                            cfg.max_tokens,
                        )
                    )
                else:
                    from .opencode_provider import OpenCodeProvider
                    candidates.append(
                        OpenCodeProvider(
                            cfg.opencode_key,
                            cfg.opencode_base_url,
                            model_for("opencode"),
                            cfg.temperature,
                            cfg.max_tokens,
                            structured_model=cfg.opencode_structured_model,
                        )
                    )
            elif name == "openai" and cfg.openai_key:
                from .openai_provider import OpenAIProvider
                candidates.append(OpenAIProvider(cfg.openai_key, model_for("openai"), cfg.temperature, cfg.max_tokens))
            elif name == "anthropic" and cfg.anthropic_key:
                from .anthropic_provider import AnthropicProvider
                candidates.append(AnthropicProvider(cfg.anthropic_key, model_for("anthropic"), cfg.temperature, cfg.max_tokens))
            elif name == "ollama" and cfg.ollama_base_url:
                from .ollama_provider import OllamaProvider
                candidates.append(OllamaProvider(cfg.ollama_base_url, model_for("ollama"), cfg.temperature, cfg.max_tokens))
            elif name == "groq" and cfg.groq_key:
                from .groq_provider import GroqProvider
                candidates.append(GroqProvider(cfg.groq_key, cfg.groq_model, cfg.temperature, cfg.max_tokens))
        except LLMError as e:
            log.debug("provider %s unavailable: %s", name, e)

    for name in provider_order:
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
    sticky = _STICKY.get()
    if sticky is not None:
        return sticky

    for provider in _request_providers():
        if _probe_in_cooldown(provider.name):
            continue
        if provider.is_available():
            _STICKY.set(provider)
            log.info("LLM provider selected: %s", provider.name)
            return provider
        _UNAVAILABLE_UNTIL[provider.name] = time.monotonic() + _PROBE_COOLDOWN_S

    raise NoProviderError(
        "No LLM provider available. Set OPENCODE_API_KEY (Zen) / GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY "
        "or run Ollama. Agents will use their deterministic fallbacks."
    )


def reset_sticky() -> None:
    """Reset provider health/stickiness state (mainly for tests)."""
    _STICKY.set(None)
    _UNAVAILABLE_UNTIL.clear()


def try_complete(
    fallback_fn,
    *,
    exclude_provider: str | None = None,
    pin_provider: bool = True,
    max_provider_attempts: int | None = None,
    **kwargs,
):
    """Run an LLM call with provider fallback.

    Tries the sticky provider; on :class:`LLMError` rotates to the next
    candidate. If all fail (or none configured), calls ``fallback_fn()``
    so the agent can degrade gracefully.
    """
    providers = [
        provider
        for provider in _request_providers()
        if provider.name != exclude_provider
        and not (provider.name == "groq" and kwargs.get("images"))
    ]
    # If a sticky provider exists, try it first, then the rest.
    sticky = _STICKY.get()
    if sticky is not None and sticky in providers:
        providers.remove(sticky)
        providers.insert(0, sticky)

    last_err: Exception | None = None
    attempted = 0
    budget_reason: str | None = None
    runtime = active_workflow_runtime()
    for provider in providers:
        if max_provider_attempts is not None and attempted >= max_provider_attempts:
            break
        if _probe_in_cooldown(provider.name):
            continue
        if runtime is not None:
            allowed, budget_reason = runtime.llm_budget_status()
            if not allowed:
                break
        if not provider.is_available():
            _UNAVAILABLE_UNTIL[provider.name] = time.monotonic() + _PROBE_COOLDOWN_S
            continue
        if runtime is not None:
            allowed, budget_reason = runtime.reserve_llm_attempt(provider.name)
            if not allowed:
                break
        attempted += 1
        try:
            resp = provider.complete(**kwargs)
            if runtime is not None:
                runtime.record_llm_success(resp.usage)
            if pin_provider:
                _STICKY.set(provider)  # pin the primary generation provider only
            return resp
        except LLMError as e:
            last_err = e
            # Structured truncation and a single request timeout both prove
            # that provider discovery succeeded. The adapter already performs
            # one bounded same-call retry; do not poison unrelated subsequent
            # stages with a reachability cooldown for these response-level
            # failures.
            error_text = str(e).casefold()
            response_level_failure = (
                "incomplete: max_output_tokens" in error_text
                or "timed out" in error_text
                or "timeout" in error_text
            )
            if not response_level_failure:
                _UNAVAILABLE_UNTIL[provider.name] = time.monotonic() + _PROBE_COOLDOWN_S
            log.warning("provider %s failed (%s); trying next", provider.name, e)
            continue

    if budget_reason is not None:
        fallback_reason = budget_reason
        log.warning(
            "LLM workflow budget unavailable (%s) — using deterministic fallback",
            budget_reason,
        )
    elif attempted == 0:
        fallback_reason = "no_provider"
        log.info("no reachable LLM provider — using deterministic fallback")
    else:
        fallback_reason = "provider_failure"
        log.warning("all LLM providers failed (%s) — using deterministic fallback", last_err)
    if runtime is not None:
        runtime.record_deterministic_fallback(fallback_reason)
    return fallback_fn()
