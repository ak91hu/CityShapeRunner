import math

import pytest

from gps_art_wizzard.tools import detour_repair, geo


def test_graph_proxy_admits_a_small_real_gain_for_authoritative_routing():
    from types import SimpleNamespace

    from gps_art_wizzard.orchestrator import (
        _densify_local_guides,
        _graph_proxy_priority,
        _promising_graph_proxy,
    )

    metrics = {
        "fidelity": 0.8,
        "spatial_similarity": 0.6,
        "coverage_similarity": 0.8,
        "turning_similarity": 0.6,
        "landmark_similarity": 0.8,
        "reversal_similarity": 1.0,
        "length_similarity": 0.8,
        "extent_similarity": 0.8,
    }
    baseline = SimpleNamespace(**metrics)
    measurable_gain = SimpleNamespace(
        **(
            metrics
            | {
                "fidelity": 0.8004,
                "spatial_similarity": 0.6003,
                "turning_similarity": 0.6003,
            }
        )
    )
    sampling_noise = SimpleNamespace(
        **(
            metrics
            | {
                "spatial_similarity": 0.6001,
                "turning_similarity": 0.6001,
            }
        )
    )
    balanced_tradeoff = SimpleNamespace(
        **(
            metrics
            | {
                "fidelity": 0.84,
                "spatial_similarity": 0.67,
                "turning_similarity": 0.595,
            }
        )
    )

    assert _promising_graph_proxy(baseline, measurable_gain) == pytest.approx(
        (1.4007, 0.6003)
    )
    assert _promising_graph_proxy(baseline, balanced_tradeoff) == pytest.approx(
        (1.435, 0.595)
    )
    assert _promising_graph_proxy(baseline, sampling_noise) is None
    guides = [(47.0, 19.0), (47.002, 19.004), (47.004, 19.0)]
    dense = _densify_local_guides(guides)
    expected_dense = [
        guides[0],
        (47.001, 19.002),
        guides[1],
        (47.003, 19.002),
        guides[2],
    ]
    assert len(dense) == len(expected_dense)
    for actual, expected in zip(dense, expected_dense, strict=True):
        assert actual == pytest.approx(expected)

    slightly_higher_rank = _graph_proxy_priority(
        1.4993, 0.6831, 0.8162, 0.6831, 0.7062, near_gate=False,
    )
    slightly_higher_bottleneck = _graph_proxy_priority(
        1.4975, 0.6832, 0.8143, 0.6832, 0.7070, near_gate=False,
    )
    assert slightly_higher_rank > slightly_higher_bottleneck
    assert _graph_proxy_priority(
        1.4993, 0.6831, 0.8162, 0.6831, 0.7062, near_gate=True,
    ) < _graph_proxy_priority(
        1.4975, 0.6832, 0.8143, 0.6832, 0.7070, near_gate=True,
    )


def test_removes_only_excursion_and_keeps_original_reference():
    points = [geo.unit_to_latlon(x, y, 47, 19, 1)
              for x, y in [(0, 0), (200, 0), (400, 0), (400, 400), (0, 400), (0, 0)]]
    spur = geo.unit_to_latlon(200, -100, 47, 19, 1)
    route = points[:2] + [spur, points[1]] + points[2:]
    reference = list(points)
    proposals = detour_repair.detour_guides(reference, route)
    assert proposals == [points]
    assert reference == points
    assert route[2] == spur


def test_keeps_intentional_loop_and_never_joins_nearby_coordinates():
    points = [(47, 19), (47.001, 19), (47.001, 19.001), (47.001, 19), (47.002, 19)]
    assert detour_repair.detour_guides(points, points) == []
    near = [(47, 19), (47.001, 19), (47.001, 19.001), (47.0010001, 19), (47.002, 19)]
    assert detour_repair.detour_guides(points, near) == []


def test_turning_repair_targets_bounded_closed_windows_without_mutating_reference():
    from shapely.geometry import LineString, Point

    reference = [
        geo.unit_to_latlon(400 * math.cos(angle), 400 * math.sin(angle), 47, 19, 1)
        for angle in [2 * math.pi * index / 100 for index in range(101)]
    ]
    route = list(reference)
    route[55:66] = [
        geo.unit_to_latlon(540 * math.cos(angle), 540 * math.sin(angle), 47, 19, 1)
        for angle in [2 * math.pi * index / 100 for index in range(55, 66)]
    ]
    before = list(reference)

    proposals = detour_repair.turning_repair_guides(reference, route)

    assert 1 <= len(proposals) <= 18
    assert reference == before
    assert all(proposal[0] == route[0] and proposal[-1] == route[-1]
               for proposal in proposals)
    additions = [point for proposal in proposals for point in proposal if point not in route]
    assert additions
    assert all(LineString(reference).distance(Point(point)) < 1e-10 for point in additions)
    assert detour_repair.turning_repair_guides(reference, route, limit=0) == []
    assert detour_repair.turning_repair_guides(reference[:-1], route[:-1]) == []


def test_turning_repair_densifies_sparse_closed_reference():
    reference_xy = [(0, 0), (400, 0), (400, 400), (0, 400), (0, 0)]
    reference = [geo.unit_to_latlon(x, y, 47, 19, 1) for x, y in reference_xy]
    route_xy = []
    for (ax, ay), (bx, by) in zip(reference_xy, reference_xy[1:], strict=False):
        route_xy.extend([
            (ax + (bx - ax) * step / 10, ay + (by - ay) * step / 10)
            for step in range(10)
        ])
    route_xy.append(reference_xy[-1])
    route_xy[13:18] = [(x + 90, y - 70) for x, y in route_xy[13:18]]
    route = [geo.unit_to_latlon(x, y, 47, 19, 1) for x, y in route_xy]

    proposals = detour_repair.turning_repair_guides(reference, route)

    assert proposals
    assert all(proposal[0] == route[0] and proposal[-1] == route[-1]
               for proposal in proposals)


@pytest.mark.parametrize("reverse", [False, True])
def test_turning_repair_keeps_contour_phase_at_a_self_crossing(reverse):
    reference_xy = geo.densify_path(
        [(0, 0), (400, 400), (0, 400), (400, 0), (0, 0)],
        max_step=40,
    )
    reference = [
        geo.unit_to_latlon(x, y, 47, 19, 1) for x, y in reference_xy
    ]
    route = list(reference)
    route[25:31] = [
        geo.unit_to_latlon(x + 120, y - 80, 47, 19, 1)
        for x, y in reference_xy[25:31]
    ]
    if reverse:
        route.reverse()

    proposals = detour_repair.turning_repair_guides(reference, route)

    assert proposals
    assert all(proposal[0] == route[0] and proposal[-1] == route[-1]
               for proposal in proposals)


@pytest.mark.parametrize("guided", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("closed", [False, True])
def test_reconnect_releases_local_bend_without_moving_endpoints_or_reference(guided, reverse, closed):
    reference = [geo.unit_to_latlon(x, 0, 47, 19, 1) for x in (0, 200, 320, 800, 1200)]
    route = [geo.unit_to_latlon(x, y, 47, 19, 1) for x, y in
             ((0, 0), (200, 0), (200, 110), (320, 110), (320, 0), (600, 0), (800, 0), (1200, 0))]
    if closed:
        closing = [geo.unit_to_latlon(x, y, 47, 19, 1) for x, y in ((1200, 800), (0, 800), (0, 0))]
        reference += closing
        route += closing
    before = list(reference)
    if reverse:
        route.reverse()
    proposals = detour_repair.reconnect_guides(reference, route, limit=100, reference_guided=guided)
    assert 1 <= len(proposals) <= 2
    assert reference == before
    if guided:
        from shapely.geometry import LineString, Point
        additions = [p for guide in proposals for p in guide if p not in route]
        assert additions
        assert all(LineString(reference).distance(Point(p)) < 1e-10 for p in additions)
    detour_points = [geo.unit_to_latlon(x, 110, 47, 19, 1) for x in (200, 320)]
    assert any(all(point not in p for point in detour_points) for p in proposals)
    for proposal in proposals:
        assert proposal[0] == route[0]
        assert proposal[-1] == route[-1]
    assert detour_repair.reconnect_guides(route, route, reference_guided=guided) == []
    assert detour_repair.reconnect_guides(reference, route, limit=0) == []


@pytest.mark.parametrize("outcome", ["improved", "offroad", "regression"])
@pytest.mark.parametrize("repair", ["detour", "reconnect", "reference", "reversal"])
@pytest.mark.parametrize("deadline", [False, True])
def test_orchestrator_reroutes_proposal_and_restores_incumbent_on_failure(monkeypatch, outcome, repair, deadline):
    from types import SimpleNamespace

    from gps_art_wizzard.agents.snap_agent import SnapAgent
    from gps_art_wizzard.agents.validation_agent import ValidationAgent
    from gps_art_wizzard.config import get_settings
    from gps_art_wizzard.orchestrator import Orchestrator
    from gps_art_wizzard.state import (
        Intent,
        RouteDraft,
        RouteReadiness,
        Shape,
        SnappedRoute,
        WorkflowState,
    )
    from gps_art_wizzard.tools import ors_client, street_graph

    points = [geo.unit_to_latlon(x, y, 47, 19, 1)
              for x, y in [(0, 0), (200, 0), (400, 0), (400, 400), (0, 400), (0, 0)]]
    spur = geo.unit_to_latlon(200, -100, 47, 19, 1)
    route = points[:2] + [spur, points[1]] + points[2:]
    state = WorkflowState("square", intent=Intent("square", None, "Budapest", "run", 1.6, None),
        shape=Shape("square", [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]], True),
        route_draft=RouteDraft(47, 19, 400, 0, 0, 0, 0, points, True),
        snapped=SnappedRoute(route, geo.path_distance_m(route), True))
    ValidationAgent().run(state)
    state.validation.turning_similarity = 0.2
    state.validation.reversal_similarity = 0.2
    incumbent = state.snapped
    candidate_count = len(state.candidates)
    calls = []

    def router(guides, **kw):
        assert kw.get("guide_budget") == 50
        calls.append(guides)
        returned = [(lat + 0.1, lon) for lat, lon in points] if outcome == "regression" else points
        return returned, geo.path_distance_m(returned), outcome != "offroad", RouteReadiness()

    monkeypatch.setattr(ors_client, "snap_route_detailed", router)
    orchestrator = Orchestrator()
    if repair != "detour":
        monkeypatch.setattr(detour_repair, "reconnect_guides", lambda *args, **kwargs: [points])
    if repair == "reversal":
        monkeypatch.setattr(get_settings().routing, "shape_graph_enabled", True)
        monkeypatch.setattr(street_graph, "graph_for_state", lambda state: SimpleNamespace(revision="test"))
        def graph_proposal(graph, guides, **kwargs):
            assert kwargs["reuse_penalty"] == 3
            return SimpleNamespace(points=points, expanded=10)
        monkeypatch.setattr(street_graph, "shape_route", graph_proposal)
    method = {"detour": orchestrator._repair_detours,
              "reversal": orchestrator._repair_reversals}.get(repair, orchestrator._reconnect_contour)
    method(state, {"snap": SnapAgent(), "validation": ValidationAgent()},
           SimpleNamespace(deadline_exceeded=lambda: deadline),
           **({"reference_guided": True} if repair == "reference" else {}))
    if deadline:
        assert calls == []
        assert state.snapped is incumbent
        assert len(state.candidates) == candidate_count
        return
    assert calls == [points]
    assert state.route_draft.waypoints == points
    assert state.pending_direct_guides is None
    assert state.pending_direct_guide_budget is None
    assert len(state.candidates) == candidate_count + 1
    if outcome == "improved":
        assert state.snapped.points == points
    else:
        assert state.snapped is incumbent


def test_post_graph_reconnect_forwards_its_narrow_limit_and_stage(monkeypatch):
    from types import SimpleNamespace

    from gps_art_wizzard.orchestrator import Orchestrator

    captured = {}
    state = SimpleNamespace(
        route_draft=SimpleNamespace(waypoints=[(47.0, 19.0), (47.0, 19.01)]),
        snapped=SimpleNamespace(points=[(47.0, 19.0), (47.0, 19.01)]),
        validation=SimpleNamespace(on_roads=True),
    )
    monkeypatch.setattr(Orchestrator, "_passes_quality", staticmethod(lambda _value: False))

    def reconnect(reference, route, **kwargs):
        captured.update(reference=reference, route=route, **kwargs)
        return []

    monkeypatch.setattr(detour_repair, "reconnect_guides", reconnect)
    Orchestrator()._reconnect_contour(
        state,
        {},
        SimpleNamespace(deadline_exceeded=lambda: False),
        reference_guided=True,
        limit=1,
        stage="post_graph",
    )

    assert captured["limit"] == 1
    assert captured["reference_guided"] is True


@pytest.mark.parametrize("outcome", ["improved", "offroad", "regression"])
@pytest.mark.parametrize("deadline", [False, True])
def test_direct_turn_repair_routes_reference_guides_and_rolls_back(monkeypatch, outcome, deadline):
    from types import SimpleNamespace

    from gps_art_wizzard.agents.snap_agent import SnapAgent
    from gps_art_wizzard.agents.validation_agent import ValidationAgent
    from gps_art_wizzard.orchestrator import Orchestrator
    from gps_art_wizzard.state import (
        Intent,
        RouteDraft,
        RouteReadiness,
        Shape,
        SnappedRoute,
        WorkflowState,
    )
    from gps_art_wizzard.tools import ors_client

    points = [geo.unit_to_latlon(x, y, 47, 19, 1)
              for x, y in ((0, 0), (200, 0), (400, 0), (400, 400), (0, 400), (0, 0))]
    spur = geo.unit_to_latlon(200, -100, 47, 19, 1)
    route = points[:2] + [spur, points[1]] + points[2:]
    state = WorkflowState(
        "square", intent=Intent("square", None, "Budapest", "run", 1.6, None),
        shape=Shape("square", [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]], True),
        route_draft=RouteDraft(47, 19, 400, 0, 0, 0, 0, points, True, 1.6),
        snapped=SnappedRoute(route, geo.path_distance_m(route), True),
    )
    ValidationAgent().run(state)
    state.validation.turning_similarity = 0.2
    incumbent = state.snapped
    initial_count = len(state.candidates)
    monkeypatch.setattr(detour_repair, "turning_repair_guides", lambda *args: [points])
    calls = []

    def router(guides, **kwargs):
        assert kwargs.get("guide_budget") == 50
        calls.append(guides)
        returned = [(lat + 0.1, lon) for lat, lon in points] if outcome == "regression" else points
        return returned, geo.path_distance_m(returned), outcome != "offroad", RouteReadiness()

    monkeypatch.setattr(ors_client, "snap_route_detailed", router)
    Orchestrator()._repair_turns_directly(
        state, {"snap": SnapAgent(), "validation": ValidationAgent()},
        SimpleNamespace(deadline_exceeded=lambda: deadline),
    )
    if deadline:
        assert calls == []
        assert state.snapped is incumbent
        assert len(state.candidates) == initial_count
        return
    assert calls == [points]
    assert state.pending_direct_guides is None
    assert state.pending_direct_guide_budget is None
    assert len(state.candidates) == initial_count + 1
    assert state.history[-1]["agent"] == "turning_direct"
    assert state.history[-1]["accepted"] is (outcome == "improved")
    if outcome == "improved":
        assert state.snapped.points == points
    else:
        assert state.snapped is incumbent


@pytest.mark.parametrize("outcome", ["improved", "offroad", "regression"])
@pytest.mark.parametrize("source", ["reconnect", "turning"])
def test_graph_contour_repair_splices_one_local_path_and_rolls_back(monkeypatch, outcome, source):
    from types import SimpleNamespace

    from gps_art_wizzard.agents.snap_agent import SnapAgent
    from gps_art_wizzard.agents.validation_agent import ValidationAgent
    from gps_art_wizzard.config import get_settings
    from gps_art_wizzard.orchestrator import Orchestrator
    from gps_art_wizzard.state import (
        Intent,
        RouteDraft,
        RouteReadiness,
        Shape,
        SnappedRoute,
        WorkflowState,
    )
    from gps_art_wizzard.tools import ors_client, street_graph

    points = [geo.unit_to_latlon(x, y, 47, 19, 1)
              for x, y in [(0, 0), (200, 0), (400, 0), (400, 400), (0, 400), (0, 0)]]
    spur = geo.unit_to_latlon(200, -100, 47, 19, 1)
    route = points[:2] + [spur, points[1]] + points[2:]
    state = WorkflowState("square", intent=Intent("square", None, "Budapest", "run", 1.6, None),
        shape=Shape("square", [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]], True),
        route_draft=RouteDraft(47, 19, 400, 0, 0, 0, 0, points, True),
        snapped=SnappedRoute(route, geo.path_distance_m(route), True))
    ValidationAgent().run(state)
    state.validation.turning_similarity = 0.2
    incumbent = state.snapped
    candidate_count = len(state.candidates)

    monkeypatch.setattr(get_settings().routing, "shape_graph_enabled", True)
    graph = SimpleNamespace(revision="test")
    monkeypatch.setattr(street_graph, "graph_for_state", lambda state: graph)
    graph_calls = []

    def graph_route(actual_graph, guides, **kwargs):
        assert actual_graph is graph
        assert kwargs["closed"] is False
        graph_calls.append(guides)
        return SimpleNamespace(points=[guides[0], guides[-1]], expanded=7)

    monkeypatch.setattr(street_graph, "shape_route", graph_route)
    monkeypatch.setattr(
        detour_repair,
        "reconnect_guides",
        lambda *args, **kwargs: [points] if source == "reconnect" else [],
    )
    monkeypatch.setattr(
        detour_repair,
        "turning_repair_guides",
        lambda *args, **kwargs: [points] if source == "turning" else [],
    )
    provider_calls = []

    def router(guides, **kwargs):
        assert kwargs.get("guide_budget") == 50
        provider_calls.append(guides)
        returned = [(lat + 0.1, lon) for lat, lon in points] if outcome == "regression" else points
        return returned, geo.path_distance_m(returned), outcome != "offroad", RouteReadiness()

    monkeypatch.setattr(ors_client, "snap_route_detailed", router)
    Orchestrator()._repair_contour_with_graph(
        state,
        {"snap": SnapAgent(), "validation": ValidationAgent()},
        SimpleNamespace(deadline_exceeded=lambda: False),
    )

    assert len(graph_calls) == (2 if source == "turning" else 1)
    assert len(provider_calls) == 1
    assert provider_calls[0][0] == route[0]
    assert provider_calls[0][-1] == route[-1]
    assert state.pending_direct_guides is None
    assert state.pending_direct_guide_budget is None
    assert len(state.candidates) == candidate_count + 1
    history = [row for row in state.history if row.get("agent") == "contour_graph"]
    assert len(history) == 1
    assert history[0]["accepted"] is (outcome == "improved")
    assert history[0]["phase_targeted"] is (source == "turning")
    if outcome == "improved":
        assert state.snapped.points == points
    else:
        assert state.snapped is incumbent


def test_graph_contour_repair_recomputes_two_follow_ups_for_a_failed_shape_gate(monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace

    from gps_art_wizzard.config import get_settings
    from gps_art_wizzard.orchestrator import Orchestrator
    from gps_art_wizzard.state import (
        Intent,
        RouteDraft,
        Shape,
        SnappedRoute,
        Validation,
        WorkflowState,
    )
    from gps_art_wizzard.tools import shape_similarity, street_graph

    reference = [(47.0, 19.0), (47.001, 19.0), (47.002, 19.001),
                 (47.001, 19.002), (47.0, 19.001), (47.0, 19.0)]
    routes = [
        reference[:2] + [(47.0015, 19.0002)] + reference[3:],
        reference[:2] + [(47.0015, 19.0005)] + reference[3:],
        reference[:2] + [(47.0015, 19.0008)] + reference[3:],
        reference[:2] + [(47.0015, 19.0010)] + reference[3:],
    ]
    validation = Validation(
        score=0.8, closure=1.0, distance_fit=0.8, shape_fidelity=0.8,
        on_roads=True, spatial_similarity=0.8, coverage_similarity=0.8,
        turning_similarity=0.5, landmark_similarity=0.8,
        reversal_similarity=1.0, length_similarity=0.8, extent_similarity=0.8,
    )
    state = WorkflowState(
        "heart",
        intent=Intent("heart", None, "Szeged", "run", 5, None),
        shape=Shape("heart", [], True),
        route_draft=RouteDraft(47, 19, 500, 0, 0, 0, 0, reference, True, 5),
        snapped=SnappedRoute(routes[0], 5_000, True),
        validation=validation,
    )
    monkeypatch.setattr(get_settings().routing, "shape_graph_enabled", True)
    monkeypatch.setattr(
        street_graph, "graph_for_state", lambda state: SimpleNamespace(revision="test"),
    )
    monkeypatch.setattr(
        street_graph,
        "shape_route",
        lambda graph, guides, **kwargs: SimpleNamespace(
            points=[guides[0], guides[-1]], expanded=7,
        ),
    )
    monkeypatch.setattr(
        detour_repair,
        "turning_repair_guides",
        lambda reference, route: [route[:2] + [reference[2]] + route[3:]],
    )
    monkeypatch.setattr(detour_repair, "reconnect_guides", lambda *args, **kwargs: [])

    diagnostic_calls = 0

    def diagnostics(reference, candidate):
        nonlocal diagnostic_calls
        attempt = diagnostic_calls // 2
        is_proxy = diagnostic_calls % 2 == 1
        diagnostic_calls += 1
        turning = ((0.5, 0.6), (0.6, 0.69), (0.69, 0.705))[attempt][is_proxy]
        fidelity = ((0.8, 0.79), (0.79, 0.78), (0.78, 0.775))[attempt][is_proxy]
        return SimpleNamespace(
            fidelity=fidelity,
            spatial_similarity=0.8,
            coverage_similarity=0.8,
            turning_similarity=turning,
            landmark_similarity=0.8,
            reversal_similarity=1.0,
            length_similarity=0.8,
            extent_similarity=0.8,
        )

    monkeypatch.setattr(
        shape_similarity, "similarity_diagnostics_between_routes", diagnostics,
    )
    measurements = 0

    def measure(candidate_state, nodes):
        nonlocal measurements
        measurements += 1
        candidate_state.snapped = SnappedRoute(routes[measurements], 5_000, True)
        candidate_state.validation = replace(
            validation,
            shape_fidelity=0.8 - 0.01 * measurements,
            turning_similarity=(0.6, 0.69, 0.705)[measurements - 1],
        )

    monkeypatch.setattr(Orchestrator, "_measure_route_variants", staticmethod(measure))

    Orchestrator()._repair_contour_with_graph(
        state, {}, SimpleNamespace(deadline_exceeded=lambda: False),
    )

    assert measurements == 3
    assert state.snapped.points == routes[3]
    assert state.validation.turning_similarity == pytest.approx(0.705)
    history = [row for row in state.history if row.get("agent") == "contour_graph"]
    assert [row["attempt"] for row in history] == [1, 2, 3]
    assert all(row["accepted"] for row in history)


def test_graph_contour_repair_considers_length_failure_when_turns_pass(monkeypatch):
    from types import SimpleNamespace

    from gps_art_wizzard.config import get_settings
    from gps_art_wizzard.orchestrator import Orchestrator
    from gps_art_wizzard.state import (
        Intent,
        RouteDraft,
        Shape,
        SnappedRoute,
        Validation,
        WorkflowState,
    )
    from gps_art_wizzard.tools import street_graph

    points = [(47.0, 19.0), (47.001, 19.0), (47.001, 19.001),
              (47.0, 19.001), (47.0, 19.0)]
    state = WorkflowState(
        "square", intent=Intent("square", None, "Szeged", "run", 1, None),
        shape=Shape("square", [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]], True),
        route_draft=RouteDraft(47, 19, 500, 0, 0, 0, 0, points, True, 1),
        snapped=SnappedRoute(points, 1_000, True),
        validation=Validation(0.8, 1.0, 0.9, 0.8, turning_similarity=0.8,
                              length_similarity=0.5),
    )
    monkeypatch.setattr(get_settings().routing, "shape_graph_enabled", True)
    calls = []
    monkeypatch.setattr(street_graph, "graph_for_state", lambda _state: calls.append("graph") or SimpleNamespace(revision="test"))
    monkeypatch.setattr(detour_repair, "reconnect_guides",
                        lambda *args, **kwargs: calls.append("reconnect") or [])
    monkeypatch.setattr(detour_repair, "turning_repair_guides",
                        lambda *args, **kwargs: pytest.fail("turning guides are not needed"))

    Orchestrator()._repair_contour_with_graph(
        state, {}, SimpleNamespace(deadline_exceeded=lambda: False),
    )
    assert calls == ["graph", "reconnect", "reconnect"]


@pytest.mark.parametrize("reason", ["passing", "anchor", "bearing", "disabled", "expired_after_graph"])
def test_reversal_repair_skips_inapplicable_or_expired_search(monkeypatch, reason):
    from types import SimpleNamespace

    from gps_art_wizzard.config import get_settings
    from gps_art_wizzard.orchestrator import Orchestrator
    from gps_art_wizzard.tools import street_graph

    draft = SimpleNamespace(anchored_start=(47, 19) if reason == "anchor" else None,
                            preferred_start_direction_deg=90 if reason == "bearing" else None)
    state = SimpleNamespace(route_draft=draft, snapped=object(),
                            validation=SimpleNamespace(on_roads=True,
                                reversal_similarity=1 if reason == "passing" else 0.2))
    monkeypatch.setattr(get_settings().routing, "shape_graph_enabled", reason != "disabled")
    calls = []
    def graph_for_state(state):
        calls.append("graph")
        return object()
    monkeypatch.setattr(street_graph, "graph_for_state", graph_for_state)
    def unexpected(*args, **kwargs):
        pytest.fail("No graph search or provider request should start")
    monkeypatch.setattr(street_graph, "shape_route", unexpected)
    runtime = SimpleNamespace(deadline_exceeded=lambda: bool(calls))
    Orchestrator()._repair_reversals(state, {}, runtime)
    assert calls == (["graph"] if reason == "expired_after_graph" else [])
