from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable, Iterable

from app.core import geometry as geom, scoring
from app.core.graph import RoadGraph
from app.core.schemas import Activity, Difficulty, ScoreBreakdown
from app.core.seed import Artwork, City
from app.core.shape_matching import MatchResult, Transform, create_best_gps_art
from app.core.snapping import repair_and_route, snap_polyline
from app.core.units import Projector

type GeoPoint = tuple[float, float]
type MetricPoint = tuple[float, float]

ACCEPT_FIT_THRESHOLD = 0.40

PROGRESS_STAGES = [
    "loading_city",
    "building_indexes",
    "parsing_shapes",
    "ranking_shapes",
    "generating_transforms",
    "corridor_scoring",
    "beam_matching",
    "constructing_routes",
    "refining_candidates",
    "scoring",
    "ai_retry",
    "storing_results",
    "completed",
]


@dataclass
class Candidate:
    candidate_id: str
    artwork_id: str
    artwork_name: str
    rank: int
    distance_km: float
    elevation_gain_m: float | None
    scores: ScoreBreakdown
    warnings: list[str]
    route_lonlat: list[GeoPoint]
    target_lonlat: list[GeoPoint]
    keypoint_lonlat: list[GeoPoint]
    debug: dict = field(default_factory=dict)


def _detour_factor(activity: str, road_density: float) -> float:
    sparse = 1.0 - max(0.0, min(1.0, road_density))
    if activity == "cycling":
        return 1.20 + 0.60 * sparse
    return 1.10 + 0.40 * sparse


def build_density_anchors(
    graph: RoadGraph, bbox_metric: tuple[float, float, float, float], target_distance_km: float, max_anchors: int = 20
) -> list[MetricPoint]:
    """Road-density grid placement anchors (section 51.3)."""
    minx, miny, maxx, maxy = bbox_metric
    cell = max(300.0, min(1500.0, target_distance_km * 100.0))
    cols = max(1, int((maxx - minx) / cell))
    rows = max(1, int((maxy - miny) / cell))
    cell_w = (maxx - minx) / cols
    cell_h = (maxy - miny) / rows
    density: dict[tuple[int, int], float] = {}
    for e in graph.edges:
        if e.rejected:
            continue
        mx = (e.geometry_xy[0][0] + e.geometry_xy[1][0]) / 2
        my = (e.geometry_xy[0][1] + e.geometry_xy[1][1]) / 2
        ci = max(0, min(cols - 1, int((mx - minx) / cell_w)))
        cj = max(0, min(rows - 1, int((my - miny) / cell_h)))
        density[(ci, cj)] = density.get((ci, cj), 0.0) + e.length_m
    if not density:
        center = ((minx + maxx) / 2, (miny + maxy) / 2)
        return [center]
    best = sorted(density.items(), key=lambda kv: kv[1], reverse=True)[:max_anchors]
    anchors = []
    for (ci, cj), _ in best:
        cx = minx + (ci + 0.5) * cell_w
        cy = miny + (cj + 0.5) * cell_h
        anchors.append((cx, cy))
    return anchors


def _target_fits(target_xy: list[MetricPoint], bbox_metric: tuple[float, float, float, float], margin: float = 0.1) -> bool:
    if not target_xy:
        return False
    minx, miny, maxx, maxy = bbox_metric
    w = maxx - minx
    h = maxy - miny
    inside = sum(
        1 for x, y in target_xy if minx - margin * w <= x <= maxx + margin * w and miny - margin * h <= y <= maxy + margin * h
    )
    return inside / len(target_xy) >= 0.8


def _anchor_lonlat(anchor_xy: MetricPoint, projector: Projector) -> GeoPoint:
    return projector.to_wgs84(anchor_xy[0], anchor_xy[1])


def _match_to_candidate(m: MatchResult, rank: int) -> Candidate:
    t = m.transform
    cid = "cand_" + hashlib.sha1(
        f"{m.artwork_id}|{t.translation[0]:.1f},{t.translation[1]:.1f}|{t.scale:.1f}|{t.rotation_deg:.1f}".encode()
    ).hexdigest()[:10]
    breakdown = ScoreBreakdown(
        fit_score=round(m.fit_score, 4),
        shape_similarity_score=round(m.shape_similarity_score, 4),
        distance_accuracy_score=round(m.distance_accuracy_score, 4),
        road_quality_score=round(m.road_quality_score, 4),
        continuity_score=round(m.continuity_score, 4),
        elevation_score=round(m.elevation_score, 4),
    )
    return Candidate(
        candidate_id=cid,
        artwork_id=m.artwork_id,
        artwork_name=m.artwork_name,
        rank=rank,
        distance_km=round(m.distance_km, 2),
        elevation_gain_m=None,
        scores=breakdown,
        warnings=m.warnings,
        route_lonlat=m.route_lonlat,
        target_lonlat=m.target_lonlat,
        keypoint_lonlat=m.keypoint_lonlat,
        debug=m.debug,
    )


def generate_suggestions(
    city: City,
    graph: RoadGraph,
    projector: Projector,
    bbox_metric: tuple[float, float, float, float],
    artworks: Iterable[Artwork],
    activity: Activity,
    target_distance_km: float,
    difficulty: Difficulty,
    max_suggestions: int,
    algorithm_version: str,
    max_transformations: int = 1000,
    max_route_repairs: int = 100,
    progress_callback: Callable[[str, int], None] | None = None,
) -> list[Candidate]:
    """Run the SVG-first GPS art matching pipeline and return ranked candidates."""
    from app.config import get_settings
    settings = get_settings()

    activity_v = activity.value if hasattr(activity, "value") else str(activity)
    difficulty_v = difficulty.value if hasattr(difficulty, "value") else str(difficulty)

    matches = create_best_gps_art(
        city=city,
        graph=graph,
        projector=projector,
        bbox=bbox_metric,
        artworks=artworks,
        activity=activity_v,
        difficulty=difficulty_v,
        target_distance_km=target_distance_km,
        max_suggestions=max_suggestions,
        settings=settings,
        algorithm_version=algorithm_version,
        max_transformations=max_transformations,
        max_route_repairs=max_route_repairs,
        progress_callback=progress_callback,
    )

    candidates = [_match_to_candidate(m, rank) for rank, m in enumerate(matches, 1)]
    return candidates
