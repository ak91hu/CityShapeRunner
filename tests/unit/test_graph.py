from __future__ import annotations



from app.core.graph import Edge, Node, RoadGraph, build_mini_grid_city, build_river_city, build_restricted_city


def test_mini_grid_dimensions():
    fc = build_mini_grid_city()
    assert len(fc.graph.nodes) == 100  # 10x10
    # 10x10 grid: horizontal 10*9 + vertical 9*10 = 180
    assert len(fc.graph.edges) == 180
    assert fc.graph.projector is not None


def test_river_city_has_bridges():
    fc = build_river_city()
    bridges = [e for e in fc.graph.edges if e.bridge]
    assert fc.has_river
    assert len(bridges) == 2


def test_restricted_city_has_restricted_edges():
    fc = build_restricted_city()
    access_no = [e for e in fc.graph.edges if e.access == "no"]
    private = [e for e in fc.graph.edges if e.access == "private"]
    assert len(access_no) >= 1
    assert len(private) >= 1


def test_running_footway_cheaper_than_primary():
    g = RoadGraph()
    for i, hw in enumerate(["footway", "residential", "primary"]):
        g.add_node(Node(id=i, x=float(i) * 100, y=0, lat=47.5, lon=19.04))
    g.add_edge(Edge(id=0, from_id=0, to_id=1, highway="footway", length_m=100,
                    geometry_xy=[(0, 0), (100, 0)], geometry_lonlat=[(47.5, 19.04), (47.5, 19.05)]))
    g.add_edge(Edge(id=1, from_id=1, to_id=2, highway="residential", length_m=100,
                    geometry_xy=[(100, 0), (200, 0)], geometry_lonlat=[(47.5, 19.05), (47.5, 19.06)]))
    g.add_edge(Edge(id=2, from_id=0, to_id=2, highway="primary", length_m=200,
                    geometry_xy=[(0, 0), (200, 0)], geometry_lonlat=[(47.5, 19.04), (47.5, 19.06)]))
    from app.core.graph import apply_profile_weight
    for e in g.edges:
        apply_profile_weight(e, "running", "medium")
    foot = next(e for e in g.edges if e.highway == "footway")
    prim = next(e for e in g.edges if e.highway == "primary")
    assert foot.profile_weight < prim.profile_weight


def test_cycling_rejects_steps():
    e = Edge(id=1, from_id=0, to_id=1, highway="steps", length_m=50,
             geometry_xy=[(0, 0), (0, 50)], geometry_lonlat=[(47.5, 19.04), (47.5, 19.04)])
    from app.core.graph import apply_profile_weight
    apply_profile_weight(e, "cycling", "medium")
    assert e.rejected
    assert e.profile_weight == float("inf")


def test_access_no_rejected():
    from app.core.graph import apply_profile_weight
    for activity in ("running", "cycling", "walking"):
        e = Edge(id=1, from_id=0, to_id=1, highway="residential", access="no", length_m=100,
                 geometry_xy=[(0, 0), (100, 0)], geometry_lonlat=[(47.5, 19.04), (47.5, 19.05)])
        apply_profile_weight(e, activity, "medium")
        assert e.rejected


def test_private_penalty_added():
    from app.core.graph import apply_profile_weight
    e_priv = Edge(id=1, from_id=0, to_id=1, highway="residential", access="private", length_m=100,
                  geometry_xy=[(0, 0), (100, 0)], geometry_lonlat=[(47.5, 19.04), (47.5, 19.05)])
    e_norm = Edge(id=2, from_id=0, to_id=1, highway="residential", length_m=100,
                  geometry_xy=[(0, 0), (100, 0)], geometry_lonlat=[(47.5, 19.04), (47.5, 19.05)])
    apply_profile_weight(e_priv, "running", "medium")
    apply_profile_weight(e_norm, "running", "medium")
    assert e_priv.profile_weight > e_norm.profile_weight + 400  # +500 penalty


def test_foot_no_rejected_for_running():
    from app.core.graph import apply_profile_weight
    e = Edge(id=1, from_id=0, to_id=1, highway="residential", foot="no", length_m=100,
             geometry_xy=[(0, 0), (100, 0)], geometry_lonlat=[(47.5, 19.04), (47.5, 19.05)])
    apply_profile_weight(e, "running", "medium")
    assert e.rejected


def test_filter_for_profile_excludes_rejected():
    fc = build_restricted_city()
    filtered = fc.graph.filter_for_profile("cycling", "medium")
    for eid_list in filtered.adj.values():
        for _, e in eid_list:
            assert not e.rejected


def test_nearest_edge_within_tolerance(mini_grid):
    fc = mini_grid
    filtered = fc.graph.filter_for_profile("running", "medium")
    # point near edge between (0,0) and (100,0)
    edge, proj, dist = filtered.nearest_edge((50.0, 0.0), 80.0)
    assert edge is not None
    assert dist < 1.0


def test_nearest_edge_out_of_tolerance(mini_grid):
    fc = mini_grid
    filtered = fc.graph.filter_for_profile("running", "medium")
    edge, proj, dist = filtered.nearest_edge((5000.0, 5000.0), 80.0)
    assert edge is None
