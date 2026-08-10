"""Typed workflow state threaded through the agent graph.

Every agent reads what it needs and writes its own slot. The orchestrator owns
the instance; agents are stateless. All slots are dataclasses so the state is
serialisable for debugging and for the API response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LatLon = tuple[float, float]


@dataclass
class Intent:
    shape: str | None
    text: str | None
    city: str | None
    sport: str
    distance_km: float | None
    style: str | None
    suggest: bool = False  # True = user wants AI to suggest the best shape for the city


@dataclass
class Plan:
    """Strategy committed by the PlanningAgent before any drawing happens."""
    shape_strategy: str  # template | text | llm
    difficulty: str = "medium"  # easy | medium | hard
    rotation_hint_deg: float | None = None
    scale_hint: float | None = None
    placement_hints: str | None = None
    notes: str | None = None
    lat_offset_m: float = 0.0   # initial placement offset (metres) from city centre
    lon_offset_m: float = 0.0   # initial placement offset (metres) from city centre
    suggested_shape: str | None = None  # AI-suggested shape name (when intent.suggest=True)
    suggestion_candidates: list[str] = field(default_factory=list)
    suggestion_reasons: dict[str, str] = field(default_factory=dict)
    fallback_candidates: list[str] = field(default_factory=list)
    center_lat: float | None = None
    center_lon: float | None = None
    city_bbox: tuple[float, float, float, float] | None = None


@dataclass
class Shape:
    name: str
    paths: list[list[tuple[float, float]]]
    closed: bool
    source: str = "template"  # template | text | llm | fallback


@dataclass
class RouteDraft:
    center_lat: float
    center_lon: float
    scale_m: float
    rotation_deg: float
    lat_offset_m: float
    lon_offset_m: float
    simplify_tolerance: float
    waypoints: list[LatLon]
    closed: bool
    target_distance_km: float | None = None
    preflight_score: float | None = None
    preflight_coverage: float | None = None
    preflight_snap_distance_m: float | None = None


@dataclass
class SnappedRoute:
    points: list[LatLon]
    total_distance_m: float
    snapped: bool  # True = road-following, False = straight-line fallback


@dataclass
class Validation:
    score: float
    closure: float
    distance_fit: float
    shape_fidelity: float
    issues: list[str] = field(default_factory=list)
    on_roads: bool = True  # False = straight-line fallback, route not on real roads
    spatial_similarity: float = 0.0
    coverage_similarity: float = 0.0
    turning_similarity: float = 0.0
    length_similarity: float = 0.0
    extent_similarity: float = 0.0
    route_length_ratio: float = 0.0
    mean_deviation_ratio: float = 0.0
    landmark_similarity: float = 0.0
    reversal_similarity: float = 1.0
    closure_gap_m: float = 0.0
    actual_distance_km: float = 0.0
    target_distance_km: float | None = None
    route_point_count: int = 0
    guide_point_count: int = 0


@dataclass
class EvaluatedCandidate:
    """One fully routed candidate retained for comparison and manual editing."""

    shape_name: str
    shape_source: str
    points: list[LatLon]
    ideal_points: list[LatLon]
    total_distance_m: float
    snapped: bool
    closed: bool
    target_distance_km: float | None
    validation: Validation
    rotation_deg: float
    scale_m: float
    lat_offset_m: float
    lon_offset_m: float
    preflight_score: float | None = None


@dataclass
class FitDecision:
    """Why the requested drawing was retained or another was recommended."""

    requested_shape: str
    selected_shape: str
    substituted: bool
    requested_score: float
    requested_fidelity: float
    selected_score: float
    selected_fidelity: float
    candidates_tested: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@dataclass
class Export:
    gpx: str
    tcx: str | None
    file_paths: dict[str, str]
    name: str


@dataclass
class WorkflowState:
    prompt: str
    request_id: str | None = None
    intent: Intent | None = None
    plan: Plan | None = None
    shape: Shape | None = None
    route_draft: RouteDraft | None = None
    snapped: SnappedRoute | None = None
    validation: Validation | None = None
    export: Export | None = None
    iterations: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    below_threshold: bool = False
    best_validation: Validation | None = None
    best_snapped: SnappedRoute | None = None
    requested_shape: str | None = None
    fit_decision: FitDecision | None = None
    candidate_count: int = 0
    preflight_count: int = 0
    placement_candidates: list[RouteDraft] = field(default_factory=list)
    preflight_candidates: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[EvaluatedCandidate] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        """Compact, JSON-friendly snapshot for the API / history."""
        v = self.validation
        return {
            "iteration": self.iterations,
            "score": v.score if v else None,
            "shape_fidelity": v.shape_fidelity if v else None,
            "distance_km": (self.snapped.total_distance_m / 1000) if self.snapped else None,
            "snapped": self.snapped.snapped if self.snapped else None,
            "on_roads": v.on_roads if v else None,
            "issues": v.issues if v else [],
            "shape": self.shape.name if self.shape else None,
        }
