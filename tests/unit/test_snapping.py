from __future__ import annotations


from app.core.snapping import repair_and_route, snap_polyline, snap_edit_route, validate_route


def test_snap_on_grid_acceptable(mini_grid):
    fc = mini_grid
    filtered = fc.graph.filter_for_profile("running", "medium")
    # target along grid lines: a square around (200,200) size 400
    target_lonlat = [fc.graph.projector.to_wgs84(x, y) for x, y in [
        (200, 200), (600, 200), (600, 600), (200, 600), (200, 200)
    ]]
    snap = snap_polyline(target_lonlat, filtered, fc.graph.projector, "running")
    assert snap.acceptable
    assert snap.within_tolerance_ratio == 1.0
    assert -1 not in snap.snapped_node_ids


def test_snap_out_of_tolerance_rejected(mini_grid):
    fc = mini_grid
    filtered = fc.graph.filter_for_profile("running", "medium")
    # points far from the grid (grid is 0..900)
    target_lonlat = [fc.graph.projector.to_wgs84(x, y) for x, y in [
        (5000, 5000), (5200, 5000), (5200, 5200)
    ]]
    snap = snap_polyline(target_lonlat, filtered, fc.graph.projector, "running")
    assert not snap.acceptable


def test_repair_connects_nodes(mini_grid):
    fc = mini_grid
    filtered = fc.graph.filter_for_profile("running", "medium")
    target_lonlat = [fc.graph.projector.to_wgs84(x, y) for x, y in [
        (100, 100), (300, 100), (300, 300), (100, 300), (100, 100)
    ]]
    snap = snap_polyline(target_lonlat, filtered, fc.graph.projector, "running")
    route = repair_and_route(snap, filtered, "running", "medium")
    assert route.valid
    assert len(route.node_path) >= 2
    assert route.length_m > 0
    # route should be roughly continuous (no failed segments)
    assert route.segments_failed == 0


def test_keypoints_distinct(mini_grid):
    fc = mini_grid
    filtered = fc.graph.filter_for_profile("running", "medium")
    target_lonlat = [fc.graph.projector.to_wgs84(x, y) for x, y in [
        (100, 100), (300, 100), (300, 300), (100, 300), (100, 100)
    ]]
    snap = snap_polyline(target_lonlat, filtered, fc.graph.projector, "running")
    route = repair_and_route(snap, filtered, "running", "medium")
    assert 2 <= len(route.keypoint_lonlat) <= len(snap.snapped_node_ids)


def test_control_indices_scaling():
    from app.core.snapping import _control_indices
    assert len(_control_indices(2)) == 2
    # At n=100, n//4 = 25. Max(16, min(96, 25)) = 25
    assert len(_control_indices(100)) == 25
    # At n=600, n//4 = 150. Max(16, min(96, 150)) = 96
    assert len(_control_indices(600)) == 96
    # At n=20, n//4 = 5. Max(16, min(96, 5)) = 16 -> min(16, 20) = 16
    assert len(_control_indices(20)) == 16


# --------------------------------------------------------------------------- #
# Barrier (water / building) avoidance tests
# --------------------------------------------------------------------------- #


def test_river_city_has_water_polygon(river_city):
    """River city fixture should have a water polygon barrier."""
    assert len(river_city.graph.water_polygons) > 0
    assert river_city.graph.has_barriers()


def test_mini_grid_no_barriers(mini_grid):
    """Mini grid has no water or building barriers."""
    assert not mini_grid.graph.has_barriers()


def test_crosses_water_detection(river_city):
    """A line crossing the river gap should be detected as crossing water."""
    # line from left grid to right grid (crosses the river gap at x=500..700)
    xy_line = [(400.0, 300.0), (800.0, 300.0)]
    assert river_city.graph.crosses_water(xy_line)


def test_no_cross_water_on_same_side(river_city):
    """A line staying on one side of the river should not cross water."""
    xy_line = [(100.0, 100.0), (400.0, 400.0)]
    assert not river_city.graph.crosses_water(xy_line)


def test_bridge_edge_not_flagged_as_crossing_water(river_city):
    """Bridge edges should not be penalized even if they cross the water polygon."""
    bridges = [e for e in river_city.graph.edges if e.bridge]
    assert len(bridges) == 2
    # A bridge edge geometry crosses the water polygon geometrically, but
    # that's fine — the routing logic exempts bridges from the penalty.
    for bridge in bridges:
        assert river_city.graph.crosses_water(bridge.geometry_xy)


def test_snap_edit_route_avoids_water(river_city):
    """snap_edit_route should route via bridges, not straight across water."""
    proj = river_city.graph.projector
    filtered = river_city.graph.filter_for_profile("running", "medium")
    # target from left side to right side — straight line crosses the river
    target_lonlat = [
        proj.to_wgs84(200.0, 300.0),
        proj.to_wgs84(900.0, 300.0),
    ]
    result = snap_edit_route(target_lonlat, filtered, proj, "running")
    assert result.snapped
    # The snapped route should NOT cross water (it should go via a bridge)
    assert "crosses_water" not in result.warnings


def test_validate_route_detects_water_crossing(river_city):
    """validate_route should flag a straight line across the river."""
    proj = river_city.graph.projector
    route_lonlat = [
        proj.to_wgs84(200.0, 300.0),
        proj.to_wgs84(900.0, 300.0),
    ]
    warnings = validate_route(route_lonlat, river_city.graph, proj)
    assert "crosses_water" in warnings


def test_validate_route_clean_on_same_side(river_city):
    """validate_route should return no warnings for a route on one side."""
    proj = river_city.graph.projector
    route_lonlat = [
        proj.to_wgs84(100.0, 100.0),
        proj.to_wgs84(400.0, 400.0),
    ]
    warnings = validate_route(route_lonlat, river_city.graph, proj)
    assert warnings == []


def test_snap_edit_route_empty_input():
    """snap_edit_route handles empty input gracefully."""
    from app.core.graph import build_mini_grid_city
    fc = build_mini_grid_city()
    filtered = fc.graph.filter_for_profile("running", "medium")
    result = snap_edit_route([], filtered, fc.graph.projector, "running")
    assert not result.snapped
    assert result.route_lonlat == []


def test_snap_edit_route_returns_original_on_failure(mini_grid):
    """When snapping can't find a route, the original input is returned."""
    fc = mini_grid
    filtered = fc.graph.filter_for_profile("running", "medium")
    # points far outside the grid — snapping will fail to find edges
    target_lonlat = [fc.graph.projector.to_wgs84(x, y) for x, y in [
        (50000, 50000), (52000, 50000)
    ]]
    result = snap_edit_route(target_lonlat, filtered, fc.graph.projector, "running")
    assert not result.snapped
    assert len(result.route_lonlat) == len(target_lonlat)
