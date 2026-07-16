from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from app.core.graph import Edge, RoadGraph
from app.core.units import GeoPoint, MetricPoint, angle_difference_deg, heading_deg

# Tolerances (meters) per section 22.1
SNAP_TOLERANCE_M = {"running": 150.0, "walking": 120.0, "cycling": 250.0}
MAX_DETOUR_RATIO = {"running": 4.0, "walking": 4.0, "cycling": 3.0}

WATER_CROSSING_PENALTY = 100_000.0
BUILDING_CROSSING_PENALTY = 50_000.0


@dataclass
class SnapResult:
    acceptable: bool
    target_lonlat: list[GeoPoint]
    target_metric: list[MetricPoint]
    control_target_lonlat: list[GeoPoint]
    control_target_metric: list[MetricPoint]
    snapped_node_ids: list[int]
    snapped_lonlat: list[GeoPoint]
    snapped_metric: list[MetricPoint]
    per_point_distance: list[float]
    within_tolerance_ratio: float
    warnings: list[str] = field(default_factory=list)


def _control_indices(n: int) -> list[int]:
    if n <= 2:
        return list(range(n))
    n_controls = max(32, min(256, n // 2))
    n_controls = min(n_controls, n)
    return [round(i * (n - 1) / (n_controls - 1)) for i in range(n_controls)]


def _avg_edge_length_m(graph: RoadGraph) -> float:
    lengths = [e.length_m for e in graph.edges if not e.rejected and e.length_m > 0]
    return sum(lengths) / len(lengths) if lengths else 150.0


def snap_polyline(
    target_lonlat: list[GeoPoint],
    graph: RoadGraph,
    projector,
    activity: str,
    city_density_factor: float = 1.0,
    control_indices: list[int] | None = None,
) -> SnapResult:
    """Snap control points of the target to the nearest traversable graph nodes (section 22)."""
    # Coarser graphs need a looser tolerance or almost no control points will snap.
    avg_edge = _avg_edge_length_m(graph)
    adaptive_factor = max(1.0, min(3.5, avg_edge / 120.0))
    tol = SNAP_TOLERANCE_M[activity] * city_density_factor * adaptive_factor
    full_metric = [projector.to_metric(lon, lat) for lat, lon in target_lonlat]
    ctrl_idx = control_indices if control_indices is not None else _control_indices(len(target_lonlat))
    control_target_lonlat = [target_lonlat[i] for i in ctrl_idx]
    control_target_metric = [full_metric[i] for i in ctrl_idx]

    snapped_node_ids: list[int] = []
    snapped_lonlat: list[GeoPoint] = []
    snapped_metric: list[MetricPoint] = []
    distances: list[float] = []

    for tx, ty in control_target_metric:
        edge, proj, dist = graph.nearest_edge((tx, ty), tol)
        if edge is None:
            best = None
            best_d = tol
            for n in graph.nodes.values():
                d = math.hypot(n.x - tx, n.y - ty)
                if d < best_d:
                    best_d = d
                    best = n
            if best is None:
                snapped_node_ids.append(-1)
                snapped_lonlat.append(target_lonlat[0])
                snapped_metric.append((tx, ty))
                distances.append(tol + 1.0)
                continue
            snapped_node_ids.append(best.id)
            snapped_lonlat.append((best.lat, best.lon))
            snapped_metric.append((best.x, best.y))
            distances.append(best_d)
            continue
        from_node = graph.nodes[edge.from_id]
        to_node = graph.nodes[edge.to_id]
        d_from = math.hypot(from_node.x - tx, from_node.y - ty)
        d_to = math.hypot(to_node.x - tx, to_node.y - ty)
        node = from_node if d_from <= d_to else to_node
        snapped_node_ids.append(node.id)
        snapped_lonlat.append((node.lat, node.lon))
        snapped_metric.append((node.x, node.y))
        # Use the edge perpendicular distance (from nearest_edge) for the tolerance check.
        distances.append(dist)

    within = sum(1 for d in distances if d <= tol) / max(1, len(distances))
    warnings: list[str] = []
    if within < 0.8:
        warnings.append("low_shape_similarity")
    acceptable = within >= 0.8 and -1 not in snapped_node_ids
    return SnapResult(
        acceptable=acceptable,
        target_lonlat=target_lonlat,
        target_metric=full_metric,
        control_target_lonlat=control_target_lonlat,
        control_target_metric=control_target_metric,
        snapped_node_ids=snapped_node_ids,
        snapped_lonlat=snapped_lonlat,
        snapped_metric=snapped_metric,
        per_point_distance=distances,
        within_tolerance_ratio=within,
        warnings=warnings,
    )


@dataclass
class RouteResult:
    valid: bool
    node_path: list[int]
    edges_used: list[int]
    route_metric: list[MetricPoint]
    route_lonlat: list[GeoPoint]
    length_m: float
    detour_ratios: list[float]
    duplicate_fraction: float
    keypoint_lonlat: list[GeoPoint]
    warnings: list[str] = field(default_factory=list)
    segments_failed: int = 0


def _segment_distance(p: MetricPoint, a: MetricPoint, b: MetricPoint) -> float:
    """Perpendicular distance from point p to segment a-b (metric)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    px, py = ax + t * dx, ay + t * dy
    return math.hypot(p[0] - px, p[1] - py)


def _dijkstra(
    graph: RoadGraph,
    start: int,
    goal: int,
    target_seg_a: MetricPoint,
    target_seg_b: MetricPoint,
    used_edges: set[int],
    max_detour: float,
) -> tuple[list[int], list[int], float] | None:
    """Dijkstra with geometry-aware repair weights (section 52.4)."""
    if start == goal:
        return [start], [], 0.0
    target_heading = heading_deg(target_seg_a, target_seg_b)
    straight = math.hypot(target_seg_b[0] - target_seg_a[0], target_seg_b[1] - target_seg_a[1]) or 1.0
    max_cost = max(straight * max_detour + 3000.0, 5000.0)  # generous guard

    def edge_weight(edge: Edge, u: int, v: int) -> float:
        w = edge.profile_weight
        if w == float("inf"):
            return float("inf")
        # distance-from-target-segment penalty
        mid = ((graph.nodes[u].x + graph.nodes[v].x) / 2, (graph.nodes[u].y + graph.nodes[v].y) / 2)
        d = _segment_distance(mid, target_seg_a, target_seg_b)
        w += max(0.0, d - 50.0) * 1.5
        # heading penalty (normalized * length)
        eh = heading_deg((graph.nodes[u].x, graph.nodes[u].y), (graph.nodes[v].x, graph.nodes[v].y))
        w += (angle_difference_deg(eh, target_heading) / 180.0) * edge.length_m * 0.5
        # duplicate penalty
        if edge.id in used_edges:
            w += 200.0
        # barrier penalties: avoid edges crossing water (unless bridge) or buildings
        if not edge.bridge and graph.crosses_water(edge.geometry_xy):
            w += WATER_CROSSING_PENALTY
        if graph.crosses_building(edge.geometry_xy):
            w += BUILDING_CROSSING_PENALTY
        return w

    dist = {start: 0.0}
    prev: dict[int, int] = {}
    prev_edge: dict[int, int] = {}
    pq = [(0.0, start)]
    visited: set[int] = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == goal:
            break
        for v, edge in graph.adj.get(u, []):
            if edge.rejected:
                continue
            w = edge_weight(edge, u, v)
            if w == float("inf"):
                continue
            nd = d + w
            if nd > max_cost:
                continue
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                prev_edge[v] = edge.id
                heapq.heappush(pq, (nd, v))
    if goal not in dist:
        return None
    # reconstruct
    path = [goal]
    edges: list[int] = []
    cur = goal
    while cur != start:
        p = prev.get(cur)
        if p is None:
            return None
        edges.append(prev_edge[cur])
        path.append(p)
        cur = p
    path.reverse()
    edges.reverse()
    return path, edges, dist[goal]


def repair_and_route(
    snap: SnapResult,
    graph: RoadGraph,
    activity: str,
    difficulty: str,
) -> RouteResult:
    """Route between consecutive snapped nodes with repair + continuity (section 22.2/52)."""
    max_detour = MAX_DETOUR_RATIO[activity]
    if difficulty == "easy":
        max_detour *= 0.8

    used_edges: set[int] = set()
    node_path: list[int] = []
    edges_used: list[int] = []
    route_metric: list[MetricPoint] = []
    detour_ratios: list[float] = []
    segments_failed = 0
    edge_use_count: dict[int, int] = {}

    nids_raw = snap.snapped_node_ids
    ctrl_metric_raw = snap.control_target_metric
    
    nids = []
    ctrl_metric = []
    for nid, ctrl in zip(nids_raw, ctrl_metric_raw):
        if nid != -1:
            nids.append(nid)
            ctrl_metric.append(ctrl)

    for i in range(len(nids) - 1):
        a, b = nids[i], nids[i + 1]
        ta = ctrl_metric[i]
        tb = ctrl_metric[i + 1]
        if a == b:
            continue
        res = _dijkstra(graph, a, b, ta, tb, used_edges, max_detour)
        if res is None:
            segments_failed += 1
            continue
        seg_path, seg_edges, _ = res
        if not node_path:
            node_path.extend(seg_path)
            route_metric.append((graph.nodes[seg_path[0]].x, graph.nodes[seg_path[0]].y))
        else:
            node_path.extend(seg_path[1:])
        for eid in seg_edges:
            edges_used.append(eid)
            used_edges.add(eid)
            edge_use_count[eid] = edge_use_count.get(eid, 0) + 1
        for nid in seg_path[1:]:
            route_metric.append((graph.nodes[nid].x, graph.nodes[nid].y))
        straight = math.hypot(tb[0] - ta[0], tb[1] - ta[1]) or 1.0
        seg_len = sum(graph.edges[eid].length_m for eid in seg_edges)
        detour_ratios.append(seg_len / straight)

    # build lonlat
    route_lonlat = [(graph.nodes[nid].lat, graph.nodes[nid].lon) for nid in node_path]
    length_m = 0.0
    for i in range(len(node_path) - 1):
        a = graph.nodes[node_path[i]]
        b = graph.nodes[node_path[i + 1]]
        length_m += math.hypot(b.x - a.x, b.y - a.y)
    # duplicate fraction
    total_edge_uses = sum(edge_use_count.values())
    duplicate_fraction = (total_edge_uses - len(edge_use_count)) / max(1, total_edge_uses)

    # keypoints = distinct consecutive snapped control nodes
    keypoint_lonlat: list[GeoPoint] = []
    last = -1
    for nid in nids:
        if nid != -1 and nid != last:
            keypoint_lonlat.append((graph.nodes[nid].lat, graph.nodes[nid].lon))
            last = nid

    warnings: list[str] = []
    if segments_failed > 0:
        warnings.append("route_disconnected")
    if duplicate_fraction > 0.10:
        warnings.append("high_detour_ratio")
    if detour_ratios and max(detour_ratios) > max_detour:
        warnings.append("high_detour_ratio")

    valid = len(node_path) >= 2 and segments_failed <= 3
    return RouteResult(
        valid=valid,
        node_path=node_path,
        edges_used=edges_used,
        route_metric=route_metric,
        route_lonlat=route_lonlat,
        length_m=length_m,
        detour_ratios=detour_ratios,
        duplicate_fraction=duplicate_fraction,
        keypoint_lonlat=keypoint_lonlat,
        warnings=warnings,
        segments_failed=segments_failed,
    )


def validate_route(
    route_lonlat: list[GeoPoint],
    graph: RoadGraph,
    projector,
) -> list[str]:
    """Check a route's geometry against barrier polygons (water, buildings).

    Returns a list of warning strings: 'crosses_water', 'crosses_building'.
    Each segment between consecutive points is checked.
    """
    warnings: list[str] = []
    if not route_lonlat or len(route_lonlat) < 2:
        return warnings
    if not graph.has_barriers():
        return warnings
    crosses_water = False
    crosses_building = False
    for i in range(len(route_lonlat) - 1):
        lat1, lon1 = route_lonlat[i]
        lat2, lon2 = route_lonlat[i + 1]
        x1, y1 = projector.to_metric(lon1, lat1)
        x2, y2 = projector.to_metric(lon2, lat2)
        seg_xy = [(x1, y1), (x2, y2)]
        if graph.crosses_water(seg_xy):
            crosses_water = True
        if graph.crosses_building(seg_xy):
            crosses_building = True
    if crosses_water:
        warnings.append("crosses_water")
    if crosses_building:
        warnings.append("crosses_building")
    return warnings


@dataclass
class SnapEditResult:
    snapped: bool
    route_lonlat: list[GeoPoint]
    original_lonlat: list[GeoPoint]
    warnings: list[str] = field(default_factory=list)
    segments_failed: int = 0


def snap_edit_route(
    target_lonlat: list[GeoPoint],
    graph: RoadGraph,
    projector,
    activity: str,
    difficulty: str = "normal",
) -> SnapEditResult:
    """High-level: snap an edited polyline to real roads, avoiding water and buildings.

    Returns the snapped route coordinates plus warnings about barrier crossings
    and connectivity issues. Falls back to the original input if snapping fails.
    """
    if not target_lonlat:
        return SnapEditResult(snapped=False, route_lonlat=[], original_lonlat=[])
    if len(target_lonlat) < 2:
        return SnapEditResult(
            snapped=False, route_lonlat=list(target_lonlat), original_lonlat=list(target_lonlat)
        )

    diff = "medium" if difficulty == "normal" else difficulty
    snap = snap_polyline(target_lonlat, graph, projector, activity)
    route = repair_and_route(snap, graph, activity, diff)

    warnings = list(route.warnings)
    if route.route_lonlat and len(route.route_lonlat) >= 2:
        # Check edges used (not raw coordinates) so bridge crossings are not flagged
        edge_map = {e.id: e for e in graph.edges}
        has_water = False
        has_building = False
        for eid in route.edges_used:
            edge = edge_map.get(eid)
            if edge is None:
                continue
            if not edge.bridge and graph.crosses_water(edge.geometry_xy):
                has_water = True
            if graph.crosses_building(edge.geometry_xy):
                has_building = True
        if has_water:
            warnings.append("crosses_water")
        if has_building:
            warnings.append("crosses_building")
        return SnapEditResult(
            snapped=True,
            route_lonlat=route.route_lonlat,
            original_lonlat=list(target_lonlat),
            warnings=warnings,
            segments_failed=route.segments_failed,
        )
    # Fallback: return original but still check for barrier crossings on coordinates
    warnings.extend(validate_route(target_lonlat, graph, projector))
    return SnapEditResult(
        snapped=False,
        route_lonlat=list(target_lonlat),
        original_lonlat=list(target_lonlat),
        warnings=warnings,
    )
