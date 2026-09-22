"""Public/export route safety invariants."""

from gps_art_wizzard.tools.route_safety import is_provider_routed_geometry


def test_only_provider_routed_non_degenerate_geometry_is_publicly_safe():
    points = [(47.0, 19.0), (47.001, 19.001)]

    assert is_provider_routed_geometry(points, 150.0, routed=True)
    assert not is_provider_routed_geometry(points, 150.0, routed=False)
    assert not is_provider_routed_geometry(points, 0.0, routed=True)
    assert not is_provider_routed_geometry([], 150.0, routed=True)
    assert not is_provider_routed_geometry([points[0], points[0]], 150.0, routed=True)
    assert not is_provider_routed_geometry([(float("nan"), 19.0), points[1]], 150.0, routed=True)
