from __future__ import annotations

from app.core.graph import build_river_city


def test_snap_edit_endpoint_basic(client):
    """The snap-edit endpoint should return a snapped route with warnings."""
    fc = build_river_city()
    proj = fc.graph.projector

    # A simple route on the left grid (no water crossing)
    lonlat = [
        [proj.to_wgs84(100, 100)[1], proj.to_wgs84(100, 100)[0]],
        [proj.to_wgs84(300, 100)[1], proj.to_wgs84(300, 100)[0]],
        [proj.to_wgs84(300, 300)[1], proj.to_wgs84(300, 300)[0]],
    ]
    r = client.post("/api/routes/snap-edit", json={
        "city_id": "river-city",
        "activity": "running",
        "lonlat": lonlat,
    })
    assert r.status_code == 200
    body = r.json()
    assert "lonlat" in body
    assert "snapped" in body
    assert "warnings" in body
    assert "originalLonlat" in body
    assert isinstance(body["lonlat"], list)
    assert isinstance(body["warnings"], list)


def test_snap_edit_endpoint_empty(client):
    """Empty lonlat should return empty response."""
    r = client.post("/api/routes/snap-edit", json={
        "city_id": "river-city",
        "activity": "running",
        "lonlat": [],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["lonlat"] == []
    assert body["snapped"] is False


def test_snap_edit_endpoint_unknown_city(client):
    """Unknown city should return the original lonlat unsnapped."""
    r = client.post("/api/routes/snap-edit", json={
        "city_id": "nonexistent-city",
        "activity": "running",
        "lonlat": [[19.04, 47.5], [19.05, 47.5]],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["snapped"] is False
    assert body["lonlat"] == [[19.04, 47.5], [19.05, 47.5]]


def test_snap_edit_endpoint_avoids_water(client):
    """The snapped route should not cross water (goes via bridge instead)."""
    fc = build_river_city()
    proj = fc.graph.projector

    # Straight line from left to right — crosses the river
    p1 = proj.to_wgs84(200, 300)
    p2 = proj.to_wgs84(900, 300)
    lonlat = [[p1[1], p1[0]], [p2[1], p2[0]]]

    r = client.post("/api/routes/snap-edit", json={
        "city_id": "river-city",
        "activity": "running",
        "lonlat": lonlat,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["snapped"] is True
    assert "crosses_water" not in body["warnings"]
