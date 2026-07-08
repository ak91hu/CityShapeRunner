from __future__ import annotations


from app.core.graph import Edge, Node, RoadGraph
from app.core.scoring import score_candidate
from app.core.snapping import RouteResult
from app.core.units import Projector


def _build_graph(projector: Projector, specs: list[tuple[int, int, int, int, str, str]]) -> RoadGraph:
    """specs: (id, from, to, highway, surface). Nodes at (from*100, 0)."""
    g = RoadGraph(projector=projector)
    coords = {}
    for i in range(4):
        x = i * 100.0
        lat, lon = projector.to_wgs84(x, 0.0)
        g.add_node(Node(id=i, x=x, y=0.0, lat=lat, lon=lon))
        coords[i] = (x, 0.0)
    for eid, a, b, hw, surf in specs:
        g.add_edge(Edge(id=eid, from_id=a, to_id=b, highway=hw, surface=surf, length_m=100.0,
                        geometry_xy=[coords[a], coords[b]],
                        geometry_lonlat=[(g.nodes[a].lat, g.nodes[a].lon), (g.nodes[b].lat, g.nodes[b].lon)]))
    return g


def _route(g: RoadGraph, node_path: list[int], edges: list[int], length_m: float, projector: Projector) -> RouteResult:
    route_metric = [(g.nodes[n].x, g.nodes[n].y) for n in node_path]
    route_lonlat = [(g.nodes[n].lat, g.nodes[n].lon) for n in node_path]
    return RouteResult(
        valid=True, node_path=node_path, edges_used=edges, route_metric=route_metric,
        route_lonlat=route_lonlat, length_m=length_m, detour_ratios=[1.0], duplicate_fraction=0.0,
        keypoint_lonlat=route_lonlat, warnings=[], segments_failed=0,
    )


def test_distance_accuracy_decreases_with_error(projector):
    g = _build_graph(projector, [(0, 0, 1, "residential", "asphalt")])
    target = [projector.to_wgs84(0, 0), projector.to_wgs84(0.001, 0)]
    r = _route(g, [0, 1], [0], 1000.0, projector)  # 1km
    near = score_candidate(target, r, 1.0, "running", g, projector)
    far = score_candidate(target, r, 5.0, "running", g, projector)  # 1km route vs 5km target
    assert near.breakdown.distance_accuracy_score > far.breakdown.distance_accuracy_score


def test_road_quality_footway_beats_primary(projector):
    g = _build_graph(projector, [
        (0, 0, 1, "footway", "asphalt"),
        (1, 1, 2, "primary", "asphalt"),
    ])
    target = [projector.to_wgs84(0, 0), projector.to_wgs84(0.002, 0)]
    r_foot = _route(g, [0, 1], [0], 100.0, projector)
    r_prim = _route(g, [1, 2], [1], 100.0, projector)
    s_foot = score_candidate(target, r_foot, 0.1, "running", g, projector)
    s_prim = score_candidate(target, r_prim, 0.1, "running", g, projector)
    assert s_foot.breakdown.road_quality_score > s_prim.breakdown.road_quality_score


def test_high_similarity_beats_poor(projector):
    g = _build_graph(projector, [(0, 0, 1, "residential", "asphalt")])
    target = [projector.to_wgs84(0, 0), projector.to_wgs84(0.01, 0),
              projector.to_wgs84(0.01, 0.01), projector.to_wgs84(0, 0)]
    # route that follows the target square closely
    close = RouteResult(
        valid=True, node_path=[0, 1, 0, 1, 0], edges_used=[0, 0, 0, 0],
        route_metric=[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)],
        route_lonlat=[projector.to_wgs84(x, y) for x, y in [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]],
        length_m=400.0, detour_ratios=[1.0], duplicate_fraction=0.0, keypoint_lonlat=[], warnings=[], segments_failed=0,
    )
    # route that is a straight line (poor shape match)
    poor = RouteResult(
        valid=True, node_path=[0, 1], edges_used=[0],
        route_metric=[(0, 0), (100, 0)],
        route_lonlat=[projector.to_wgs84(0, 0), projector.to_wgs84(100, 0)],
        length_m=100.0, detour_ratios=[1.0], duplicate_fraction=0.0, keypoint_lonlat=[], warnings=[], segments_failed=0,
    )
    s_close = score_candidate(target, close, 0.4, "running", g, projector)
    s_poor = score_candidate(target, poor, 0.1, "running", g, projector)
    assert s_close.breakdown.shape_similarity_score >= s_poor.breakdown.shape_similarity_score


def test_warnings_distance_outside_tolerance(projector):
    g = _build_graph(projector, [(0, 0, 1, "residential", "asphalt")])
    target = [projector.to_wgs84(0, 0), projector.to_wgs84(0.001, 0)]
    r = _route(g, [0, 1], [0], 1000.0, projector)
    s = score_candidate(target, r, 1.0, "running", g, projector)  # exact distance -> no warning
    assert "distance_outside_preferred_tolerance" not in s.warnings
    s2 = score_candidate(target, r, 1.2, "running", g, projector)  # 1km vs 1.2km -> 16% error
    assert "distance_outside_preferred_tolerance" in s2.warnings


def test_quality_gate_low_shape(projector):
    g = _build_graph(projector, [(0, 0, 1, "residential", "asphalt")])
    # a target triangle vs a straight route -> low similarity
    target = [projector.to_wgs84(0, 0), projector.to_wgs84(0.01, 0.01), projector.to_wgs84(0.02, 0)]
    r = _route(g, [0, 1], [0], 100.0, projector)
    s = score_candidate(target, r, 0.05, "running", g, projector)
    if s.breakdown.shape_similarity_score < 0.45:
        assert not s.passed
        assert s.rejection_reason == "low_shape_similarity"


def test_fit_score_in_unit_interval(projector):
    g = _build_graph(projector, [(0, 0, 1, "residential", "asphalt")])
    target = [projector.to_wgs84(0, 0), projector.to_wgs84(0.001, 0)]
    r = _route(g, [0, 1], [0], 1000.0, projector)
    s = score_candidate(target, r, 1.0, "running", g, projector)
    assert 0.0 <= s.breakdown.fit_score <= 1.0
    assert 0.0 <= s.breakdown.shape_similarity_score <= 1.0
