from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.core.shape_matching import (
    CityIndexes,
    MatchResult,
    MatchingConstraints,
    RoadGraph,
)


@dataclass
class RetryPlan:
    actions: list[dict[str, Any]]
    source: str = "heuristic"


def build_matching_diagnostics(
    city_graph: RoadGraph,
    indexes: CityIndexes,
    ranked_shapes: list[tuple[Any, Any, float]],
    best_matches: list[MatchResult],
    constraints: MatchingConstraints,
) -> dict[str, Any]:
    """Build structured diagnostics JSON for AI retry (algorithm section 10)."""
    city_features_data: dict[str, Any] = {}
    node_count = len(city_graph.nodes)
    edge_lengths = [e.length_m for e in city_graph.edges if not e.rejected]
    avg_block = sum(edge_lengths) / max(1, len(edge_lengths)) if edge_lengths else 0
    total_edge = sum(edge_lengths)

    density = node_count / max(1.0, total_edge / 1000.0) if total_edge > 0 else 0
    city_features_data = {
        "intersection_density": "low" if density < 2 else "medium" if density < 10 else "high",
        "avg_block_size_m": round(avg_block, 1),
        "total_edge_length_m": round(total_edge, 1),
        "node_count": node_count,
        "largest_component": max(indexes.component_sizes.values()) if indexes.component_sizes else 0,
    }

    shape_failures: list[dict[str, Any]] = []
    for art, sg, score in ranked_shapes[:5]:
        matches_for_shape = [m for m in best_matches if m.artwork_id == art.id]
        if matches_for_shape:
            best = max(matches_for_shape, key=lambda m: m.confidence)
            failure_reason = ""
            missing: list[str] = []
            if best.confidence < constraints.min_confidence:
                failure_reason = "low_confidence"
            if best.detail_level == "coarse":
                missing.append("fine_details")
            shape_failures.append({
                "shape": f"{art.id}.svg",
                "confidence": round(best.confidence, 3),
                "failure_reason": failure_reason,
                "missing_features": missing,
                "detail_level": best.detail_level,
            })
        else:
            shape_failures.append({
                "shape": f"{art.id}.svg",
                "confidence": 0.0,
                "failure_reason": "no_match_found",
                "missing_features": [],
                "detail_level": "none",
            })

    candidate_metrics: dict[str, Any] = {
        "route_mode": constraints.activity,
        "target_distance_km": constraints.target_distance_km,
    }
    if best_matches:
        scales = [m.transform.scale for m in best_matches[:5]]
        candidate_metrics["best_scales"] = [round(s, 1) for s in scales]
        candidate_metrics["best_confidence"] = round(
            max(m.confidence for m in best_matches), 3
        )
        neighborhoods = [
            (m.transform.translation[0], m.transform.translation[1])
            for m in best_matches[:5]
        ]
        candidate_metrics["best_neighborhoods"] = [
            [round(n[0], 1), round(n[1], 1)] for n in neighborhoods
        ]

    return {
        "city_features": city_features_data,
        "shape_failures": shape_failures,
        "candidate_metrics": candidate_metrics,
        "constraints": {
            "min_confidence": constraints.min_confidence,
            "min_corridor_score": constraints.min_corridor_score,
            "min_weighted_coverage": constraints.min_weighted_coverage,
            "max_ai_retry_rounds": constraints.max_ai_retry_rounds,
        },
    }


def _call_zen_api(diagnostics: dict[str, Any], settings: Settings) -> RetryPlan | None:
    """Call Zen API for retry suggestions. Returns None if unavailable."""
    if not settings.zen_api_key:
        return None
    try:
        import httpx
        payload = {
            "model": "glm-4-flash",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a GPS art matching assistant. Given matching "
                        "diagnostics, suggest bounded retry actions as JSON. "
                        'Return {"actions": [...]} where each action has '
                        '"type" and "params". Valid types: rerank_shapes, '
                        "change_neighborhood, change_scale, "
                        "change_rotation_prior, simplify_low_weight_svg_details, "
                        "adjust_candidate_budget."
                    ),
                },
                {
                    "role": "user",
                    "content": str(diagnostics),
                },
            ],
            "temperature": 0.3,
            "max_tokens": 500,
        }
        headers = {"Authorization": f"Bearer {settings.zen_api_key}"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{settings.zen_base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            import json
            parsed = json.loads(content)
            return RetryPlan(actions=parsed.get("actions", []), source="ai")
    except Exception:
        return None


def propose_retry_plan(
    diagnostics: dict[str, Any], settings: Settings
) -> RetryPlan:
    """Propose a retry plan via Zen API, or deterministic heuristics as fallback."""
    plan = _call_zen_api(diagnostics, settings)
    if plan is not None:
        return plan

    actions: list[dict[str, Any]] = []
    shape_failures = diagnostics.get("shape_failures", [])
    candidate_metrics = diagnostics.get("candidate_metrics", {})

    has_low_confidence = any(
        f.get("failure_reason") == "low_confidence" for f in shape_failures
    )
    has_no_match = any(
        f.get("failure_reason") == "no_match_found" for f in shape_failures
    )

    if has_no_match or has_low_confidence:
        actions.append({
            "type": "simplify_low_weight_svg_details",
            "params": {"target_detail": "coarse"},
        })

    if has_low_confidence:
        best_scales = candidate_metrics.get("best_scales", [])
        if best_scales:
            avg_scale = sum(best_scales) / len(best_scales)
            actions.append({
                "type": "change_scale",
                "params": {"factor": 1.2},
            })
        else:
            actions.append({
                "type": "change_scale",
                "params": {"factor": 0.8},
            })

        actions.append({
            "type": "change_rotation_prior",
            "params": {"offset": 30},
        })

    actions.append({
        "type": "adjust_candidate_budget",
        "params": {"coarse_limit_multiplier": 1.5},
    })

    return RetryPlan(actions=actions, source="heuristic")


def apply_ai_retry_plan(
    ai_plan: RetryPlan,
    ranked_shapes: list[tuple[Any, Any, float]],
    constraints: MatchingConstraints,
) -> tuple[list[tuple[Any, Any, float]], MatchingConstraints]:
    """Convert AI/heuristic suggestions into concrete search parameters."""
    new_constraints = MatchingConstraints(
        min_confidence=constraints.min_confidence,
        min_corridor_score=constraints.min_corridor_score,
        min_weighted_coverage=constraints.min_weighted_coverage,
        coarse_candidate_limit=constraints.coarse_candidate_limit,
        medium_candidate_limit=constraints.medium_candidate_limit,
        final_candidate_limit=constraints.final_candidate_limit,
        beam_width=constraints.beam_width,
        candidates_per_sample=constraints.candidates_per_sample,
        max_ai_retry_rounds=constraints.max_ai_retry_rounds,
        target_distance_km=constraints.target_distance_km,
        activity=constraints.activity,
        difficulty=constraints.difficulty,
        bbox_metric=constraints.bbox_metric,
        max_transformations=constraints.max_transformations,
        max_route_repairs=constraints.max_route_repairs,
        has_river=constraints.has_river,
        road_density=constraints.road_density,
        ai_retry_enabled=constraints.ai_retry_enabled,
        symmetric=constraints.symmetric,
        normalized_length=constraints.normalized_length,
        detour_factor=constraints.detour_factor,
        algorithm_version=constraints.algorithm_version,
        preferred_neighborhood=constraints.preferred_neighborhood,
        preferred_scale=constraints.preferred_scale,
        preferred_rotation=constraints.preferred_rotation,
        detail_level_override=constraints.detail_level_override,
        signature_artwork_ids=constraints.signature_artwork_ids,
    )

    new_ranked = list(ranked_shapes)

    for action in ai_plan.actions:
        atype = action.get("type", "")
        params = action.get("params", {})

        if atype == "rerank_shapes":
            new_ranked.sort(
                key=lambda x: x[2] * (1.0 + params.get("boost", 0.1) * (1.0 - x[2])),
                reverse=True,
            )

        elif atype == "change_neighborhood":
            neighborhoods = params.get("neighborhoods", [])
            if neighborhoods:
                new_constraints.preferred_neighborhood = tuple(neighborhoods[0])

        elif atype == "change_scale":
            factor = params.get("factor", 1.2)
            if new_constraints.preferred_scale is None:
                target_m = new_constraints.target_distance_km * 1000.0
                if new_constraints.normalized_length > 0:
                    base = target_m / (
                        new_constraints.normalized_length * new_constraints.detour_factor
                    )
                    new_constraints.preferred_scale = base * factor
            else:
                new_constraints.preferred_scale *= factor

        elif atype == "change_rotation_prior":
            offset = params.get("offset", 30)
            new_constraints.preferred_rotation = offset

        elif atype == "simplify_low_weight_svg_details":
            target_detail = params.get("target_detail", "coarse")
            new_constraints.detail_level_override = target_detail

        elif atype == "adjust_candidate_budget":
            mult = params.get("coarse_limit_multiplier", 1.5)
            new_constraints.coarse_candidate_limit = int(
                new_constraints.coarse_candidate_limit * mult
            )
            new_constraints.medium_candidate_limit = min(
                int(new_constraints.medium_candidate_limit * mult),
                new_constraints.coarse_candidate_limit,
            )

    return new_ranked, new_constraints
