from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.core import geometry as geom
from app.core.graph import RoadGraph
from app.core.snapping import RouteResult, _segment_distance
from app.core.units import GeoPoint, Projector
from app.core.schemas import ScoreBreakdown

PREFERRED_HIGHWAY = {
    "running": {"footway", "path", "pedestrian", "residential", "living_street", "track"},
    "walking": {"footway", "path", "pedestrian", "residential", "living_street", "track"},
    "cycling": {"cycleway", "residential", "living_street"},
}
AVOID_HIGHWAY = {"primary", "secondary", "motorway", "motorway_link"}

MIN_SHAPE_SIMILARITY = 0.45
MAX_DISTANCE_ERROR = 0.25


@dataclass
class ScoreResult:
    breakdown: ScoreBreakdown
    warnings: list[str]
    distance_error: float
    passed: bool
    rejection_reason: str | None = None
    debug: dict[str, float] = field(default_factory=dict)


def _road_quality(
    route: RouteResult, graph: RoadGraph, activity: str
) -> tuple[float, list[str], dict[str, float]]:
    if not route.edges_used:
        return 0.5, [], {}
    preferred = PREFERRED_HIGHWAY[activity]
    total_len = 0.0
    weighted = 0.0
    use_count: dict[int, int] = {}
    warnings: list[str] = []
    private_seen = False
    stairs_seen = False
    for eid in route.edges_used:
        edge = graph.edges[eid]
        use_count[eid] = use_count.get(eid, 0) + 1
        q = 1.0
        if edge.highway in preferred:
            q = min(1.0, q + 0.05)
        if edge.highway in AVOID_HIGHWAY:
            q -= 0.4
        if edge.access == "private":
            q -= 0.5
            private_seen = True
        if edge.stairs:
            q -= 0.1
            stairs_seen = True
        if edge.surface in ("gravel", "ground", "dirt") and activity == "cycling":
            q -= 0.2
        if use_count[eid] > 1:
            q -= 0.05 * (use_count[eid] - 1)
        weighted += max(0.0, q) * edge.length_m
        total_len += edge.length_m
    quality = weighted / total_len if total_len else 0.5
    quality = max(0.0, min(1.0, quality))

    # u-turn / backtracking detection on node path
    backtracks = sum(
        1 for i in range(len(route.node_path) - 2) if route.node_path[i] == route.node_path[i + 2]
    )
    if backtracks > 0:
        quality = max(0.0, quality - 0.02 * backtracks)

    if private_seen:
        warnings.append("contains_private_access_penalty")
    if stairs_seen and activity == "running":
        warnings.append("contains_stairs")
    return quality, warnings, {"backtracks": backtracks, "private_seen": float(private_seen)}


def score_candidate(
    target_lonlat: list[GeoPoint],
    route: RouteResult,
    target_distance_km: float,
    activity: str,
    graph: RoadGraph,
    projector: Projector,
    has_river: bool = False,
) -> ScoreResult:
    target_distance_m = target_distance_km * 1000.0
    route_distance_m = route.length_m
    route_distance_km = route_distance_m / 1000.0

    target_xy = [projector.to_metric(lon, lat) for lat, lon in target_lonlat]
    shape = geom.shape_similarity(target_xy, route.route_metric, target_distance_m)

    distance_error = abs(route_distance_km - target_distance_km) / target_distance_km
    tolerance = 0.10
    distance_accuracy = max(0.0, 1.0 - distance_error / tolerance)

    road_quality, road_warnings, road_debug = _road_quality(route, graph, activity)

    continuity = 1.0 if route.valid and route.segments_failed == 0 else max(0.0, 1.0 - route.segments_failed * 0.2)
    elevation = 1.0  # MVP omits elevation (section 54.3)

    fit = (
        0.45 * shape
        + 0.20 * distance_accuracy
        + 0.20 * road_quality
        + 0.10 * continuity
        + 0.05 * elevation
    )
    # aggregate penalties
    penalty = 0.0
    if route.duplicate_fraction > 0.10:
        penalty += 0.05
    if route.segments_failed > 0:
        penalty += 0.1
    fit = max(0.0, min(1.0, fit - penalty))

    warnings: list[str] = []
    warnings.extend(route.warnings)
    warnings.extend(road_warnings)
    if distance_error > 0.05:
        warnings.append("distance_outside_preferred_tolerance")
    if shape < MIN_SHAPE_SIMILARITY:
        warnings.append("low_shape_similarity")
    if has_river and any(d > 3.0 for d in route.detour_ratios):
        warnings.append("connect_the_dots_recommended")
    # de-duplicate preserving order
    seen: set[str] = set()
    warnings = [w for w in warnings if not (w in seen or seen.add(w))]

    breakdown = ScoreBreakdown(
        fit_score=round(fit, 4),
        shape_similarity_score=round(shape, 4),
        distance_accuracy_score=round(distance_accuracy, 4),
        road_quality_score=round(road_quality, 4),
        continuity_score=round(continuity, 4),
        elevation_score=round(elevation, 4),
    )

    rejection: str | None = None
    if shape < MIN_SHAPE_SIMILARITY:
        rejection = "low_shape_similarity"
    elif distance_error > MAX_DISTANCE_ERROR:
        rejection = "distance_out_of_range"
    elif not route.valid:
        rejection = "route_invalid"
    passed = rejection is None

    debug = {
        "route_distance_km": route_distance_km,
        "distance_error": distance_error,
        "detour_max": max(route.detour_ratios) if route.detour_ratios else 0.0,
        "duplicate_fraction": route.duplicate_fraction,
        **road_debug,
    }
    return ScoreResult(breakdown=breakdown, warnings=warnings, distance_error=distance_error,
                       passed=passed, rejection_reason=rejection, debug=debug)


# --------------------------------------------------------------------------- #
# New confidence scoring (algorithm document section 9)
# --------------------------------------------------------------------------- #


def _point_to_polyline_min_dist(
    p: tuple[float, float], polyline: list[tuple[float, float]]
) -> float:
    """Minimum Euclidean distance from point *p* to any segment of *polyline*."""
    if not polyline:
        return float("inf")
    if len(polyline) == 1:
        return math.hypot(p[0] - polyline[0][0], p[1] - polyline[0][1])
    min_d = float("inf")
    for i in range(len(polyline) - 1):
        d = _segment_distance(p, polyline[i], polyline[i + 1])
        if d < min_d:
            min_d = d
    return min_d


def svg_geometry_score(
    svg_samples: list[tuple[float, float]],
    svg_weights: list[float],
    route_samples: list[tuple[float, float]],
    tolerance_m: float,
) -> float:
    """exp(-weighted_mean_svg_to_route_error_m / tolerance_m)."""
    if not svg_samples or not route_samples or tolerance_m <= 0:
        return 0.0
    total_w = 0.0
    weighted_err = 0.0
    for i, pt in enumerate(svg_samples):
        w = svg_weights[i] if i < len(svg_weights) else 0.3
        d = _point_to_polyline_min_dist(pt, route_samples)
        weighted_err += d * w
        total_w += w
    if total_w == 0:
        return 0.0
    mean_err = weighted_err / total_w
    return float(math.exp(-mean_err / tolerance_m))


def reverse_geometry_score(
    route_samples: list[tuple[float, float]],
    svg_samples: list[tuple[float, float]],
    tolerance_m: float,
) -> float:
    """exp(-mean_route_to_svg_error_m / tolerance_m)."""
    if not route_samples or not svg_samples or tolerance_m <= 0:
        return 0.0
    total = 0.0
    for pt in route_samples:
        d = _point_to_polyline_min_dist(pt, svg_samples)
        total += d
    mean_err = total / len(route_samples)
    return float(math.exp(-mean_err / tolerance_m))


def weighted_coverage_score(
    matched_weighted_length: float, total_weighted_length: float
) -> float:
    """Percentage of high-weight SVG length supported by streets."""
    if total_weighted_length <= 0:
        return 0.0
    return float(max(0.0, min(1.0, matched_weighted_length / total_weighted_length)))


def corner_score(
    matched_important_points: int, total_important_points: int
) -> float:
    """Fraction of important SVG corners that align with route turns or intersections."""
    if total_important_points <= 0:
        return 1.0
    return float(max(0.0, min(1.0, matched_important_points / total_important_points)))


def routeability_score(
    legal_route_length: float, required_route_length: float
) -> float:
    """How close the legal connected route length is to the required length."""
    if required_route_length <= 0:
        return 0.0
    ratio = legal_route_length / required_route_length
    if ratio <= 0:
        return 0.0
    if ratio <= 1.0:
        return float(ratio)
    # Penalise excess length but don't go to zero immediately
    return float(max(0.0, 2.0 - ratio))


def detour_score_fn(
    detour_ratio: float, max_allowed_detour: float
) -> float:
    """max(0, 1 - (detour_ratio - 1) / max_allowed_detour)."""
    if max_allowed_detour <= 0:
        return 0.0
    return float(max(0.0, 1.0 - (detour_ratio - 1.0) / max_allowed_detour))


def uniqueness_score(
    best_confidence: float, second_best_confidence: float
) -> float:
    """clamp(1 - second_best / best, 0, 1)."""
    if best_confidence <= 0:
        return 0.0
    return float(max(0.0, min(1.0, 1.0 - second_best_confidence / best_confidence)))


def topology_score(
    endpoints_matched: int,
    total_endpoints: int,
    branches_preserved: int,
    total_branches: int,
    closed_loop_preserved: bool,
    is_closed_shape: bool,
) -> float:
    """Score how well endpoints, branches, and closed loops are preserved."""
    parts: list[float] = []
    if total_endpoints > 0:
        parts.append(endpoints_matched / total_endpoints)
    if total_branches > 0:
        parts.append(branches_preserved / total_branches)
    if is_closed_shape:
        parts.append(1.0 if closed_loop_preserved else 0.0)
    if not parts:
        return 1.0
    return float(sum(parts) / len(parts))


@dataclass
class ConfidenceResult:
    confidence: float
    svg_geometry: float
    reverse_geometry: float
    weighted_coverage: float
    corner: float
    topology: float
    routeability: float
    detour: float
    uniqueness: float
    metrics: dict[str, float] = field(default_factory=dict)


def compute_confidence(
    svg_geometry: float,
    reverse_geometry: float,
    weighted_coverage: float,
    corner: float,
    topology: float,
    routeability: float,
    detour: float,
    uniqueness: float,
) -> ConfidenceResult:
    """Weighted combination of all confidence sub-scores (algorithm section 9)."""
    confidence = (
        0.25 * svg_geometry
        + 0.15 * reverse_geometry
        + 0.20 * weighted_coverage
        + 0.10 * corner
        + 0.10 * topology
        + 0.10 * routeability
        + 0.05 * detour
        + 0.05 * uniqueness
    )
    confidence = max(0.0, min(1.0, confidence))
    return ConfidenceResult(
        confidence=confidence,
        svg_geometry=svg_geometry,
        reverse_geometry=reverse_geometry,
        weighted_coverage=weighted_coverage,
        corner=corner,
        topology=topology,
        routeability=routeability,
        detour=detour,
        uniqueness=uniqueness,
        metrics={
            "svg_geometry_score": svg_geometry,
            "reverse_geometry_score": reverse_geometry,
            "weighted_coverage_score": weighted_coverage,
            "corner_score": corner,
            "topology_score": topology,
            "routeability_score": routeability,
            "detour_score": detour,
            "uniqueness_score": uniqueness,
        },
    )
