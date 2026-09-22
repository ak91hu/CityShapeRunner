"""Carry authored semantic cues through transforms and measure street coverage.

Feature geometry shares the complete drawing's normalization and anchor shift.
It is never independently centered or stitched: doing so would lose its identity
and location in multi-stroke drawings. Scores describe geometric preservation,
not independent semantic recognition.
"""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import LineString, Point

from ..state import Shape, WorkflowState
from . import geo


def normalize_with_features(shape: Shape) -> None:
    normalized = geo.normalize_shape(shape.paths)
    points = [point for path in shape.paths for point in path]
    new_points = [point for path in normalized for point in path]
    if points and new_points:
        scale = max(max(p[i] for p in points) - min(p[i] for p in points) for i in (0, 1))
        scale = scale if scale >= 1e-9 else 1.0
        origin, target = points[0], new_points[0]
        shape.feature_paths = {
            key: [[((x - origin[0]) / scale + target[0], (y - origin[1]) / scale + target[1])
                   for x, y in path] for path in paths]
            for key, paths in shape.feature_paths.items()
        }
    shape.paths = normalized


def projected_features(state: WorkflowState) -> dict[str, list[geo.Path]]:
    from ..agents.placement_agent import _metres_to_dlat, _metres_to_dlon
    if state.shape is None or state.route_draft is None:
        return {}
    draft, shape = state.route_draft, state.shape
    latitude = draft.center_lat + _metres_to_dlat(draft.lat_offset_m)
    longitude = draft.center_lon + _metres_to_dlon(draft.lon_offset_m, draft.center_lat)
    angle = math.radians(draft.rotation_deg)
    shift = (0.0, 0.0)
    if draft.anchored_start is not None:
        route = geo.stitch_paths(geo.rotate_shape(shape.paths, angle))
        first = geo.project_paths([route], latitude, longitude, draft.scale_m)[0]
        shift = (draft.anchored_start[0] - first[0], draft.anchored_start[1] - first[1])
    result = {}
    for key, paths in shape.feature_paths.items():
        transformed = []
        for path in geo.rotate_shape(paths, angle):
            transformed.append([(lat + shift[0], lon + shift[1]) for lat, lon in
                                geo.project_paths([path], latitude, longitude, draft.scale_m)])
        result[key] = transformed
    return result


def measure_features(state: WorkflowState) -> tuple[list[dict], float | None]:
    if not state.shape or not state.snapped or not state.snapped.snapped or len(state.snapped.points) < 2:
        return [], None
    projected = projected_features(state)
    if not projected:
        return [], None
    center = state.snapped.points[0]
    road = LineString([geo.latlon_to_unit(lat, lon, *center, 1) for lat, lon in state.snapped.points])
    spec = {feature.id: feature for feature in state.shape.spec.recognition_features} if state.shape.spec else {}
    measurements: list[dict] = []
    for key, paths in projected.items():
        feature = spec.get(key)
        lines = [LineString([geo.latlon_to_unit(lat, lon, *center, 1) for lat, lon in path])
                 for path in paths if len(path) >= 2]
        length = sum(line.length for line in lines)
        # Short identity cues deserve a tighter metre tolerance. Scale cannot
        # make an absent ear pass just because the complete route is large.
        tolerance = min(65.0, max(12.0, length * 0.12))
        weighted_distances = []
        for line in lines:
            count = max(3, min(48, math.ceil(line.length / 15)))
            if line.length <= 0:
                continue
            for distance in np.linspace(0, line.length, count):
                point = line.interpolate(float(distance))
                weighted_distances.append((road.distance(point), line.length / count))
        if not weighted_distances:
            continue
        total_weight = sum(weight for _, weight in weighted_distances)
        coverage = sum(weight for distance, weight in weighted_distances if distance <= tolerance) / total_weight
        deviation = sum(distance * weight for distance, weight in weighted_distances) / total_weight
        # Include geometric turn evidence: points along a chord alone must not
        # claim preservation of a salient tip far from the routed line.
        worst = max(road.distance(Point(point)) for line in lines for point in line.coords)
        score = coverage * math.exp(-deviation / tolerance) * math.exp(-max(0, worst - tolerance) / (2 * tolerance))
        measurements.append({"feature_id": key, "label": feature.label if feature else key,
                             "importance": feature.importance if feature else 3,
                             "score": score, "coverage": coverage, "mean_deviation_m": deviation,
                             "max_deviation_m": worst, "tolerance_m": tolerance,
                             "preserved": score >= 0.65, "expected_paths": paths})
    weights = sum(row["importance"] for row in measurements)
    overall = sum(row["score"] * row["importance"] for row in measurements) / weights if weights else None
    return measurements, overall


def propose_feature_repair(state: WorkflowState) -> bool:
    """Reserve at most two existing refinement attempts for lost semantic cues."""
    if state.validation is None or state.route_draft is None:
        return False
    attempts = [row for row in state.history if row.get("feature_repair_attempt")]
    if len(attempts) >= 2:
        return False
    lost = sorted((row for row in state.validation.feature_measurements if not row["preserved"]),
                  key=lambda row: (-row["importance"], row["score"]))
    if not lost:
        return False
    key = lost[0]["feature_id"]
    variant = sum(row["feature_id"] == key for row in attempts)
    state.route_draft.feature_repair = key
    state.route_draft.feature_repair_variant = variant
    state.history.append({"agent": "refinement", "feature_repair_attempt": True,
                          "feature_id": key, "variant": variant})
    return True


def feature_repair_guides(state: WorkflowState) -> geo.Path:
    """Pin the feature's endpoints and strongest off-road tip in contour order.

    The ideal reference stays unchanged. A second attempt moves only the tip
    slightly outward to reach a different nearby street. Directions still owns
    connectivity and the unchanged drawing is used for final validation.
    """
    from . import ors_client
    draft = state.route_draft
    if draft is None:
        return []
    paths = projected_features(state).get(draft.feature_repair or "", [])
    feature = [point for path in paths for point in path]
    if not feature or len(draft.waypoints) < 2:
        return draft.waypoints
    center = draft.waypoints[0]
    def project(p):
        return geo.latlon_to_unit(*p, *center, 1)
    contour = LineString([project(p) for p in draft.waypoints])
    road = LineString([project(p) for p in state.snapped.points]) if state.snapped and len(state.snapped.points) > 1 else contour
    tip = max(feature, key=lambda p: road.distance(Point(project(p))))
    guide = ors_client._subsample(draft.waypoints, closed=draft.closed, max_points=20)
    # Keep first/last fixed, including requested start bearing's first segment.
    interior = [(contour.project(Point(project(p))), p) for p in guide[1:-1]]
    for point in (feature[0], tip, feature[-1]):
        position = contour.project(Point(project(point)))
        if position <= 1e-6 or position >= contour.length - 1e-6:
            continue
        if draft.preferred_start_direction_deg is not None and position <= contour.project(Point(project(guide[1]))):
            continue
        replacement = point
        if point == tip and draft.feature_repair_variant:
            xy = Point(project(point))
            nearest = road.interpolate(road.project(xy))
            dx, dy = xy.x - nearest.x, xy.y - nearest.y
            norm = math.hypot(dx, dy)
            if norm > 1e-6:
                step = min(25.0, norm * 0.5)
                replacement = geo.unit_to_latlon(xy.x + dx / norm * step, xy.y + dy / norm * step, *center, 1)
        if state.map_placement is not None:
            manual = state.map_placement
            # Local outward perturbations cannot escape the original footprint
            # by more than the explicitly allowed neighbourhood search radius.
            if geo.haversine(*point, *replacement) > manual.search_radius_m:
                replacement = point
        elif state.plan and state.plan.city_bbox:
            south, north, west, east = state.plan.city_bbox
            if not (south <= replacement[0] <= north and west <= replacement[1] <= east):
                replacement = point
        interior = [(distance, p) for distance, p in interior if abs(distance - position) > 0.1]
        interior.append((position, replacement))
    interior.sort(key=lambda item: item[0])
    return [guide[0], *(point for _, point in interior), guide[-1]]
