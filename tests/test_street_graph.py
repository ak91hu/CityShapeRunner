"""Graph identity, activity access, ordered shapes, turns and bounded fallback."""
from gps_art_wizzard.tools import street_graph
from gps_art_wizzard.tools.street_graph import (
    StreetGraph,
    build_graph,
    connectivity_proxy,
    shape_route,
)


def node(identifier, x, y):
    return {"type": "node", "id": identifier, "lat": 47.5 + y / 111000, "lon": 19 + x / 75000}


def way(identifier, refs, **tags):
    return {"type": "way", "id": identifier, "nodes": refs, "tags": {"highway": "residential", **tags}}


def test_ordered_shape_follows_corners_instead_of_shortcut():
    elements = [node(1, 0, 0), node(2, 400, 0), node(3, 400, 400), node(4, 0, 400),
                way(10, [1, 2, 3, 4, 1]), way(11, [1, 3])]
    graph = build_graph(elements)
    guides = [graph.nodes[i] for i in (1, 2, 3, 4, 1)]
    result = shape_route(graph, guides, closed=True, seconds=5)
    assert result is not None
    assert result.points == guides
    assert result.distance_m > 1500


def test_bridge_crossing_does_not_create_an_intersection():
    graph = build_graph([node(1, 0, 0), node(2, 400, 0), node(3, 200, -200), node(4, 200, 200),
                         way(10, [1, 2]), way(11, [3, 4], bridge="yes")])
    assert connectivity_proxy(graph, [graph.nodes[1], graph.nodes[4]]) == (0, None)
    assert shape_route(graph, [graph.nodes[1], graph.nodes[4]]) is None


def test_nearby_isolated_nodes_do_not_hide_connected_guide_alternative():
    graph = build_graph([
        node(1, 0, 0), node(2, 400, 0), node(3, 800, 0), way(10, [1, 2, 3]),
        node(4, 400, 40), node(5, 401, 40), node(6, 399, 40), way(20, [4, 5, 6]),
    ])
    guides = [graph.nodes[1], graph.nodes[4], graph.nodes[3]]
    assert set(graph.nearest(guides)[1]) == {4, 5, 6}
    assert graph.nearest(guides, common_component=True)[1] == [2]
    proposal = shape_route(graph, guides, seconds=5)
    assert proposal is not None
    assert proposal.points == [graph.nodes[i] for i in (1, 2, 3)]
    # The cheap placement proxy still measures the closest streets. The full
    # search can explore connected alternatives without changing its ranking.
    assert connectivity_proxy(graph, guides) == (0, None)


def test_nearest_sorts_only_nodes_inside_search_radius(monkeypatch):
    center = (47.5, 19.0)
    nodes = {index: (47.5 + index * 0.001, 19.0) for index in range(1, 1001)}
    nodes[1001] = center
    nodes[1002] = (47.5001, 19.0)
    graph = StreetGraph(nodes, {})
    original_argsort = street_graph.np.argsort
    sorted_lengths = []

    def count_argsort(values, *args, **kwargs):
        sorted_lengths.append(len(values))
        return original_argsort(values, *args, **kwargs)

    monkeypatch.setattr(street_graph.np, "argsort", count_argsort)
    assert graph.nearest([center], radius=30) == [[1001, 1002]]
    assert sorted_lengths == [2]


def test_component_filter_keeps_radius_and_directed_constraints():
    graph = build_graph([
        node(1, 0, 0), node(2, 400, 0), node(3, 800, 0), way(10, [1, 2, 3], oneway="yes"),
        node(4, 400, 40), node(5, 401, 40), node(6, 399, 40), way(20, [4, 5, 6]),
    ], "bike")
    guides = [graph.nodes[3], graph.nodes[4], graph.nodes[1]]
    assert shape_route(graph, guides, seconds=5) is None
    assert set(graph.nearest(guides, radius=20, common_component=True)[1]) == {4, 5, 6}
    assert graph.nearest([], common_component=True) == []


def test_bicycle_oneway_and_foot_access_are_distinct():
    data = [node(1, 0, 0), node(2, 400, 0), way(10, [1, 2], oneway="yes")]
    run, bike = build_graph(data, "run"), build_graph(data, "bike")
    assert shape_route(run, [run.nodes[2], run.nodes[1]]) is not None
    assert shape_route(bike, [bike.nodes[2], bike.nodes[1]]) is None
    data[-1]["tags"]["oneway:bicycle"] = "no"
    bike = build_graph(data, "bike")
    assert shape_route(bike, [bike.nodes[2], bike.nodes[1]]) is not None


def test_private_and_conditional_access_are_not_assumed_open():
    data = [node(1, 0, 0), node(2, 400, 0), way(10, [1, 2], access="private")]
    assert not build_graph(data).nodes
    data[-1]["tags"]["foot"] = "yes"
    assert build_graph(data).nodes
    data[-1]["tags"]["foot:conditional"] = "no @ (sunset-sunrise)"
    assert not build_graph(data).nodes


def test_turn_restriction_survives_guide_boundary():
    data = [node(1, 0, 0), node(2, 400, 0), node(3, 400, 400),
            way(10, [1, 2], oneway="yes"), way(20, [2, 3], oneway="yes"),
            {"type": "relation", "id": 30, "tags": {"type": "restriction", "restriction": "no_left_turn"},
             "members": [{"type": "way", "ref": 10, "role": "from"},
                         {"type": "node", "ref": 2, "role": "via"},
                         {"type": "way", "ref": 20, "role": "to"}]}]
    bike = build_graph(data, "bike")
    assert shape_route(bike, [bike.nodes[i] for i in (1, 2, 3)]) is None
    run = build_graph(data, "run")
    assert shape_route(run, [run.nodes[i] for i in (1, 2, 3)]) is not None


def test_search_budget_returns_no_unverified_partial_route():
    graph = build_graph([node(1, 0, 0), node(2, 400, 0), way(10, [1, 2])])
    assert shape_route(graph, [graph.nodes[1], graph.nodes[2]], max_expansions=1) is None


def test_optional_reuse_cost_can_avoid_retracing_an_earlier_guide_leg():
    graph = build_graph([node(1, 0, 0), node(2, 400, 0), node(3, 400, 40), node(4, 0, 40),
                         way(10, [1, 2]), way(20, [2, 3, 4, 1])])
    guides = [graph.nodes[i] for i in (1, 2, 1)]
    original = shape_route(graph, guides, closed=True, seconds=5)
    challenger = shape_route(graph, guides, closed=True, seconds=5, reuse_penalty=3)
    assert original is not None and challenger is not None
    assert original.points == guides
    assert graph.nodes[3] in challenger.points
    assert graph.nodes[4] in challenger.points
    assert challenger.points[0] == challenger.points[-1]
    assert challenger.distance_m > original.distance_m


def test_network_detour_proxy_measures_connected_road_length():
    graph = build_graph([node(1, 0, 0), node(2, 0, 400), node(3, 400, 400), node(4, 400, 0), way(10, [1, 2, 3, 4])])
    connected, ratio = connectivity_proxy(graph, [graph.nodes[1], graph.nodes[4]])
    assert connected == 1
    assert ratio > 2.8


def test_shape_cost_can_choose_longer_streets_that_follow_the_contour():
    coordinates = [(0, 0), (50, 150), (150, 50), (150, 250), (250, 150),
                   (250, 350), (350, 250), (400, 400), (400, 0)]
    data = [node(i + 1, x, y) for i, (x, y) in enumerate(coordinates)]
    data += [way(10, list(range(1, 9))), way(20, [1, 9, 8])]
    graph = build_graph(data)
    result = shape_route(graph, [graph.nodes[1], graph.nodes[8]], seconds=5)
    assert result is not None
    assert graph.nodes[9] not in result.points
    assert result.distance_m > 900  # the ordinary shortest route is ~800 m


def test_no_uturn_on_same_way_still_allows_straight_travel():
    data = [node(1, 0, 0), node(2, 400, 0), node(3, 800, 0), way(10, [1, 2, 3]),
            {"type": "relation", "id": 30, "tags": {"type": "restriction", "restriction": "no_u_turn"},
             "members": [{"type": "way", "ref": 10, "role": "from"},
                         {"type": "node", "ref": 2, "role": "via"},
                         {"type": "way", "ref": 10, "role": "to"}]}]
    graph = build_graph(data, "bike")
    assert not graph.turn_allowed(10, 2, 10, 1, 1)
    assert graph.turn_allowed(10, 2, 10, 1, 3)
    assert shape_route(graph, [graph.nodes[i] for i in (1, 2, 3)]) is not None


def test_shape_search_keeps_legal_arrival_when_cheapest_arrival_cannot_continue():
    data = [node(1, 0, 0), node(2, 400, 0), node(3, 800, 0), node(4, 200, 180),
            way(10, [1, 2], oneway="yes"), way(11, [1, 4, 2], oneway="yes"),
            way(20, [2, 3], oneway="yes"),
            {"type": "relation", "id": 30, "tags": {"type": "restriction", "restriction": "no_straight_on"},
             "members": [{"type": "way", "ref": 10, "role": "from"},
                         {"type": "node", "ref": 2, "role": "via"},
                         {"type": "way", "ref": 20, "role": "to"}]}]
    graph = build_graph(data, "bike")
    result = shape_route(graph, [graph.nodes[i] for i in (1, 2, 3)], seconds=5)
    assert result is not None
    assert result.points == [graph.nodes[i] for i in (1, 4, 2, 3)]


def test_restricted_guide_keeps_arrival_that_can_reach_the_next_guide():
    # The cheap arrival can legally leave the guide, but only into a one-way
    # dead end. A different incoming way permits continuation along the shape.
    data = [node(1, 0, 0), node(2, 400, 0), node(3, 800, 0), node(4, 200, 180),
            node(5, 400, -200), way(10, [1, 2], oneway="yes"),
            way(11, [1, 4, 2], oneway="yes"), way(20, [2, 3], oneway="yes"),
            way(21, [2, 5], oneway="yes"),
            {"type": "relation", "id": 30, "tags": {"type": "restriction", "restriction": "no_straight_on"},
             "members": [{"type": "way", "ref": 10, "role": "from"},
                         {"type": "node", "ref": 2, "role": "via"},
                         {"type": "way", "ref": 20, "role": "to"}]}]
    graph = build_graph(data, "bike")
    result = shape_route(graph, [graph.nodes[i] for i in (1, 2, 3)], seconds=5)
    assert result is not None
    assert result.points == [graph.nodes[i] for i in (1, 4, 2, 3)]
