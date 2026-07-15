from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from app.core.units import Projector

type GeoPoint = tuple[float, float]  # (lat, lon)
type MetricPoint = tuple[float, float]  # (x, y)


@dataclass
class Polyline:
    points: list[tuple[float, float]]
    closed: bool = False


# --------------------------------------------------------------------------- #
# SVG parsing
# --------------------------------------------------------------------------- #

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _tokenize_numbers(d: str) -> list[float]:
    return [float(t) for t in _NUM_RE.findall(d)]


def _sample_cubic(p0, p1, p2, p3, n: int = 48) -> list[tuple[float, float]]:
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def _sample_quadratic(p0, p1, p2, n: int = 40) -> list[tuple[float, float]]:
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**2 * p0[0] + 2 * mt * t * p1[0] + t**2 * p2[0]
        y = mt**2 * p0[1] + 2 * mt * t * p1[1] + t**2 * p2[1]
        pts.append((x, y))
    return pts


def _parse_path(d: str) -> list[Polyline]:
    """Parse an SVG path `d` string into a list of Polylines with sampled beziers."""
    polylines: list[Polyline] = []
    current: list[tuple[float, float]] = []
    start: tuple[float, float] = (0.0, 0.0)
    cur = (0.0, 0.0)

    # Scan commands and read subsequent numbers until the next command letter.
    idx = 0
    cmd_seq: list[tuple[str, list[float]]] = []
    while idx < len(d):
        ch = d[idx]
        if ch in "MmLlHhVvCcSsQqTtZzAa":
            c = ch
            idx += 1
            # read numbers until next command letter
            j = idx
            while j < len(d) and d[j] not in "MmLlHhVvCcSsQqTtZzAa":
                j += 1
            num_str = d[idx:j]
            cmd_seq.append((c, _tokenize_numbers(num_str)))
            idx = j
        else:
            idx += 1

    for c, args in cmd_seq:
        rel = c.islower()
        C = c.upper()
        k = 0
        if C == "M":
            while k + 1 < len(args) or (k == 0 and len(args) >= 2):
                if k + 1 >= len(args) and not (k == 0 and len(args) == 2):
                    break
                x, y = args[k], args[k + 1]
                if rel and current:
                    x += cur[0]
                    y += cur[1]
                cur = (x, y)
                if not current:
                    start = cur
                current.append(cur)
                k += 2
                # subsequent implicit coords are lineto
                C = "L"
                c = "L"
        elif C == "L":
            while k + 1 < len(args):
                x, y = args[k], args[k + 1]
                if rel:
                    x += cur[0]
                    y += cur[1]
                cur = (x, y)
                current.append(cur)
                k += 2
        elif C == "H":
            while k < len(args):
                x = args[k] + (cur[0] if rel else 0.0)
                cur = (x, cur[1])
                current.append(cur)
                k += 1
        elif C == "V":
            while k < len(args):
                y = args[k] + (cur[1] if rel else 0.0)
                cur = (cur[0], y)
                current.append(cur)
                k += 1
        elif C == "C":
            while k + 5 < len(args):
                p1 = (args[k] + (cur[0] if rel else 0), args[k + 1] + (cur[1] if rel else 0))
                p2 = (args[k + 2] + (cur[0] if rel else 0), args[k + 3] + (cur[1] if rel else 0))
                p3 = (args[k + 4] + (cur[0] if rel else 0), args[k + 5] + (cur[1] if rel else 0))
                current.extend(_sample_cubic(cur, p1, p2, p3))
                cur = p3
                k += 6
        elif C == "S":
            while k + 3 < len(args):
                p2 = (args[k] + (cur[0] if rel else 0), args[k + 1] + (cur[1] if rel else 0))
                p3 = (args[k + 2] + (cur[0] if rel else 0), args[k + 3] + (cur[1] if rel else 0))
                current.extend(_sample_cubic(cur, cur, p2, p3))
                cur = p3
                k += 4
        elif C == "Q":
            while k + 3 < len(args):
                p1 = (args[k] + (cur[0] if rel else 0), args[k + 1] + (cur[1] if rel else 0))
                p2 = (args[k + 2] + (cur[0] if rel else 0), args[k + 3] + (cur[1] if rel else 0))
                current.extend(_sample_quadratic(cur, p1, p2))
                cur = p2
                k += 4
        elif C == "T":
            while k + 1 < len(args):
                p2 = (args[k] + (cur[0] if rel else 0), args[k + 1] + (cur[1] if rel else 0))
                current.extend(_sample_quadratic(cur, cur, p2))
                cur = p2
                k += 2
        elif C == "Z":
            if current and current[0] != current[-1]:
                current.append(start)
            if current:
                polylines.append(Polyline(points=current, closed=True))
            current = []
            cur = start
        # Arc (A) not supported by generated library; skip gracefully.
    if current:
        polylines.append(Polyline(points=current, closed=False))
    return polylines


def _points_from_basic(el: ET.Element, tag: str) -> list[Polyline]:
    def num(attr: str) -> float:
        return float(el.get(attr, "0"))

    if tag == "line":
        return [Polyline(points=[(num("x1"), num("y1")), (num("x2"), num("y2"))], closed=False)]
    if tag == "rect":
        x, y, w, h = num("x"), num("y"), num("width"), num("height")
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        return [Polyline(points=pts, closed=True)]
    if tag == "polyline":
        pts = [(float(a), float(b)) for a, b in _pair_iter(el.get("points", ""))]
        return [Polyline(points=pts, closed=False)]
    if tag == "polygon":
        pts = [(float(a), float(b)) for a, b in _pair_iter(el.get("points", ""))]
        if pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        return [Polyline(points=pts, closed=True)]
    if tag == "circle":
        cx, cy, r = num("cx"), num("cy"), num("r")
        n = 96
        pts = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]
        return [Polyline(points=pts, closed=True)]
    if tag == "ellipse":
        cx, cy, rx, ry = num("cx"), num("cy"), num("rx"), num("ry")
        n = 96
        pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]
        return [Polyline(points=pts, closed=True)]
    return []


def _pair_iter(s: str):
    nums = _tokenize_numbers(s)
    for i in range(0, len(nums) - 1, 2):
        yield nums[i], nums[i + 1]


def parse_svg(svg_text: str) -> list[Polyline]:
    """Parse SVG text into ordered polylines (SVG user coordinates, y-down)."""
    root = ET.fromstring(svg_text)
    out: list[Polyline] = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag == "path":
            d = el.get("d", "")
            if d:
                out.extend(_parse_path(d))
        elif tag in {"line", "rect", "polyline", "polygon", "circle", "ellipse"}:
            out.extend(_points_from_basic(el, tag))
    return out


# --------------------------------------------------------------------------- #
# Normalization & transforms
# --------------------------------------------------------------------------- #


def polylines_bbox(polylines: list[Polyline]) -> tuple[float, float, float, float]:
    xs = [p[0] for pl in polylines for p in pl.points]
    ys = [p[1] for pl in polylines for p in pl.points]
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def normalize_polylines(polylines: list[Polyline]) -> list[Polyline]:
    """Normalize to [-0.5, 0.5] preserving aspect ratio (uses the larger dimension)."""
    minx, miny, maxx, maxy = polylines_bbox(polylines)
    w = maxx - minx
    h = maxy - miny
    scale = max(w, h) or 1.0
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    # Flip y so that the shape is upright in a conventional y-up metric frame,
    # and shift both axes so normalized coordinates lie in [-0.5, 0.5].
    out = []
    for pl in polylines:
        pts = [((p[0] - cx) / scale, (cy - p[1]) / scale) for p in pl.points]
        out.append(Polyline(points=pts, closed=pl.closed))
    return out


def normalized_length(normalized: list[Polyline]) -> float:
    """Total polyline length in normalized units (after normalization)."""
    total = 0.0
    for pl in normalized:
        for i in range(len(pl.points) - 1):
            total += math.hypot(pl.points[i + 1][0] - pl.points[i][0], pl.points[i + 1][1] - pl.points[i][1])
    return total


def aspect_ratio(normalized: list[Polyline]) -> float:
    minx, miny, maxx, maxy = polylines_bbox(normalized)
    w = maxx - minx
    h = maxy - miny
    if h == 0:
        return 1.0
    return w / h


def transform_polyline(
    normalized: list[Polyline],
    anchor_latlon: GeoPoint,
    scale_m: float,
    rotation_deg: float,
    projector: Projector,
) -> list[Polyline]:
    """Place normalized artwork at anchor with scale (meters per unit) and rotation.

    Returns polylines in WGS84 (lat, lon). Rotation is counter-clockwise in the
    y-up metric frame. The anchor maps to the artwork origin (0,0 in normalized
    space), i.e. the bottom-left of the artwork bbox.
    """
    ax, ay = projector.to_metric(anchor_latlon[1], anchor_latlon[0])
    theta = math.radians(rotation_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    out = []
    for pl in normalized:
        pts = []
        for nx, ny in pl.points:
            rx = scale_m * (nx * cos_t - ny * sin_t)
            ry = scale_m * (nx * sin_t + ny * cos_t)
            lat, lon = projector.to_wgs84(ax + rx, ay + ry)
            pts.append((lat, lon))
        out.append(Polyline(points=pts, closed=pl.closed))
    return out


def flatten(polylines: list[Polyline]) -> list[GeoPoint]:
    out: list[GeoPoint] = []
    for pl in polylines:
        out.extend(pl.points)
    return out


def estimate_scale_candidates(
    normalized_len: float, target_distance_m: float, detour_factor: float
) -> list[float]:
    if normalized_len <= 0:
        return [target_distance_m]
    base = target_distance_m / (normalized_len * detour_factor)
    return [f * base for f in (0.75, 0.90, 1.00, 1.10, 1.25)]


def rotation_candidates(symmetric: bool) -> list[float]:
    if symmetric:
        return [0.0, 45.0, 90.0, 135.0]
    return [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 330.0]


# --------------------------------------------------------------------------- #
# Similarity metrics (section 53)
# --------------------------------------------------------------------------- #


def resample_polyline(points: list[tuple[float, float]], n: int = 512) -> list[tuple[float, float]]:
    if len(points) < 2:
        return list(points)
    seg = []
    for i in range(len(points) - 1):
        seg.append(math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]))
    total = sum(seg)
    if total == 0:
        return [points[0]] * n
    out = []
    for k in range(n):
        d = total * k / (n - 1)
        acc = 0.0
        for i, s in enumerate(seg):
            if acc + s >= d:
                t = (d - acc) / s if s else 0.0
                out.append((points[i][0] + t * (points[i + 1][0] - points[i][0]),
                            points[i][1] + t * (points[i + 1][1] - points[i][1])))
                break
            acc += s
        else:
            out.append(points[-1])
    return out


def _normalize_for_shape(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not points:
        return points
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    minx, miny = min(xs), min(ys)
    w = max(xs) - minx
    h = max(ys) - miny
    scale = max(w, h) or 1.0
    return [((p[0] - minx) / scale, (p[1] - miny) / scale) for p in points]


def hausdorff_distance(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    def directed(p, q):
        return max(min(math.hypot(px - qx, py - qy) for qx, qy in q) for px, py in p)
    if not a or not b:
        return float("inf")
    return max(directed(a, b), directed(b, a))


def average_min_distance(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    if not a or not b:
        return float("inf")
    return sum(min(math.hypot(px - qx, py - qy) for qx, qy in b) for px, py in a) / len(a)


def turning_angles(points: list[tuple[float, float]]) -> list[float]:
    angles = []
    for i in range(1, len(points) - 1):
        v1 = (points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
        v2 = (points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        a1 = math.degrees(math.atan2(v1[1], v1[0]))
        a2 = math.degrees(math.atan2(v2[1], v2[0]))
        diff = (a2 - a1 + 180.0) % 360.0 - 180.0
        angles.append(diff)
    return angles


def shape_similarity(
    target_xy: list[tuple[float, float]],
    route_xy: list[tuple[float, float]],
    target_distance_m: float,
) -> float:
    """Combined shape similarity score in [0,1] per section 53.5."""
    if len(target_xy) < 2 or len(route_xy) < 2:
        return 0.0
    tn = resample_polyline(_normalize_for_shape(target_xy), 128)
    rn = resample_polyline(_normalize_for_shape(route_xy), 128)

    allowed_err = max(50.0, target_distance_m * 0.015)
    haus = hausdorff_distance(target_xy, route_xy)
    haus_score = 1.0 - min(1.0, haus / allowed_err)

    avg = average_min_distance(tn, rn)
    avg_score = 1.0 - min(1.0, avg / 0.25)

    t_angles = turning_angles(tn)
    r_angles = turning_angles(rn)
    if t_angles and r_angles:
        m = min(len(t_angles), len(r_angles))
        turn_diff = sum(abs(t_angles[i] - r_angles[i]) for i in range(m)) / m
        turn_score = 1.0 - min(1.0, turn_diff / 180.0)
    else:
        turn_score = 1.0

    t_aspect = aspect_ratio([Polyline(points=_normalize_for_shape(target_xy))])
    r_aspect = aspect_ratio([Polyline(points=_normalize_for_shape(route_xy))])
    if t_aspect > 0:
        aspect_score = 1.0 - min(1.0, abs(t_aspect - r_aspect) / t_aspect)
    else:
        aspect_score = 1.0

    return float(
        0.45 * max(0.0, haus_score)
        + 0.25 * max(0.0, avg_score)
        + 0.20 * max(0.0, turn_score)
        + 0.10 * max(0.0, aspect_score)
    )


# --------------------------------------------------------------------------- #
# Multi-level SVG parsing with weighted important points
# --------------------------------------------------------------------------- #


def _perp_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Perpendicular distance from point *p* to segment *a*-*b*."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if dx == 0 and dy == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    px = a[0] + t * dx
    py = a[1] + t * dy
    return math.hypot(p[0] - px, p[1] - py)


def ramer_douglas_peucker(
    points: list[tuple[float, float]], epsilon: float
) -> list[tuple[float, float]]:
    """Iterative Ramer-Douglas-Peucker simplification."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = True
    keep[-1] = True
    stack: list[tuple[int, int]] = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        dmax = 0.0
        idx = -1
        for i in range(start + 1, end):
            d = _perp_distance(points[i], points[start], points[end])
            if d > dmax:
                dmax = d
                idx = i
        if dmax > epsilon and idx != -1:
            keep[idx] = True
            stack.append((start, idx))
            stack.append((idx, end))
    return [points[i] for i in range(len(points)) if keep[i]]


def simplify_polylines(
    polylines: list[Polyline], epsilon: float
) -> list[Polyline]:
    """Apply RDP simplification to each polyline independently."""
    out: list[Polyline] = []
    for pl in polylines:
        simplified = ramer_douglas_peucker(pl.points, epsilon)
        if len(simplified) < 2 and len(pl.points) >= 2:
            simplified = [pl.points[0], pl.points[-1]]
        out.append(Polyline(points=simplified, closed=pl.closed))
    return out


def _turn_angle_at(
    points: list[tuple[float, float]], i: int
) -> float:
    """Absolute turn angle (degrees) at point *i* (1 <= i <= len-2)."""
    v1 = (points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
    v2 = (points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
    a1 = math.degrees(math.atan2(v1[1], v1[0]))
    a2 = math.degrees(math.atan2(v2[1], v2[0]))
    return abs((a2 - a1 + 180.0) % 360.0 - 180.0)


def detect_important_points(
    polylines: list[Polyline],
) -> list[tuple[float, float]]:
    """Detect endpoints, sharp corners, branch points, and high-curvature points."""
    important: list[tuple[float, float]] = []

    # Endpoints of open polylines
    for pl in polylines:
        if not pl.closed:
            important.append(pl.points[0])
            important.append(pl.points[-1])
        else:
            # Closed-shape extrema
            important.append(pl.points[0])

    # Sharp corners (turn angle > 45 degrees) and high-curvature points
    for pl in polylines:
        for i in range(1, len(pl.points) - 1):
            turn = _turn_angle_at(pl.points, i)
            if turn > 45.0:
                important.append(pl.points[i])

    # Branch points (points shared by multiple polylines within tolerance)
    all_pts: list[tuple[tuple[float, float], int]] = []
    for pi, pl in enumerate(polylines):
        for pt in pl.points:
            all_pts.append((pt, pi))
    for i in range(len(all_pts)):
        pt_i, pi_i = all_pts[i]
        for j in range(i + 1, len(all_pts)):
            pt_j, pi_j = all_pts[j]
            if pi_i != pi_j and math.hypot(pt_i[0] - pt_j[0], pt_i[1] - pt_j[1]) < 0.02:
                important.append(pt_i)
                break

    # Deduplicate within tolerance
    deduped: list[tuple[float, float]] = []
    for pt in important:
        if not any(math.hypot(pt[0] - dp[0], pt[1] - dp[1]) < 0.01 for dp in deduped):
            deduped.append(pt)
    return deduped


def assign_weights(
    points: list[tuple[float, float]],
    important_points: list[tuple[float, float]],
) -> list[float]:
    """Assign importance weights: high for corners/endpoints/branches, medium for
    silhouette strokes, low for decorative details."""
    weights: list[float] = []
    for pt in points:
        is_important = any(
            math.hypot(pt[0] - ip[0], pt[1] - ip[1]) < 0.02 for ip in important_points
        )
        if is_important:
            weights.append(1.0)
        else:
            weights.append(0.3)
    return weights


def build_detail_levels(
    polylines: list[Polyline],
) -> dict[str, list[Polyline]]:
    """Build coarse / medium / fine Polyline sets via RDP simplification.

    coarse:  silhouette and main strokes only (~50-250 points)
    medium:  important corners and curves (~100-800 points)
    fine:    full sampled SVG geometry (original)
    """
    fine = [Polyline(points=list(pl.points), closed=pl.closed) for pl in polylines]

    total_fine = sum(len(pl.points) for pl in fine)

    # Medium: moderate simplification
    medium_eps = 0.015
    medium = simplify_polylines(fine, medium_eps)
    medium_count = sum(len(pl.points) for pl in medium)
    while medium_count > 300 and medium_eps < 0.3:
        medium_eps *= 1.5
        medium = simplify_polylines(fine, medium_eps)
        medium_count = sum(len(pl.points) for pl in medium)

    # Coarse: aggressive simplification
    coarse_eps = 0.05
    coarse = simplify_polylines(fine, coarse_eps)
    coarse_count = sum(len(pl.points) for pl in coarse)
    while coarse_count > 150 and coarse_eps < 0.5:
        coarse_eps *= 1.5
        coarse = simplify_polylines(fine, coarse_eps)
        coarse_count = sum(len(pl.points) for pl in coarse)

    return {"coarse": coarse, "medium": medium, "fine": fine}


def bearing_histogram(
    polylines: list[Polyline], n_bins: int = 36
) -> list[int]:
    """Histogram of stroke bearings (n_bins bins of 360/n_bins degrees each)."""
    hist = [0] * n_bins
    for pl in polylines:
        for i in range(len(pl.points) - 1):
            dx = pl.points[i + 1][0] - pl.points[i][0]
            dy = pl.points[i + 1][1] - pl.points[i][1]
            if dx == 0 and dy == 0:
                continue
            angle = math.degrees(math.atan2(dy, dx)) % 360.0
            bin_idx = int(angle / (360.0 / n_bins)) % n_bins
            hist[bin_idx] += 1
    return hist


@dataclass
class ShapeGraph:
    """Multi-level shape graph with weighted important points."""

    polylines: list[Polyline]
    important_points: list[tuple[float, float]]
    weights: list[float]
    detail_level: str  # "coarse", "medium", "fine"
    normalized_length: float
    aspect_ratio: float
    bearing_histogram: list[int]
    stroke_order: list[int]
    levels: list["ShapeGraph"] = field(default_factory=list)
    shape_id: str = ""
    shape_name: str = ""
    closed_path: bool = False


def _build_shape_graph_from_normalized(
    normalized: list[Polyline],
    shape_id: str = "",
    shape_name: str = "",
    closed_path: bool = False,
) -> ShapeGraph:
    """Build a multi-level ShapeGraph from already-normalized polylines."""
    levels_dict = build_detail_levels(normalized)

    level_sgs: list[ShapeGraph] = []
    for level_name in ("coarse", "medium", "fine"):
        level_pls = levels_dict[level_name]
        important = detect_important_points(level_pls)
        all_points = flatten(level_pls)
        wts = assign_weights(all_points, important)
        sg = ShapeGraph(
            polylines=level_pls,
            important_points=important,
            weights=wts,
            detail_level=level_name,
            normalized_length=normalized_length(level_pls),
            aspect_ratio=aspect_ratio(level_pls),
            bearing_histogram=bearing_histogram(level_pls),
            stroke_order=list(range(len(level_pls))),
            shape_id=shape_id,
            shape_name=shape_name,
            closed_path=closed_path,
        )
        level_sgs.append(sg)

    fine_sg = level_sgs[-1]
    fine_sg.levels = level_sgs
    return fine_sg


def build_shape_graph_from_normalized(
    normalized: list[Polyline],
    shape_id: str = "",
    shape_name: str = "",
    closed_path: bool = False,
) -> ShapeGraph:
    """Build a multi-level ShapeGraph from already-normalized polylines."""
    return _build_shape_graph_from_normalized(normalized, shape_id, shape_name, closed_path)


def parse_svg_multilevel(
    svg_text: str,
    shape_id: str = "",
    shape_name: str = "",
    closed_path: bool = False,
) -> ShapeGraph:
    """Parse SVG text into a multi-level ShapeGraph with weighted important points."""
    polylines = parse_svg(svg_text)
    normalized = normalize_polylines(polylines)
    return _build_shape_graph_from_normalized(normalized, shape_id, shape_name, closed_path)
