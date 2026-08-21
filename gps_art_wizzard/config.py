"""Configuration loaded from environment + ``config/settings.yaml``.

Provider-agnostic by design: no LLM key is required for the package to import.
Agents fall back to deterministic, rule-based behaviour when no provider is
available, so the pipeline can be exercised end-to-end offline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_YAML = ROOT / "config" / "settings.yaml"


@dataclass
class LLMConfig:
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "auto"))
    fallback_order: list[str] = field(default_factory=lambda: _split_env("LLM_FALLBACK", ["opencode", "anthropic", "openai", "ollama"]))
    temperature: float = field(default_factory=lambda: _float("LLM_TEMPERATURE", 0.2))
    max_tokens: int = field(default_factory=lambda: _int("LLM_MAX_TOKENS", 2048))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    opencode_model: str = field(default_factory=lambda: os.getenv("OPENCODE_MODEL", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", ""))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", ""))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", ""))
    opencode_key: str = field(default_factory=lambda: os.getenv("OPENCODE_API_KEY", ""))
    opencode_base_url: str = field(default_factory=lambda: os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1"))
    opencode_structured_model: str = field(
        default_factory=lambda: os.getenv(
            "OPENCODE_STRUCTURED_MODEL",
            "gpt-5.4-mini",
        )
    )
    openai_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))

    @property
    def has_any_provider(self) -> bool:
        return bool(self.opencode_key or self.openai_key or self.anthropic_key or self.ollama_base_url)


@dataclass
class RoutingConfig:
    ors_api_key: str = field(default_factory=lambda: os.getenv("ORS_API_KEY", ""))
    ors_base_url: str = field(
        default_factory=lambda: os.getenv(
            "ORS_BASE_URL",
            "https://api.heigit.org/openrouteservice",
        )
    )
    snap_radius_m: int = field(default_factory=lambda: _int("ORS_SNAP_RADIUS_M", 120))
    # GPS-art cusps and lettering often require U-turns at via-points.
    continue_straight: bool = field(
        default_factory=lambda: _bool("ORS_CONTINUE_STRAIGHT", False)
    )
    preference: str = field(
        default_factory=lambda: os.getenv("ORS_PREFERENCE", "recommended")
    )


@dataclass
class GeocoderConfig:
    nominatim_base_url: str = field(default_factory=lambda: os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"))
    nominatim_email: str = field(default_factory=lambda: os.getenv("NOMINATIM_EMAIL", ""))


@dataclass
class WorkflowConfig:
    max_refinement_iterations: int = field(default_factory=lambda: _int("MAX_REFINEMENT_ITERATIONS", 6))
    validation_score_threshold: float = field(default_factory=lambda: _float("VALIDATION_SCORE_THRESHOLD", 0.72))
    min_shape_fidelity: float = 0.7
    preflight_enabled: bool = field(
        default_factory=lambda: _bool("PREFLIGHT_ENABLED", True)
    )
    preflight_max_placements: int = field(
        default_factory=lambda: _int("PREFLIGHT_MAX_PLACEMENTS", 180)
    )
    preflight_shortlist: int = field(
        default_factory=lambda: _int("PREFLIGHT_SHORTLIST", 7)
    )
    preflight_guide_points: int = field(
        default_factory=lambda: _int("PREFLIGHT_GUIDE_POINTS", 18)
    )
    ai_shape_verifier_enabled: bool = field(
        default_factory=lambda: _bool("AI_SHAPE_VERIFIER_ENABLED", True)
    )
    ai_shape_min_semantic_score: float = field(
        default_factory=lambda: _float("AI_SHAPE_MIN_SEMANTIC_SCORE", 0.68)
    )
    ai_shape_max_candidates: int = field(
        default_factory=lambda: _int("AI_SHAPE_MAX_CANDIDATES", 4)
    )
    max_duration_seconds: float = field(
        default_factory=lambda: _float("WORKFLOW_MAX_DURATION_SECONDS", 175.0)
    )
    max_llm_calls: int = field(
        default_factory=lambda: _int("WORKFLOW_MAX_LLM_CALLS", 8)
    )
    max_trace_events: int = field(
        default_factory=lambda: _int("WORKFLOW_MAX_TRACE_EVENTS", 256)
    )
    sport_default: str = field(default_factory=lambda: os.getenv("DEFAULT_SPORT", "run"))
    city_default: str = field(default_factory=lambda: os.getenv("DEFAULT_CITY", "Budapest"))
    distance_bounds: dict[str, list[float]] = field(default_factory=lambda: {"run": [3, 60], "bike": [10, 200]})
    distance_defaults: dict[str, float] = field(
        default_factory=lambda: {
            "run": _float("DEFAULT_RUN_DISTANCE_KM", 8.0),
            "bike": _float("DEFAULT_BIKE_DISTANCE_KM", 20.0),
        }
    )


@dataclass
class Settings:
    llm: LLMConfig = field(default_factory=LLMConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    geocoder: GeocoderConfig = field(default_factory=GeocoderConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)


def _split_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalised = raw.strip().lower()
    if normalised in {"1", "true", "yes", "on"}:
        return True
    if normalised in {"0", "false", "no", "off"}:
        return False
    return default


def _load_yaml_overlays() -> dict:
    if SETTINGS_YAML.exists():
        with SETTINGS_YAML.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build a :class:`Settings` object, merging env vars with yaml defaults."""
    settings = Settings()
    yaml_data = _load_yaml_overlays()

    wf_yaml = yaml_data.get("workflow", {})
    if wf_yaml:
        for k, v in wf_yaml.items():
            if k == "distance_bounds":
                settings.workflow.distance_bounds = v
            elif k == "distance_defaults":
                settings.workflow.distance_defaults = {
                    "run": _float(
                        "DEFAULT_RUN_DISTANCE_KM",
                        float(v.get("run", 8.0)),
                    ),
                    "bike": _float(
                        "DEFAULT_BIKE_DISTANCE_KM",
                        float(v.get("bike", 20.0)),
                    ),
                }
            elif hasattr(settings.workflow, k):
                # Env vars win over yaml; only apply yaml when env didn't set it.
                env_name = {
                    "max_refinement_iterations": "MAX_REFINEMENT_ITERATIONS",
                    "validation_score_threshold": "VALIDATION_SCORE_THRESHOLD",
                    "preflight_enabled": "PREFLIGHT_ENABLED",
                    "preflight_max_placements": "PREFLIGHT_MAX_PLACEMENTS",
                    "preflight_shortlist": "PREFLIGHT_SHORTLIST",
                    "preflight_guide_points": "PREFLIGHT_GUIDE_POINTS",
                    "ai_shape_verifier_enabled": "AI_SHAPE_VERIFIER_ENABLED",
                    "ai_shape_min_semantic_score": "AI_SHAPE_MIN_SEMANTIC_SCORE",
                    "ai_shape_max_candidates": "AI_SHAPE_MAX_CANDIDATES",
                    "max_duration_seconds": "WORKFLOW_MAX_DURATION_SECONDS",
                    "max_llm_calls": "WORKFLOW_MAX_LLM_CALLS",
                    "max_trace_events": "WORKFLOW_MAX_TRACE_EVENTS",
                    "sport_default": "DEFAULT_SPORT",
                    "city_default": "DEFAULT_CITY",
                }.get(k)
                if env_name and os.getenv(env_name):
                    continue
                setattr(settings.workflow, k, v)

    rt_yaml = yaml_data.get("routing", {})
    if rt_yaml:
        for k, v in rt_yaml.items():
            if hasattr(settings.routing, k):
                env_name = {
                    "snap_radius_m": "ORS_SNAP_RADIUS_M",
                    "continue_straight": "ORS_CONTINUE_STRAIGHT",
                    "preference": "ORS_PREFERENCE",
                }.get(k)
                if env_name and os.getenv(env_name):
                    continue
                setattr(settings.routing, k, v)

    return settings
