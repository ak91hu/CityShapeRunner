from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Callable

from app.core import geometry as geom
from app.core import scoring as scoring_mod
from app.core.graph import Edge, Node, RoadGraph
from app.core.scoring import (
    ScoreResult,
    _road_quality,
    compute_confidence,
    corner_score,
    detour_score_fn,
    reverse_geometry_score,
    routeability_score,
    svg_geometry_score,
    topology_score,
    uniqueness_score,
    weighted_coverage_score,
)
from app.core.schemas import Activity, Difficulty, ScoreBreakdown
from app.core.seed import Artwork, City
from app.core.snapping import (
    MAX_DETOUR_RATIO,
    SNAP_TOLERANCE_M,
    RouteResult,
    SnapResult,
    _control_indices,
    repair_and_route,
    snap_polyline,
)
from app.core.units import GeoPoint, MetricPoint, Projector, angle_difference_deg, heading_deg
from app.config import Settings

type GeoPoint = tuple[float, float]
type MetricPoint = tuple[float, float]

ACCEPT_FIT_THRESHOLD = 0.40


@dataclass
class Transform:
    translation: tuple[float, float]
    rotation_deg: float
    scale: float


@dataclass
class MatchingConstraints:
    min_confidence: float = 0.65
    min_corridor_score: float = 0.30
    min_weighted_coverage: float = 0.40
    coarse_candidate_limit: int = 200
    medium_candidate_limit: int = 50
    final_candidate_limit: int = 15
    beam_width: int = 40
    candidates_per_sample: int = 5
    max_ai_retry_rounds: int = 2
    target_distance_km: float = 10.0
    activity: str = "running"
    difficulty: str = "medium"
    bbox_metric: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    max_transformations: int = 1000
    max_route_repairs: int = 100
    has_river: bool = False
    road_density: float = 0.6
    ai_retry_enabled: bool = True
    symmetric: bool = False
    normalized_length: float = 1.0
    detour_factor: float = 1.3
    algorithm_version: str = "svg-first-1.0"
    preferred_neighborhood: tuple[float, float] | None = None
    preferred_scale: float | None = None
    preferred_rotation: float | None = None
    detail_level_override: str | None = None
    signature_artwork_ids: list[str] = field(default_factory=list)


@dataclass
class NodeSignature:
    degree: int
    outgoing_bearings: list[float]
    edge_lengths: list[float]


@dataclass
class CityIndexes:
    graph: RoadGraph
    node_signatures: dict[int, NodeSignature]
    bearing_buckets: dict[int, list[int]]
    component_index: dict[int, int]
    component_sizes: dict[int, int]
    route_cache: dict[tuple[int, int], tuple[list[int], float]]
    _cache_order: list[tuple[int, int]] = field(default_factory=list)
    _cache_max: int = 512

    def cache_get(self, a: int, b: int) -> tuple[list[int], float] | None:
        key = (min(a, b), max(a, b))
        return self.route_cache.get(key)

    def cache_put(self, a: int, b: int, path: list[int], cost: float) -> None:
        key = (min(a, b), max(a, b))
        if key in self.route_cache:
            return
        if len(self._cache_order) >= self._cache_max:
            old = self._cache_order.pop(0)
            self.route_cache.pop(old, None)
        self.route_cache[key] = (path, cost)
        self._cache_order.append(key)


@dataclass
class CityFeatures:
    intersection_density: float
    orientation_entropy: float
    dominant_bearings: list[float]
    curvature: str
    largest_component_length_m: float
    avg_block_size: float
    dead_end_ratio: float
    total_edge_length_m: float
    node_count: int


@dataclass
class SnappedResult:
    weighted_coverage: float
    snap: SnapResult
    candidate_nodes: list[list[int]]
    matched_important: int
    total_important: int


@dataclass
class Router:
    graph: RoadGraph
    activity: str
    difficulty: str

    def snap_tolerance(self) -> float:
        return SNAP_TOLERANCE_M[self.activity]

    def max_detour(self) -> float:
        d = MAX_DETOUR_RATIO[self.activity]
        if self.difficulty == "easy":
            d *= 0.8
        return d


@dataclass
class MatchResult:
    artwork_id: str
    artwork_name: str
    confidence: float
    transform: Transform
    route_lonlat: list[GeoPoint]
    target_lonlat: list[GeoPoint]
    keypoint_lonlat: list[GeoPoint]
    distance_km: float
    detail_level: str
    fit_score: float
    shape_similarity_score: float
    distance_accuracy_score: float
    road_quality_score: float
    continuity_score: float
    elevation_score: float
    warnings: list[str]
    debug: dict


def apply_transform_to_metric(
    normalized: list[geom.Polyline], transform: Transform
) -> list[geom.Polyline]:
    theta = math.radians(transform.rotation_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    tx, ty = transform.translation
    s = transform.scale
    out: list[geom.Polyline] = []
    for pl in normalized:
        pts = [
            (tx + s * (nx * cos_t - ny * sin_t), ty + s * (nx * sin_t + ny * cos_t))
            for nx, ny in pl.points
        ]
        out.append(geom.Polyline(points=pts, closed=pl.closed))
    return out


def transform_to_lonlat(
    normalized: list[geom.Polyline], transform: Transform, projector: Projector
) -> list[geom.Polyline]:
    metric = apply_transform_to_metric(normalized, transform)
    out: list[geom.Polyline] = []
    for pl in metric:
        pts = [projector.to_wgs84(x, y) for x, y in pl.points]
        out.append(geom.Polyline(points=pts, closed=pl.closed))
    return out


def _target_fits_bbox(
    metric_polylines: list[geom.Polyline],
    bbox_metric: tuple[float, float, float, float],
    margin: float = 0.1,
) -> bool:
    all_pts = [pt for pl in metric_polylines for pt in pl.points]
    if not all_pts:
        return False
    minx, miny, maxx, maxy = bbox_metric
    w = maxx - minx
    h = maxy - miny
    inside = sum(
        1
        for x, y in all_pts
        if minx - margin * w <= x <= maxx + margin * w
        and miny - margin * h <= y <= maxy + margin * h
    )
    return inside / len(all_pts) >= 0.8


def build_city_indexes(graph: RoadGraph, projector: Projector) -> CityIndexes:
    if graph._tree is None:
        graph.build_spatial_index()

    node_sigs: dict[int, NodeSignature] = {}
    for nid, node in graph.nodes.items():
        bearings: list[float] = []
        lengths: list[float] = []
        for vid, edge in graph.adj.get(nid, []):
            vn = graph.nodes[vid]
            b = heading_deg((node.x, node.y), (vn.x, vn.y))
            bearings.append(b)
            lengths.append(edge.length_m)
        node_sigs[nid] = NodeSignature(
            degree=node.degree, outgoing_bearings=bearings, edge_lengths=lengths
        )

    n_bins = 36
    bearing_buckets: dict[int, list[int]] = {i: [] for i in range(n_bins)}
    for i, edge in enumerate(graph.edges):
        if edge.rejected:
            continue
        a = graph.nodes[edge.from_id]
        b = graph.nodes[edge.to_id]
        bearing = heading_deg((a.x, a.y), (b.x, b.y))
        bin_idx = int(bearing / (360.0 / n_bins)) % n_bins
        bearing_buckets[bin_idx].append(i)

    component_index: dict[int, int] = {}
    component_sizes: dict[int, int] = {}
    comp_id = 0
    for nid in graph.nodes:
        if nid in component_index:
            continue
        queue = deque([nid])
        component_index[nid] = comp_id
        size = 0
        while queue:
            cur = queue.popleft()
            size += 1
            for vid, _ in graph.adj.get(cur, []):
                if vid not in component_index:
                    component_index[vid] = comp_id
                    queue.append(vid)
        component_sizes[comp_id] = size
        comp_id += 1

    return CityIndexes(
        graph=graph,
        node_signatures=node_sigs,
        bearing_buckets=bearing_buckets,
        component_index=component_index,
        component_sizes=component_sizes,
        route_cache={},
    )


def extract_city_features(
    graph: RoadGraph, indexes: CityIndexes, bbox_metric: tuple[float, float, float, float]
) -> CityFeatures:
    minx, miny, maxx, maxy = bbox_metric
    area = max(1.0, (maxx - minx) * (maxy - miny))
    node_count = len(graph.nodes)
    intersection_density = node_count / (area / 1_000_000.0)

    total_edges = sum(len(v) for v in indexes.bearing_buckets.values())
    entropy = 0.0
    for ids in indexes.bearing_buckets.values():
        if ids and total_edges > 0:
            p = len(ids) / total_edges
            if p > 0:
                entropy -= p * math.log2(p)

    sorted_bins = sorted(
        indexes.bearing_buckets.items(), key=lambda kv: len(kv[1]), reverse=True
    )
    dominant = [bin_idx * 10.0 for bin_idx, _ in sorted_bins[:3]]
    curvature = "grid" if entropy < 2.5 else "organic"

    edge_lengths = [e.length_m for e in graph.edges if not e.rejected]
    avg_block = sum(edge_lengths) / max(1, len(edge_lengths)) if edge_lengths else 0.0
    total_edge = sum(edge_lengths)

    dead_ends = sum(1 for n in graph.nodes.values() if n.degree <= 1)
    dead_end_ratio = dead_ends / max(1, node_count)

    return CityFeatures(
        intersection_density=intersection_density,
        orientation_entropy=entropy,
        dominant_bearings=dominant,
        curvature=curvature,
        largest_component_length_m=total_edge,
        avg_block_size=avg_block,
        dead_end_ratio=dead_end_ratio,
        total_edge_length_m=total_edge,
        node_count=node_count,
    )


def _shape_city_fit_score(
    city_features: CityFeatures, sg: geom.ShapeGraph, constraints: MatchingConstraints
) -> float:
    density = min(1.0, city_features.intersection_density / 500.0)
    n_important = len(sg.important_points)
    detail_need = min(1.0, n_important / 20.0)
    street_density_fit = 1.0 - abs(density - detail_need) * 0.5

    svg_hist = sg.bearing_histogram
    n_bins = len(svg_hist)
    city_hist_raw = [0] * n_bins
    for b in city_features.dominant_bearings:
        idx = int(b / (360.0 / n_bins)) % n_bins
        city_hist_raw[idx] += 1
    dot = sum(a * b for a, b in zip(svg_hist, city_hist_raw))
    mag_a = math.sqrt(sum(a * a for a in svg_hist)) or 1.0
    mag_b = math.sqrt(sum(b * b for b in city_hist_raw)) or 1.0
    orientation_fit = dot / (mag_a * mag_b) if mag_a > 0 and mag_b > 0 else 0.5

    is_curvy = sum(1 for w in sg.weights if w < 0.5) / max(1, len(sg.weights))
    if city_features.curvature == "organic":
        curvature_fit = 0.5 + 0.5 * is_curvy
    else:
        curvature_fit = 0.5 + 0.5 * (1.0 - is_curvy)

    target_m = constraints.target_distance_km * 1000.0
    if sg.normalized_length > 0 and constraints.detour_factor > 0:
        est_scale = target_m / (sg.normalized_length * constraints.detour_factor)
        if 50.0 <= est_scale <= 20000.0:
            route_length_fit = 1.0
        else:
            route_length_fit = max(0.0, 1.0 - abs(est_scale - 3000.0) / 20000.0)
    else:
        route_length_fit = 0.5

    if sg.closed_path:
        topology_fit = 0.7 + 0.3 * (1.0 - city_features.dead_end_ratio)
    else:
        topology_fit = 0.5 + 0.5 * city_features.dead_end_ratio

    if constraints.activity in ("running", "walking"):
        mode_fit = 1.0 - min(1.0, n_important / 50.0)
    else:
        mode_fit = min(1.0, sg.normalized_length / 5.0)

    score = (
        0.25 * max(0.0, min(1.0, street_density_fit))
        + 0.20 * max(0.0, min(1.0, orientation_fit))
        + 0.20 * max(0.0, min(1.0, curvature_fit))
        + 0.15 * max(0.0, min(1.0, route_length_fit))
        + 0.10 * max(0.0, min(1.0, topology_fit))
        + 0.10 * max(0.0, min(1.0, mode_fit))
    )
    return max(0.0, min(1.0, score))


def rank_shapes_for_city(
    city_features: CityFeatures,
    parsed_shapes: list[tuple[Artwork, geom.ShapeGraph]],
    constraints: MatchingConstraints,
) -> list[tuple[Artwork, geom.ShapeGraph, float]]:
    ranked: list[tuple[Artwork, geom.ShapeGraph, float]] = []
    for art, sg in parsed_shapes:
        score = _shape_city_fit_score(city_features, sg, constraints)
        ranked.append((art, sg, score))
    ranked.sort(key=lambda x: x[2], reverse=True)
    return ranked


@dataclass
class CityCompatibility:
    city_id: str
    city_name: str
    fit_score: float
    min_km: float
    max_km: float
    recommended_km: float
    is_signature: bool


def compute_shape_city_compatibility(
    artwork: Artwork,
    activity: str = "running",
    difficulty: str = "medium",
) -> list[CityCompatibility]:
    """For a given artwork, compute which cities can support it and valid distance ranges.

    Implements the inverse of rank_shapes_for_city: given a shape, find compatible cities.
    Uses the algorithm's shape_city_fit_score (section 3) plus distance feasibility checks.
    """
    from app.core.seed import load_cities
    from app.graph_provider import graph_for_city

    sg = geom.build_shape_graph_from_normalized(artwork.normalized, artwork)
    results: list[CityCompatibility] = []

    for city in load_cities():
        graph_data = graph_for_city(city.id)
        if graph_data is None:
            continue
        graph, projector, bbox = graph_data

        filtered = graph.filter_for_profile(activity, difficulty)
        indexes = build_city_indexes(filtered, projector)
        features = extract_city_features(filtered, indexes, bbox)

        detour = _detour_factor(activity, city.road_density)
        constraints = MatchingConstraints(
            target_distance_km=artwork.recommended_min_km,
            activity=activity,
            difficulty=difficulty,
            detour_factor=detour,
            normalized_length=sg.normalized_length,
            symmetric=artwork.symmetric,
        )

        fit = _shape_city_fit_score(features, sg, constraints)

        # Compute valid distance range for this shape in this city
        # The shape needs to fit within the city bbox at a reasonable scale
        L = sg.normalized_length
        if L <= 0:
            continue

        minx, miny, maxx, maxy = bbox
        city_dim_m = min(maxx - minx, maxy - miny)
        # Max scale = city dimension / shape bounding box (normalized ~1.0)
        max_scale = city_dim_m * 0.45  # leave margin
        # Min scale = enough that the route is at least 3km
        min_scale_for_3km = 3000.0 / (L * detour)

        # Max distance = max_scale * L * detour
        max_km = (max_scale * L * detour) / 1000.0
        # Min distance = min_scale_for_3km * L * detour / 1000, but at least 3
        min_km = max(3.0, (min_scale_for_3km * L * detour) / 1000.0)

        # Clamp to artwork's recommended range with tolerance
        art_lo = artwork.recommended_min_km * 0.5
        art_hi = artwork.recommended_max_km * 2.0
        min_km = max(min_km, art_lo)
        max_km = min(max_km, art_hi)

        # Recommended distance
        rec_km = (artwork.recommended_min_km + artwork.recommended_max_km) / 2.0
        rec_km = max(min_km, min(max_km, rec_km))

        if max_km < min_km:
            continue

        is_signature = artwork.id in city.signature_artwork_ids
        # Signature shapes get a boost
        if is_signature:
            fit = min(1.0, fit + 0.15)

        # Only include cities with reasonable fit
        if fit < 0.30:
            continue

        results.append(CityCompatibility(
            city_id=city.id,
            city_name=city.name,
            fit_score=round(fit, 4),
            min_km=round(min_km, 1),
            max_km=round(max_km, 1),
            recommended_km=round(rec_km, 1),
            is_signature=is_signature,
        ))

    results.sort(key=lambda c: c.fit_score, reverse=True)
    return results


@dataclass
class ShapeCompatibility:
    artwork_id: str
    artwork_name: str
    category: str
    complexity: str
    preview_svg_url: str
    fit_score: float
    min_km: float
    max_km: float
    recommended_km: float
    is_signature: bool


def compute_city_shape_compatibility(
    city_id: str,
    activity: str = "running",
    difficulty: str = "medium",
) -> list[ShapeCompatibility]:
    """For a given city, compute which shapes are compatible and at what distances.

    This is the reverse of compute_shape_city_compatibility: given a city, find
    which artworks fit and rank them by shape_city_fit_score.
    """
    from app.core.seed import load_artworks, get_city

    city = get_city(city_id)
    if city is None:
        return []

    graph_data = _get_graph_for_city(city_id)
    if graph_data is None:
        return []
    graph, projector, bbox = graph_data

    filtered = graph.filter_for_profile(activity, difficulty)
    indexes = build_city_indexes(filtered, projector)
    features = extract_city_features(filtered, indexes, bbox)

    detour = _detour_factor(activity, city.road_density)
    results: list[ShapeCompatibility] = []

    for art in load_artworks():
        sg = geom.build_shape_graph_from_normalized(art.normalized, art.id, art.name, art.closed_path)
        L = sg.normalized_length
        if L <= 0:
            continue

        constraints = MatchingConstraints(
            target_distance_km=art.recommended_min_km,
            activity=activity,
            difficulty=difficulty,
            detour_factor=detour,
            normalized_length=L,
            symmetric=art.symmetric,
        )
        fit = _shape_city_fit_score(features, sg, constraints)

        minx, miny, maxx, maxy = bbox
        city_dim_m = min(maxx - minx, maxy - miny)
        max_scale = city_dim_m * 0.45
        min_scale_for_3km = 3000.0 / (L * detour)
        max_km = (max_scale * L * detour) / 1000.0
        min_km = max(3.0, (min_scale_for_3km * L * detour) / 1000.0)
        art_lo = art.recommended_min_km * 0.5
        art_hi = art.recommended_max_km * 2.0
        min_km = max(min_km, art_lo)
        max_km = min(max_km, art_hi)
        rec_km = (art.recommended_min_km + art.recommended_max_km) / 2.0
        rec_km = max(min_km, min(max_km, rec_km))
        if max_km < min_km:
            continue

        is_signature = art.id in city.signature_artwork_ids
        if is_signature:
            fit = min(1.0, fit + 0.15)
        if fit < 0.30:
            continue

        results.append(ShapeCompatibility(
            artwork_id=art.id,
            artwork_name=art.name,
            category=art.category,
            complexity=art.complexity,
            preview_svg_url=f"/assets/shapes/{art.id}.svg",
            fit_score=round(fit, 4),
            min_km=round(min_km, 1),
            max_km=round(max_km, 1),
            recommended_km=round(rec_km, 1),
            is_signature=is_signature,
        ))

    results.sort(key=lambda s: s.fit_score, reverse=True)
    return results


def _get_graph_for_city(city_id: str):
    from app.graph_provider import graph_for_city
    return graph_for_city(city_id)


@dataclass
class SVGAnchor:
    anchor_type: str
    point: tuple[float, float]
    weight: float


def extract_weighted_svg_anchors(shape_graph: geom.ShapeGraph) -> list[SVGAnchor]:
    anchors: list[SVGAnchor] = []
    for pl in shape_graph.polylines:
        if not pl.closed:
            anchors.append(SVGAnchor("endpoint", pl.points[0], 1.0))
            anchors.append(SVGAnchor("endpoint", pl.points[-1], 1.0))
    for pt in shape_graph.important_points:
        anchors.append(SVGAnchor("corner", pt, 1.0))
    all_pts = [pt for pl in shape_graph.polylines for pt in pl.points]
    if all_pts:
        for key_idx, key_fn in [(0, min), (0, max), (1, min), (1, max)]:
            extrema = key_fn(all_pts, key=lambda p: p[key_idx])
            anchors.append(SVGAnchor("extrema", extrema, 0.8))
    seen: set[tuple[int, int]] = set()
    deduped: list[SVGAnchor] = []
    for a in anchors:
        key = (round(a.point[0], 4), round(a.point[1], 4))
        if key not in seen:
            seen.add(key)
            deduped.append(a)
    return deduped


def _build_density_anchors(
    graph: RoadGraph,
    bbox_metric: tuple[float, float, float, float],
    target_distance_km: float,
    max_anchors: int = 20,
) -> list[MetricPoint]:
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
    anchors: list[MetricPoint] = []
    for (ci, cj), _ in best:
        cx = minx + (ci + 0.5) * cell_w
        cy = miny + (cj + 0.5) * cell_h
        anchors.append((cx, cy))
    return anchors


def generate_anchor_transforms(
    svg_graph: geom.ShapeGraph,
    svg_anchors: list[SVGAnchor],
    city_indexes: CityIndexes,
    constraints: MatchingConstraints,
) -> list[Transform]:
    graph = city_indexes.graph
    transforms: list[Transform] = []
    city_anchors = _build_density_anchors(
        graph, constraints.bbox_metric, constraints.target_distance_km, max_anchors=8
    )
    if constraints.preferred_neighborhood is not None:
        px, py = constraints.preferred_neighborhood
        city_anchors.sort(key=lambda a: math.hypot(a[0] - px, a[1] - py))
        city_anchors = city_anchors[: max(4, len(city_anchors) // 2)]

    L = svg_graph.normalized_length
    target_m = constraints.target_distance_km * 1000.0
    if L <= 0:
        return []
    scales = geom.estimate_scale_candidates(L, target_m, constraints.detour_factor)
    scales = scales[1:4]  # 3 scales (drop extremes)
    if constraints.preferred_scale is not None:
        scales = [constraints.preferred_scale * f for f in (0.90, 1.0, 1.10)]

    if constraints.symmetric:
        rotations = [0.0, 45.0, 90.0]
    else:
        rotations = [0.0, 30.0, 60.0, 90.0, 120.0]
    if constraints.preferred_rotation is not None:
        rotations = [constraints.preferred_rotation + d for d in (-10, 0, 10)]

    for anchor_xy in city_anchors:
        for scale in scales:
            for rotation in rotations:
                t = Transform(
                    translation=anchor_xy,
                    rotation_deg=rotation,
                    scale=scale,
                )
                transforms.append(t)
                if len(transforms) >= constraints.max_transformations:
                    return transforms
    return transforms


def score_svg_corridor_support(
    svg_graph: geom.ShapeGraph,
    transform: Transform,
    indexes: CityIndexes,
    constraints: MatchingConstraints,
) -> float:
    graph = indexes.graph
    transformed = apply_transform_to_metric(svg_graph.polylines, transform)
    if not _target_fits_bbox(transformed, constraints.bbox_metric):
        return 0.0

    corridor_width = SNAP_TOLERANCE_M[constraints.activity]
    total_length = 0.0
    matched_length = 0.0
    bearing_compat_sum = 0.0
    bearing_compat_count = 0
    components: set[int] = set()

    seg_sample_step = max(1, sum(len(pl.points) for pl in transformed) // 60)
    seg_idx = 0

    for pl in transformed:
        for i in range(len(pl.points) - 1):
            seg_idx += 1
            if seg_idx % seg_sample_step != 0 and i < len(pl.points) - 2:
                continue
            p1 = pl.points[i]
            p2 = pl.points[i + 1]
            seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            if seg_len < 1e-9:
                continue
            total_length += seg_len
            mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            edge, _, dist = graph.nearest_edge(mid, corridor_width)
            if edge is not None and dist < corridor_width:
                matched_length += seg_len
                svg_bearing = heading_deg(p1, p2)
                a = graph.nodes[edge.from_id]
                b = graph.nodes[edge.to_id]
                edge_bearing = heading_deg((a.x, a.y), (b.x, b.y))
                diff = angle_difference_deg(svg_bearing, edge_bearing)
                bearing_compat_sum += max(0.0, 1.0 - diff / 90.0)
                bearing_compat_count += 1
                comp = indexes.component_index.get(edge.from_id, -1)
                if comp >= 0:
                    components.add(comp)

    if total_length <= 0:
        return 0.0

    weighted_svg_coverage = matched_length / total_length
    bearing_compatibility = (
        bearing_compat_sum / bearing_compat_count if bearing_compat_count > 0 else 0.0
    )

    important_support = 0
    total_important = len(svg_graph.important_points)
    if total_important > 0:
        for ip in svg_graph.important_points:
            theta = math.radians(transform.rotation_deg)
            cos_t, sin_t = math.cos(theta), math.sin(theta)
            mx = transform.translation[0] + transform.scale * (ip[0] * cos_t - ip[1] * sin_t)
            my = transform.translation[1] + transform.scale * (ip[0] * sin_t + ip[1] * cos_t)
            edge, _, dist = graph.nearest_edge((mx, my), corridor_width * 1.5)
            if edge is not None:
                important_support += 1
        important_point_support = important_support / total_important
    else:
        important_point_support = 1.0

    if components:
        component_consistency = max(0.0, 1.0 - (len(components) - 1) / 5.0)
    else:
        component_consistency = 0.0

    target_m = constraints.target_distance_km * 1000.0
    est_length = svg_graph.normalized_length * transform.scale * constraints.detour_factor
    if target_m > 0:
        ratio = est_length / target_m
        scale_feasibility = max(0.0, 1.0 - abs(1.0 - ratio) * 0.5)
    else:
        scale_feasibility = 0.5

    corridor_score = (
        0.40 * weighted_svg_coverage
        + 0.25 * bearing_compatibility
        + 0.15 * important_point_support
        + 0.10 * component_consistency
        + 0.10 * scale_feasibility
    )
    return max(0.0, min(1.0, corridor_score))


def _empty_snap(target_lonlat: list[GeoPoint], projector: Projector) -> SnapResult:
    n = min(2, len(target_lonlat)) if target_lonlat else 0
    pts = target_lonlat[:n] if target_lonlat else []
    return SnapResult(
        acceptable=False,
        target_lonlat=target_lonlat,
        target_metric=[projector.to_metric(lon, lat) for lat, lon in target_lonlat],
        control_target_lonlat=pts,
        control_target_metric=[projector.to_metric(lon, lat) for lat, lon in pts],
        snapped_node_ids=[-1] * n,
        snapped_lonlat=pts,
        snapped_metric=[projector.to_metric(lon, lat) for lat, lon in pts],
        per_point_distance=[float("inf")] * n,
        within_tolerance_ratio=0.0,
        warnings=["no_candidates"],
    )


def beam_match_svg_to_streets(
    svg_graph: geom.ShapeGraph,
    transform: Transform,
    city_graph: RoadGraph,
    indexes: CityIndexes,
    router: Router,
    constraints: MatchingConstraints,
) -> SnappedResult:
    metric_polylines = apply_transform_to_metric(svg_graph.polylines, transform)
    target_lonlat: list[GeoPoint] = []
    for pl in metric_polylines:
        for x, y in pl.points:
            lat, lon = city_graph.projector.to_wgs84(x, y)
            target_lonlat.append((lat, lon))

    if len(target_lonlat) < 2:
        return SnappedResult(
            weighted_coverage=0.0,
            snap=_empty_snap(target_lonlat, city_graph.projector),
            candidate_nodes=[],
            matched_important=0,
            total_important=len(svg_graph.important_points),
        )

    snap = snap_polyline(
        target_lonlat, city_graph, city_graph.projector, constraints.activity
    )

    weights = svg_graph.weights
    ctrl_idx = _control_indices(len(target_lonlat))
    total_w = sum(weights[i] for i in ctrl_idx) if weights else len(ctrl_idx)
    matched_w = 0.0
    for i, nid in enumerate(snap.snapped_node_ids):
        if nid != -1 and snap.per_point_distance[i] <= router.snap_tolerance():
            w = weights[ctrl_idx[i]] if ctrl_idx[i] < len(weights) else 0.3
            matched_w += w
    coverage = matched_w / max(1.0, total_w) if total_w > 0 else 0.0

    matched_important = 0
    total_important = len(svg_graph.important_points)
    for i, nid in enumerate(snap.snapped_node_ids):
        if nid != -1 and snap.per_point_distance[i] <= router.snap_tolerance():
            ctrl_pt = snap.control_target_metric[i]
            for ip in svg_graph.important_points:
                theta = math.radians(transform.rotation_deg)
                cos_t, sin_t = math.cos(theta), math.sin(theta)
                mx = transform.translation[0] + transform.scale * (ip[0] * cos_t - ip[1] * sin_t)
                my = transform.translation[1] + transform.scale * (ip[0] * sin_t + ip[1] * cos_t)
                if math.hypot(ctrl_pt[0] - mx, ctrl_pt[1] - my) < router.snap_tolerance():
                    matched_important += 1
                    break

    k = constraints.candidates_per_sample
    beam_width = constraints.beam_width
    tol = router.snap_tolerance()

    candidates_per_point: list[list[tuple[int, float]]] = []
    for i, pt_metric in enumerate(snap.control_target_metric):
        cands: list[tuple[int, float]] = []
        edge, _, dist = city_graph.nearest_edge(pt_metric, tol)
        if edge is not None:
            fn = city_graph.nodes[edge.from_id]
            tn = city_graph.nodes[edge.to_id]
            d_fn = math.hypot(fn.x - pt_metric[0], fn.y - pt_metric[1])
            d_tn = math.hypot(tn.x - pt_metric[0], tn.y - pt_metric[1])
            cands.append((fn.id, d_fn))
            cands.append((tn.id, d_tn))
        orig_nid = snap.snapped_node_ids[i]
        if orig_nid != -1 and not any(c[0] == orig_nid for c in cands):
            cands.append((orig_nid, snap.per_point_distance[i]))
        cands.sort(key=lambda c: c[1])
        candidates_per_point.append(cands[:k])

    beam: list[tuple[float, list[int]]] = [(0.0, [])]
    for i, cands in enumerate(candidates_per_point):
        if not cands:
            for score, path in beam:
                path.append(-1)
            continue
        new_beam: list[tuple[float, list[int]]] = []
        for score, path in beam:
            for nid, dist in cands:
                emission = max(0.0, 1.0 - dist / tol) if tol > 0 else 0.5
                transition = 1.0
                if path:
                    prev = path[-1]
                    if prev == nid:
                        transition = 1.0
                    elif prev != -1 and nid != -1:
                        adj_ids = {v for v, _ in city_graph.adj.get(prev, [])}
                        if nid in adj_ids:
                            transition = 0.9
                        else:
                            prev_node = city_graph.nodes[prev]
                            cur_node = city_graph.nodes[nid]
                            eucl = math.hypot(
                                cur_node.x - prev_node.x, cur_node.y - prev_node.y
                            )
                            if i > 0 and i < len(snap.control_target_metric):
                                seg_d = math.hypot(
                                    snap.control_target_metric[i][0]
                                    - snap.control_target_metric[i - 1][0],
                                    snap.control_target_metric[i][1]
                                    - snap.control_target_metric[i - 1][1],
                                )
                                if seg_d > 0:
                                    transition = max(
                                        0.0,
                                        1.0 - abs(eucl - seg_d) / max(eucl, seg_d),
                                    )
                                else:
                                    transition = 0.3
                            else:
                                transition = 0.3
                new_score = score + emission + transition
                new_beam.append((new_score, path + [nid]))
        new_beam.sort(key=lambda x: x[0], reverse=True)
        beam = new_beam[:beam_width]

    if beam and beam[0][1]:
        best_path = beam[0][1]
        if all(nid != -1 for nid in best_path) and len(best_path) == len(
            snap.snapped_node_ids
        ):
            snapped_metric = [
                (city_graph.nodes[nid].x, city_graph.nodes[nid].y) for nid in best_path
            ]
            snapped_lonlat = [
                (city_graph.nodes[nid].lat, city_graph.nodes[nid].lon)
                for nid in best_path
            ]
            distances = [
                math.hypot(
                    snapped_metric[j][0] - snap.control_target_metric[j][0],
                    snapped_metric[j][1] - snap.control_target_metric[j][1],
                )
                for j in range(len(best_path))
            ]
            within = sum(1 for d in distances if d <= tol) / max(1, len(distances))
            snap = SnapResult(
                acceptable=within >= 0.8 and -1 not in best_path,
                target_lonlat=snap.target_lonlat,
                target_metric=snap.target_metric,
                control_target_lonlat=snap.control_target_lonlat,
                control_target_metric=snap.control_target_metric,
                snapped_node_ids=best_path,
                snapped_lonlat=snapped_lonlat,
                snapped_metric=snapped_metric,
                per_point_distance=distances,
                within_tolerance_ratio=within,
                warnings=snap.warnings,
            )

    return SnappedResult(
        weighted_coverage=coverage,
        snap=snap,
        candidate_nodes=candidates_per_point,
        matched_important=matched_important,
        total_important=total_important,
    )


def construct_shape_aware_route(
    svg_graph: geom.ShapeGraph,
    transform: Transform,
    snapped: SnappedResult,
    city_graph: RoadGraph,
    router: Router,
    constraints: MatchingConstraints,
) -> RouteResult:
    if not snapped.snap.acceptable:
        return RouteResult(
            valid=False,
            node_path=[],
            edges_used=[],
            route_metric=[],
            route_lonlat=[],
            length_m=0.0,
            detour_ratios=[],
            duplicate_fraction=0.0,
            keypoint_lonlat=[],
            warnings=["snap_not_acceptable"],
            segments_failed=1,
        )
    return repair_and_route(
        snapped.snap, city_graph, constraints.activity, constraints.difficulty
    )


def refine_transform(
    svg_graph: geom.ShapeGraph,
    initial_transform: Transform,
    snapped: SnappedResult,
    city_graph: RoadGraph,
    indexes: CityIndexes,
    router: Router,
    constraints: MatchingConstraints,
) -> tuple[Transform, SnappedResult, float]:
    best_t = initial_transform
    best_score = score_svg_corridor_support(
        svg_graph, initial_transform, indexes, constraints
    )

    step_m = 80.0
    for dx in (-step_m, 0, step_m):
        for dy in (-step_m, 0, step_m):
            if dx == 0 and dy == 0:
                continue
            t = Transform(
                translation=(
                    initial_transform.translation[0] + dx,
                    initial_transform.translation[1] + dy,
                ),
                rotation_deg=initial_transform.rotation_deg,
                scale=initial_transform.scale,
            )
            score = score_svg_corridor_support(
                svg_graph, t, indexes, constraints
            )
            if score > best_score + 0.01:
                best_score = score
                best_t = t

    return best_t, snapped, best_score


@dataclass
class RouteMatchScore:
    confidence: float
    fit_score: float
    shape_similarity_score: float
    distance_accuracy_score: float
    road_quality_score: float
    continuity_score: float
    elevation_score: float
    warnings: list[str]
    metrics: dict[str, float]


def _transform_point_to_metric(
    pt: tuple[float, float], transform: Transform
) -> MetricPoint:
    theta = math.radians(transform.rotation_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    mx = transform.translation[0] + transform.scale * (pt[0] * cos_t - pt[1] * sin_t)
    my = transform.translation[1] + transform.scale * (pt[0] * sin_t + pt[1] * cos_t)
    return (mx, my)


def score_svg_route_match(
    original_svg: str,
    svg_graph: geom.ShapeGraph,
    transform: Transform,
    route: RouteResult,
    constraints: MatchingConstraints,
    projector: Projector,
    graph: RoadGraph,
    uniqueness: float = 0.5,
) -> RouteMatchScore:
    if not route.valid or len(route.route_metric) < 2:
        return RouteMatchScore(
            confidence=0.0,
            fit_score=0.0,
            shape_similarity_score=0.0,
            distance_accuracy_score=0.0,
            road_quality_score=0.0,
            continuity_score=0.0,
            elevation_score=1.0,
            warnings=route.warnings + ["route_invalid"],
            metrics={},
        )

    transformed = apply_transform_to_metric(svg_graph.polylines, transform)
    svg_samples: list[MetricPoint] = [pt for pl in transformed for pt in pl.points]
    svg_weights = svg_graph.weights

    target_distance_m = constraints.target_distance_km * 1000.0
    tolerance_m = max(50.0, target_distance_m * 0.015)

    svg_geom = svg_geometry_score(
        svg_samples, svg_weights, route.route_metric, tolerance_m
    )
    rev_geom = reverse_geometry_score(route.route_metric, svg_samples, tolerance_m)

    corridor_width = SNAP_TOLERANCE_M[constraints.activity]
    total_w_len = 0.0
    matched_w_len = 0.0
    for pl in transformed:
        for i in range(len(pl.points) - 1):
            p1 = pl.points[i]
            p2 = pl.points[i + 1]
            seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            w = svg_weights[i] if i < len(svg_weights) else 0.3
            total_w_len += seg_len * w
            mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            edge, _, dist = graph.nearest_edge(mid, corridor_width)
            if edge is not None and dist < corridor_width:
                matched_w_len += seg_len * w
    w_coverage = weighted_coverage_score(matched_w_len, total_w_len)

    total_important = len(svg_graph.important_points)
    matched_important = 0
    for ip in svg_graph.important_points:
        mx, my = _transform_point_to_metric(ip, transform)
        min_d = min(
            math.hypot(rp[0] - mx, rp[1] - my) for rp in route.route_metric
        )
        if min_d < corridor_width * 1.5:
            matched_important += 1
    corner = corner_score(matched_important, total_important)

    endpoints_matched = 0
    total_endpoints = 0
    for pl in svg_graph.polylines:
        if not pl.closed:
            total_endpoints += 2
            for endpoint in (pl.points[0], pl.points[-1]):
                mx, my = _transform_point_to_metric(endpoint, transform)
                min_d = min(
                    math.hypot(rp[0] - mx, rp[1] - my) for rp in route.route_metric
                )
                if min_d < corridor_width:
                    endpoints_matched += 1
    topo = topology_score(
        endpoints_matched, total_endpoints, 0, 0, True, svg_graph.closed_path
    )

    routeability = routeability_score(route.length_m, target_distance_m)

    detour_ratios = route.detour_ratios if route.detour_ratios else [1.0]
    avg_detour = sum(detour_ratios) / len(detour_ratios)
    max_allowed = MAX_DETOUR_RATIO[constraints.activity]
    detour = detour_score_fn(avg_detour, max_allowed)

    cr = compute_confidence(
        svg_geometry=svg_geom,
        reverse_geometry=rev_geom,
        weighted_coverage=w_coverage,
        corner=corner,
        topology=topo,
        routeability=routeability,
        detour=detour,
        uniqueness=uniqueness,
    )

    target_lonlat = [projector.to_wgs84(x, y) for x, y in svg_samples]
    legacy = scoring_mod.score_candidate(
        target_lonlat, route, constraints.target_distance_km,
        constraints.activity, graph, projector, constraints.has_river,
    )

    warnings = route.warnings + legacy.warnings
    seen: set[str] = set()
    warnings = [w for w in warnings if not (w in seen or seen.add(w))]

    return RouteMatchScore(
        confidence=cr.confidence,
        fit_score=legacy.breakdown.fit_score,
        shape_similarity_score=legacy.breakdown.shape_similarity_score,
        distance_accuracy_score=legacy.breakdown.distance_accuracy_score,
        road_quality_score=legacy.breakdown.road_quality_score,
        continuity_score=legacy.breakdown.continuity_score,
        elevation_score=legacy.breakdown.elevation_score,
        warnings=warnings,
        metrics=cr.metrics,
    )


def _detour_factor(activity: str, road_density: float) -> float:
    sparse = 1.0 - max(0.0, min(1.0, road_density))
    if activity == "cycling":
        return 1.20 + 0.60 * sparse
    return 1.10 + 0.40 * sparse


def _build_constraints(
    city: City,
    activity: str,
    difficulty: str,
    target_distance_km: float,
    bbox: tuple[float, float, float, float],
    settings: Settings,
    algorithm_version: str,
    max_transformations: int,
    max_route_repairs: int,
) -> MatchingConstraints:
    detour = _detour_factor(activity, city.road_density)
    return MatchingConstraints(
        min_confidence=settings.min_confidence,
        min_corridor_score=settings.min_corridor_score,
        min_weighted_coverage=settings.min_weighted_coverage,
        coarse_candidate_limit=settings.coarse_candidate_limit,
        medium_candidate_limit=settings.medium_candidate_limit,
        final_candidate_limit=settings.final_candidate_limit,
        beam_width=settings.beam_width,
        candidates_per_sample=settings.candidates_per_sample,
        max_ai_retry_rounds=settings.max_ai_retry_rounds,
        target_distance_km=target_distance_km,
        activity=activity,
        difficulty=difficulty,
        bbox_metric=bbox,
        max_transformations=max_transformations,
        max_route_repairs=max_route_repairs,
        has_river=city.has_river,
        road_density=city.road_density,
        ai_retry_enabled=settings.ai_available,
        detour_factor=detour,
        algorithm_version=algorithm_version,
        signature_artwork_ids=list(city.signature_artwork_ids),
    )


def _diversify(matches: list[MatchResult], max_suggestions: int) -> list[MatchResult]:
    matches.sort(key=lambda x: x.fit_score, reverse=True)
    by_art: dict[str, list[MatchResult]] = {}
    for m in matches:
        by_art.setdefault(m.artwork_id, []).append(m)
    diversified: list[MatchResult] = []
    for arts in by_art.values():
        diversified.append(arts[0])
    diversified.sort(key=lambda x: x.fit_score, reverse=True)
    i = 0
    while len(diversified) < max_suggestions and i < len(matches):
        m = matches[i]
        if m not in diversified:
            diversified.append(m)
        i += 1
    return diversified[:max_suggestions]


def create_best_gps_art(
    city: City,
    graph: RoadGraph,
    projector: Projector,
    bbox: tuple[float, float, float, float],
    artworks: Iterable[Artwork],
    activity: str,
    difficulty: str,
    target_distance_km: float,
    max_suggestions: int,
    settings: Settings,
    algorithm_version: str = "svg-first-1.0",
    max_transformations: int = 1000,
    max_route_repairs: int = 100,
    progress_callback: Callable[[str, int], None] | None = None,
) -> list[MatchResult]:
    constraints = _build_constraints(
        city, activity, difficulty, target_distance_km, bbox, settings,
        algorithm_version, max_transformations, max_route_repairs,
    )

    if progress_callback:
        progress_callback("building_indexes", 10)
    filtered = graph.filter_for_profile(activity, difficulty)
    indexes = build_city_indexes(filtered, projector)
    city_features = extract_city_features(filtered, indexes, bbox)
    router = Router(graph=filtered, activity=activity, difficulty=difficulty)

    if progress_callback:
        progress_callback("parsing_shapes", 15)
    parsed_shapes: list[tuple[Artwork, geom.ShapeGraph]] = []
    for art in artworks:
        if not art.eligible_for(target_distance_km):
            continue
        sg = geom.build_shape_graph_from_normalized(
            art.normalized, art.id, art.name, art.closed_path
        )
        parsed_shapes.append((art, sg))

    if not parsed_shapes:
        return []

    if progress_callback:
        progress_callback("ranking_shapes", 20)
    ranked = rank_shapes_for_city(city_features, parsed_shapes, constraints)

    best_matches: list[MatchResult] = []
    per_shape_budget = max(120, constraints.max_transformations // max(1, len(ranked)))

    ranked_by_original = list(parsed_shapes)
    ranked_with_scores = [
        (art, sg, next((s for a, s2, s in ranked if a.id == art.id), 0.0))
        for art, sg in ranked_by_original
    ]

    for attempt in range(constraints.max_ai_retry_rounds + 1):
        if attempt == 0:
            shapes_to_try = ranked_with_scores
        else:
            shapes_to_try = ranked

        for art, sg, _fit_score in shapes_to_try:
            constraints.symmetric = art.symmetric
            constraints.normalized_length = sg.normalized_length

            if constraints.detail_level_override:
                level_names = [constraints.detail_level_override]
            else:
                level_names = ["coarse"]

            for level_name in level_names:
                level_sg = next(
                    (l for l in sg.levels if l.detail_level == level_name), sg
                )

                if progress_callback:
                    progress_callback("generating_transforms", 30)

                anchors = extract_weighted_svg_anchors(level_sg)
                constraints.max_transformations = per_shape_budget
                transforms = generate_anchor_transforms(
                    level_sg, anchors, indexes, constraints
                )
                if not transforms:
                    continue

                if progress_callback:
                    progress_callback("corridor_scoring", 40)
                coarse: list[tuple[Transform, float]] = []
                for t in transforms:
                    cs = score_svg_corridor_support(
                        level_sg, t, indexes, constraints
                    )
                    if cs >= constraints.min_corridor_score:
                        coarse.append((t, cs))
                if not coarse:
                    continue
                coarse.sort(key=lambda x: x[1], reverse=True)
                medium = coarse[: min(constraints.medium_candidate_limit, 20)]

                if progress_callback:
                    progress_callback("beam_matching", 55)
                snapped_list: list[tuple[Transform, SnappedResult, float]] = []
                for t, cs in medium:
                    snapped = beam_match_svg_to_streets(
                        level_sg, t, filtered, indexes, router, constraints
                    )
                    if snapped.weighted_coverage >= constraints.min_weighted_coverage:
                        snapped_list.append((t, snapped, cs))
                if not snapped_list:
                    continue
                snapped_list.sort(
                    key=lambda x: x[1].weighted_coverage, reverse=True
                )
                final = snapped_list[: min(constraints.final_candidate_limit, 5)]

                if progress_callback:
                    progress_callback("constructing_routes", 70)
                for t, snapped, cs in final:
                    refined_t, refined_snapped, refined_score = refine_transform(
                        level_sg, t, snapped, filtered, indexes, router, constraints
                    )
                    route = construct_shape_aware_route(
                        level_sg, refined_t, refined_snapped, filtered, router, constraints
                    )
                    if not route.valid:
                        continue

                    score = score_svg_route_match(
                        art.svg_text, level_sg, refined_t, route,
                        constraints, projector, filtered, uniqueness=0.5,
                    )

                    target_polys = transform_to_lonlat(
                        level_sg.polylines, refined_t, projector
                    )
                    target_lonlat = geom.flatten(target_polys)

                    anchor_lat, anchor_lon = projector.to_wgs84(
                        refined_t.translation[0], refined_t.translation[1]
                    )

                    fit_score = score.fit_score
                    if art.id in constraints.signature_artwork_ids:
                        fit_score = min(1.0, fit_score + 0.15)

                    best_matches.append(MatchResult(
                        artwork_id=art.id,
                        artwork_name=art.name,
                        confidence=score.confidence,
                        transform=refined_t,
                        route_lonlat=route.route_lonlat,
                        target_lonlat=target_lonlat,
                        keypoint_lonlat=route.keypoint_lonlat,
                        distance_km=route.length_m / 1000.0,
                        detail_level=level_name,
                        fit_score=fit_score,
                        shape_similarity_score=score.shape_similarity_score,
                        distance_accuracy_score=score.distance_accuracy_score,
                        road_quality_score=score.road_quality_score,
                        continuity_score=score.continuity_score,
                        elevation_score=score.elevation_score,
                        warnings=score.warnings,
                        debug={
                            "algorithmVersion": algorithm_version,
                            "placement": {
                                "anchorLat": round(anchor_lat, 6),
                                "anchorLon": round(anchor_lon, 6),
                                "scaleMeters": round(refined_t.scale, 1),
                                "rotationDegrees": refined_t.rotation_deg,
                            },
                            "detailLevel": level_name,
                            "confidence": round(score.confidence, 4),
                            "corridorScore": round(cs, 4),
                            "refinedScore": round(refined_score, 4),
                            "scores": {
                                "fitScore": round(score.fit_score, 4),
                                "shapeSimilarityScore": round(
                                    score.shape_similarity_score, 4
                                ),
                                "confidence": round(score.confidence, 4),
                                **{
                                    k: round(v, 4)
                                    for k, v in score.metrics.items()
                                },
                            },
                            "search": {
                                "transformsGenerated": len(transforms),
                                "coarseCandidates": len(coarse),
                                "mediumCandidates": len(medium),
                                "snappedCandidates": len(snapped_list),
                                "finalCandidates": len(final),
                            },
                        },
                    ))

                shape_matches = [
                    m for m in best_matches if m.artwork_id == art.id
                ]
                if len(shape_matches) >= 3:
                    break

            if len(best_matches) >= max_suggestions:
                break

        if best_matches:
            best_matches.sort(key=lambda x: x.fit_score, reverse=True)
            if best_matches[0].fit_score >= ACCEPT_FIT_THRESHOLD:
                break

        if attempt < constraints.max_ai_retry_rounds and constraints.ai_retry_enabled:
            from app.core.ai_assist import (
                build_matching_diagnostics,
                propose_retry_plan,
                apply_ai_retry_plan,
            )
            diagnostics = build_matching_diagnostics(
                filtered, indexes, ranked, best_matches, constraints
            )
            ai_plan = propose_retry_plan(diagnostics, settings)
            ranked, constraints = apply_ai_retry_plan(
                ai_plan, ranked, constraints
            )

    if progress_callback:
        progress_callback("scoring", 85)

    if not best_matches:
        return []

    best_matches.sort(key=lambda x: x.fit_score, reverse=True)

    if len(best_matches) >= 2:
        best_conf = best_matches[0].confidence
        second_conf = best_matches[1].confidence
        if best_conf > 0:
            uniq = uniqueness_score(best_conf, second_conf)
            best_matches[0].debug["uniquenessScore"] = round(uniq, 4)

    if progress_callback:
        progress_callback("storing_results", 95)

    return _diversify(best_matches, max_suggestions)
