"""Geographic maths: distances, equirectangular projection, shape normalisation.

Unit space conventions
----------------------
After :func:`normalize_shape`, a shape's bounding box has its larger side
equal to ``1.0`` and its centroid at the origin. A point ``(x, y)`` in unit
space maps to a real-world offset of ``(x * scale_m, y * scale_m)`` metres from
the placement centre, then to lat/lon via equirectangular projection. This is
accurate enough at city scale (<~50 km).
"""

from __future__ import annotations

import math

import numpy as np

EARTH_R_M = 6_371_000.0

Pt = tuple[float, float]            # unit-space (x, y)
LatLon = tuple[float, float]        # (lat, lon)
Path = list[Pt]

_MIN_COS_LAT = 1e-8


# --------------------------------------------------------------------------- #
# Distances
# --------------------------------------------------------------------------- #
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two lat/lon points."""
    values = (lat1, lon1, lat2, lon2)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("coordinates must be finite")
    if not (-90.0 <= lat1 <= 90.0 and -90.0 <= lat2 <= 90.0):
        raise ValueError("latitude must be between -90 and 90 degrees")
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_R_M * math.asin(min(1.0, math.sqrt(a)))


def path_distance_m(points: list[LatLon]) -> float:
    """Total length (m) of a lat/lon polyline."""
    return sum(havers(*a, *b) for a, b in zip(points, points[1:], strict=False))


def havers(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    return haversine(a_lat, a_lon, b_lat, b_lon)


def unit_path_length(path: Path) -> float:
    """Euclidean length of a unit-space polyline."""
    if len(path) < 2:
        return 0.0
    arr = np.asarray(path, dtype=float)
    return float(np.hypot(np.diff(arr[:, 0]), np.diff(arr[:, 1])).sum())


def unit_perimeter(paths: list[Path]) -> float:
    """Total drawn length across all sub-paths (used to estimate route size)."""
    return sum(unit_path_length(p) for p in paths)


# --------------------------------------------------------------------------- #
# Shape transforms (unit space)
# --------------------------------------------------------------------------- #
def _all_points(paths: list[Path]) -> np.ndarray:
    non_empty: list[np.ndarray] = []
    for path in paths:
        if not path:
            continue
        points = np.asarray(path, dtype=float)
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("each shape path must contain two-dimensional points")
        if not np.isfinite(points).all():
            raise ValueError("shape coordinates must be finite")
        non_empty.append(points)
    if not non_empty:
        return np.zeros((0, 2))
    return np.concatenate(non_empty)


def normalize_shape(paths: list[Path]) -> list[Path]:
    """Centre on centroid, scale so the larger bounding-box side == 1.0."""
    pts = _all_points(paths)
    if pts.size == 0:
        return [[(0.0, 0.0)]]
    centroid = pts.mean(axis=0)
    shifted = pts - centroid
    extents = shifted.max(axis=0) - shifted.min(axis=0)
    scale = float(extents.max())
    if scale < 1e-9:
        scale = 1.0
    out: list[Path] = []
    for path in paths:
        out.append([(float((x - centroid[0]) / scale), float((y - centroid[1]) / scale)) for x, y in path])
    return out


def rotate_point(x: float, y: float, angle_rad: float) -> Pt:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return (x * c - y * s, x * s + y * c)


def rotate_shape(paths: list[Path], angle_rad: float) -> list[Path]:
    return [[rotate_point(x, y, angle_rad) for x, y in path] for path in paths]


def offset_shape(paths: list[Path], dx: float, dy: float) -> list[Path]:
    return [[(x + dx, y + dy) for x, y in path] for path in paths]


# --------------------------------------------------------------------------- #
# Multi-stroke route construction (unit space)
# --------------------------------------------------------------------------- #
def stitch_paths(paths: list[Path]) -> Path:
    """Join separate strokes with short deterministic transfer segments.

    A GPS route must be continuous even when a drawing contains separate
    strokes (letters, eyes, rays, and similar details). The first, usually
    dominant, stroke is kept as the start. Remaining strokes are greedily
    selected by nearest endpoint and reversed when that shortens the transfer.
    This preserves the authored strokes while avoiding arbitrary cross-shape
    connectors and the unnecessary distance they introduce.
    """
    remaining = [list(path) for path in paths if path]
    if not remaining:
        return []

    route = remaining.pop(0)
    while remaining:
        current = route[-1]
        best_index = 0
        reverse = False
        best_distance = float("inf")
        for index, path in enumerate(remaining):
            to_start = math.hypot(path[0][0] - current[0], path[0][1] - current[1])
            to_end = math.hypot(path[-1][0] - current[0], path[-1][1] - current[1])
            candidate_distance = min(to_start, to_end)
            candidate_reverse = to_end < to_start
            if candidate_distance < best_distance:
                best_index = index
                reverse = candidate_reverse
                best_distance = candidate_distance

        next_path = remaining.pop(best_index)
        if reverse:
            next_path.reverse()
        if route[-1] == next_path[0]:
            route.extend(next_path[1:])
        else:
            route.extend(next_path)
    return route


# --------------------------------------------------------------------------- #
# Smoothing / densification (unit space)
# --------------------------------------------------------------------------- #
def densify_path(path: Path, max_step: float = 0.01) -> Path:
    """Insert intermediate points so no segment exceeds ``max_step`` in length."""
    if not math.isfinite(max_step) or max_step <= 0:
        raise ValueError("max_step must be a positive finite number")
    if len(path) < 2:
        return list(path)
    out: Path = [path[0]]
    for (x0, y0), (x1, y1) in zip(path, path[1:], strict=False):
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg <= max_step:
            out.append((x1, y1))
            continue
        n = max(1, int(math.ceil(seg / max_step)))
        for i in range(1, n + 1):
            f = i / n
            out.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
    return out


def catmull_rom_smooth(path: Path, *, closed: bool = False, subdivisions: int = 8) -> Path:
    """Smooth a polyline via Catmull-Rom splines.

    For each segment between consecutive control points, ``subdivisions``
    interpolated points are generated, producing a C1-continuous curve that
    passes through every original point. Closed paths wrap the control points
    cyclically; open paths duplicate the endpoints.
    """
    if subdivisions < 1:
        raise ValueError("subdivisions must be at least one")
    pts = list(path)
    if closed and len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    n = len(pts)
    if n < 3:
        return list(pts) + ([pts[0]] if closed and pts else [])

    if closed:
        control = [pts[-1]] + pts + [pts[0], pts[1]]
    else:
        control = [pts[0]] + pts + [pts[-1]]

    out: Path = []
    segments = n if closed else n - 1
    for i in range(segments):
        p0 = control[i]
        p1 = control[i + 1]
        p2 = control[i + 2]
        p3 = control[i + 3]
        for j in range(subdivisions):
            t = j / subdivisions
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            out.append((x, y))
    out.append(pts[-1] if not closed else pts[0])
    return out


def smooth_paths(paths: list[Path], *, closed: bool = False, subdivisions: int = 8) -> list[Path]:
    """Apply Catmull-Rom smoothing to every sub-path."""
    return [catmull_rom_smooth(p, closed=closed, subdivisions=subdivisions) for p in paths]


# --------------------------------------------------------------------------- #
# Unit <-> lat/lon projection
# --------------------------------------------------------------------------- #
def unit_to_latlon(x: float, y: float, center_lat: float, center_lon: float, scale_m: float) -> LatLon:
    """Equirectangular: unit (x,y) with ``scale_m`` metres per unit -> lat/lon."""
    if not all(math.isfinite(value) for value in (x, y, center_lat, center_lon, scale_m)):
        raise ValueError("projection values must be finite")
    if not (-90.0 < center_lat < 90.0):
        raise ValueError("projection centre latitude must be strictly between -90 and 90")
    if scale_m <= 0:
        raise ValueError("scale_m must be positive")
    dlat = (y * scale_m) / EARTH_R_M * (180.0 / math.pi)
    cos_lat = math.cos(math.radians(center_lat))
    if abs(cos_lat) < _MIN_COS_LAT:
        raise ValueError("projection is unstable too close to a pole")
    dlon = (x * scale_m) / (EARTH_R_M * cos_lat) * (180.0 / math.pi)
    lat, lon = center_lat + dlat, center_lon + dlon
    if not (-90.0 <= lat <= 90.0):
        raise ValueError("projected latitude falls outside the valid range")
    return (lat, lon)


def latlon_to_unit(lat: float, lon: float, center_lat: float, center_lon: float, scale_m: float) -> Pt:
    if not all(math.isfinite(value) for value in (lat, lon, center_lat, center_lon, scale_m)):
        raise ValueError("projection values must be finite")
    if not (-90.0 <= lat <= 90.0 and -90.0 < center_lat < 90.0):
        raise ValueError("latitude falls outside the valid range")
    if scale_m <= 0:
        raise ValueError("scale_m must be positive")
    dlat_m = math.radians(lat - center_lat) * EARTH_R_M
    dlon_m = math.radians(lon - center_lon) * EARTH_R_M * math.cos(math.radians(center_lat))
    return (dlon_m / scale_m, dlat_m / scale_m)


def project_paths(
    paths: list[Path], center_lat: float, center_lon: float, scale_m: float
) -> list[LatLon]:
    """Flatten all sub-paths into one ordered waypoint list in lat/lon."""
    out: list[LatLon] = []
    for path in paths:
        for x, y in path:
            out.append(unit_to_latlon(x, y, center_lat, center_lon, scale_m))
    return out


# --------------------------------------------------------------------------- #
# Bearings / grid alignment
# --------------------------------------------------------------------------- #
def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees [0, 360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    y = math.sin(dlmb) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def bbox_long_axis_heading(bbox: tuple[float, float, float, float]) -> float:
    """Heading (degrees) of the longer side of a city bounding box.

    This is a deterministic coarse orientation hint, not a measurement of
    street bearings. Known-city context or routing feedback should override it.
    """
    south, north, west, east = bbox
    cy = (south + north) / 2
    h = haversine(south, west, north, west)        # N-S extent
    w = haversine(cy, west, cy, east)              # E-W extent
    if w >= h:
        return bearing(cy, west, cy, east)         # roughly 90°
    return bearing(south, west, north, west)       # roughly 0°
