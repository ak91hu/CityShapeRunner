"""One authoritative definition of an acceptable GPS-art route.

The orchestrator, API, editor, exporter, and UI must agree about whether a
candidate follows the selected drawing.  Keeping these gates in one module
prevents an aggregate score from hiding a failed landmark/topology proxy and
prevents different surfaces from presenting contradictory route statuses.
"""

from __future__ import annotations

from typing import Any

from .config import get_settings
from .state import Validation

_USABILITY_THRESHOLD = 0.6


def _numeric_gate(
    key: str,
    label: str,
    group: str,
    value: float,
    minimum: float,
    description: str,
    *,
    applies: bool = True,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "group": group,
        "value": float(value),
        "minimum": float(minimum),
        "passed": bool(not applies or value >= minimum),
        "applies": applies,
        "description": description,
    }


def quality_gate_report(
    validation: Validation,
    *,
    closed: bool,
    candidate_shape: str | None = None,
    selected_shape: str | None = None,
) -> dict[str, Any]:
    """Return every independently testable route-acceptance gate.

    Shape identity is checked when both names are supplied.  All recognition
    components are hard gates: the combined fidelity score cannot compensate
    for a lost outline, turn sequence, landmark, proportion, or excessive
    detour.  This deliberately favours honest rejection over a misleading GPX.
    """

    workflow = get_settings().workflow
    shape_threshold = workflow.min_shape_fidelity
    score_threshold = workflow.validation_score_threshold
    shape_identity_applies = (
        candidate_shape is not None and selected_shape is not None
    )
    shape_identity_passed = bool(
        not shape_identity_applies
        or (
            candidate_shape is not None
            and selected_shape is not None
            and candidate_shape.casefold() == selected_shape.casefold()
        )
    )

    gates: list[dict[str, Any]] = [
        {
            "key": "selected_shape",
            "label": "Selected shape",
            "group": "shape",
            "value": candidate_shape,
            "minimum": selected_shape,
            "passed": shape_identity_passed,
            "applies": shape_identity_applies,
            "description": "The route was generated from the shape currently selected for the result.",
        },
        {
            "key": "road_network",
            "label": "Connected street route",
            "group": "route",
            "value": bool(validation.on_roads),
            "minimum": True,
            "passed": bool(validation.on_roads),
            "applies": True,
            "description": "The routing provider returned connected road/path geometry rather than a straight-line guide.",
        },
        _numeric_gate(
            "overall_score",
            "Overall route quality",
            "route",
            validation.score,
            score_threshold,
            "The combined recognition, distance, and closure score reaches the configured target.",
        ),
        _numeric_gate(
            "shape_fidelity",
            "Combined shape likeness",
            "shape",
            validation.shape_fidelity,
            shape_threshold,
            "The aggregate curve and structural comparison preserves the drawing.",
        ),
        _numeric_gate(
            "spatial_similarity",
            "Ordered curve match",
            "shape",
            validation.spatial_similarity,
            shape_threshold,
            "The route follows the drawing in the intended traversal order.",
        ),
        _numeric_gate(
            "coverage_similarity",
            "Outline coverage",
            "shape",
            validation.coverage_similarity,
            shape_threshold,
            "The street route covers the intended outline without large omissions or excursions.",
        ),
        _numeric_gate(
            "turning_similarity",
            "Characteristic turns",
            "shape",
            validation.turning_similarity,
            shape_threshold,
            "The direction-change sequence that identifies the drawing is retained.",
        ),
        _numeric_gate(
            "landmark_similarity",
            "Salient landmarks",
            "shape",
            validation.landmark_similarity,
            shape_threshold,
            "Dominant corners, tips, and notches remain at the expected contour phases.",
        ),
        _numeric_gate(
            "length_similarity",
            "Detour control",
            "shape",
            validation.length_similarity,
            shape_threshold,
            "Street detours do not add visually misleading extra strokes.",
        ),
        _numeric_gate(
            "extent_similarity",
            "Width / height preservation",
            "shape",
            validation.extent_similarity,
            shape_threshold,
            "The routed silhouette retains the drawing's principal proportions.",
        ),
        _numeric_gate(
            "distance_fit",
            "Target-distance accuracy",
            "usability",
            validation.distance_fit,
            _USABILITY_THRESHOLD,
            "The route remains close enough to the requested activity distance.",
        ),
        _numeric_gate(
            "closure",
            "Loop closure",
            "usability",
            validation.closure,
            _USABILITY_THRESHOLD,
            "A closed drawing finishes sufficiently near its start.",
            applies=closed,
        ),
    ]
    required = [gate for gate in gates if gate["applies"]]
    shape_gates = [gate for gate in required if gate["group"] == "shape"]
    failed = [gate["key"] for gate in required if not gate["passed"]]
    return {
        "passed": not failed,
        "shape_following": all(gate["passed"] for gate in shape_gates),
        "passed_count": sum(1 for gate in required if gate["passed"]),
        "required_count": len(required),
        "failed_gates": failed,
        "gates": gates,
        "thresholds": {
            "overall_score": score_threshold,
            "shape": shape_threshold,
            "usability": _USABILITY_THRESHOLD,
        },
    }


def passes_quality_gates(validation: Validation, *, closed: bool) -> bool:
    """Whether a candidate may be presented/exported as generated GPS art."""

    return bool(quality_gate_report(validation, closed=closed)["passed"])


def quality_bottleneck(validation: Validation, *, closed: bool) -> float:
    """Lowest normalised numeric gate, used to guide candidate refinement."""

    report = quality_gate_report(validation, closed=closed)
    ratios = [
        float(gate["value"]) / max(float(gate["minimum"]), 1e-9)
        for gate in report["gates"]
        if gate["applies"]
        and isinstance(gate["value"], float | int)
        and not isinstance(gate["value"], bool)
        and isinstance(gate["minimum"], float | int)
        and not isinstance(gate["minimum"], bool)
    ]
    if not validation.on_roads:
        return 0.0
    return min(ratios, default=0.0)
