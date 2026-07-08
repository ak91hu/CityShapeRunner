from __future__ import annotations


from app.core.snapping import repair_and_route, snap_polyline


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
    # keypoints are distinct consecutive control nodes
    assert 2 <= len(route.keypoint_lonlat) <= len(snap.snapped_node_ids)
