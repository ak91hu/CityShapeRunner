"""Integration boundaries: graph proposals are routed, measured and never exported alone."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from gps_art_wizzard.agents.snap_agent import SnapAgent
from gps_art_wizzard.agents.validation_agent import ValidationAgent
from gps_art_wizzard.orchestrator import Orchestrator
from gps_art_wizzard.quality import DISTANCE_FIT_THRESHOLD
from gps_art_wizzard.state import (
    EvaluatedCandidate,
    Intent,
    MapPlacement,
    RouteDraft,
    RouteReadiness,
    Shape,
    SnappedRoute,
    Validation,
    WorkflowState,
)
from gps_art_wizzard.tools import geo, ors_client, shape_similarity, street_graph


def _distance_repair_state() -> WorkflowState:
    points = [(46.25, 20.15), (46.26, 20.16), (46.25, 20.15)]
    validation = Validation(
        score=0.757, closure=1.0, distance_fit=0.532, shape_fidelity=0.795,
        spatial_similarity=0.739, coverage_similarity=0.817,
        turning_similarity=0.645, landmark_similarity=0.932,
        reversal_similarity=1.0, length_similarity=0.656,
        extent_similarity=0.985, actual_distance_km=11.84,
        target_distance_km=15.0,
    )
    return WorkflowState(
        "heart", intent=Intent("heart", None, "Szeged", "bike", 15, None),
        shape=Shape("heart", [[(0, 0), (1, 0), (0, 0)]], True),
        route_draft=RouteDraft(46.25, 20.15, 2793, 0, 0, 0, 0.8, points, True, 15),
        snapped=SnappedRoute(points, 11_840, True), validation=validation,
    )


def test_final_distance_repair_accepts_measured_on_road_route_without_losing_shape(monkeypatch):
    state = _distance_repair_state()
    measured = []

    def measure(trial, nodes):
        measured.append(trial.route_draft.scale_m)
        trial.snapped = SnappedRoute(trial.route_draft.waypoints, 13_300, True)
        trial.validation = replace(
            state.validation, distance_fit=0.712, actual_distance_km=13.3,
            shape_fidelity=0.770, turning_similarity=0.660,
            length_similarity=0.670, score=0.799,
        )

    monkeypatch.setattr(Orchestrator, "_measure_route_variants", staticmethod(measure))
    nodes = {"placement": SimpleNamespace(run=lambda trial: trial)}
    Orchestrator()._repair_distance(
        state, nodes, SimpleNamespace(deadline_exceeded=lambda: False),
    )
    assert len(measured) == 1
    assert state.route_draft.scale_m > 2793
    assert state.validation.distance_fit >= DISTANCE_FIT_THRESHOLD
    assert state.validation.shape_fidelity >= 0.7
    assert state.history[-1]["agent"] == "distance_repair"
    assert state.history[-1]["accepted"]


def test_final_distance_repair_rejects_shape_regression_and_restores_incumbent(monkeypatch):
    state = _distance_repair_state()
    incumbent_route = state.snapped

    def measure(trial, nodes):
        trial.snapped = SnappedRoute(trial.route_draft.waypoints, 15_000, True)
        trial.validation = replace(
            trial.validation, distance_fit=1.0, actual_distance_km=15.0,
            shape_fidelity=0.68, turning_similarity=0.50, score=0.8,
        )

    monkeypatch.setattr(Orchestrator, "_measure_route_variants", staticmethod(measure))
    Orchestrator()._repair_distance(
        state, {"placement": SimpleNamespace(run=lambda trial: trial)},
        SimpleNamespace(deadline_exceeded=lambda: False),
    )
    assert len(state.history) == 4
    assert all(not entry["accepted"] for entry in state.history)
    assert state.route_draft.scale_m == 2793
    assert state.snapped == incumbent_route
    assert state.validation.distance_fit == 0.532


def test_final_distance_repair_preserves_user_placed_footprint(monkeypatch):
    state = _distance_repair_state()
    state.map_placement = MapPlacement(46.25, 20.15, 2793, 0)
    monkeypatch.setattr(Orchestrator, "_measure_route_variants",
                        staticmethod(lambda *args: pytest.fail("must not reroute")))
    Orchestrator()._repair_distance(
        state, {}, SimpleNamespace(deadline_exceeded=lambda: False),
    )
    assert not state.history


def test_late_shape_repair_cannot_create_new_distance_failure():
    incumbent = replace(
        _distance_repair_state().validation, distance_fit=0.636,
        actual_distance_km=12.74, shape_fidelity=0.757,
    )
    shorter = replace(
        incumbent, distance_fit=0.532, actual_distance_km=11.84,
        shape_fidelity=0.795, turning_similarity=0.69,
    )
    assert not Orchestrator._candidate_is_better(shorter, incumbent)
    assert not Orchestrator._shape_repair_is_better(shorter, incumbent)
    assert Orchestrator._shape_repair_is_better(
        replace(shorter, distance_fit=0.61), incumbent,
    )


def test_graph_proposal_must_receive_directions_geometry(monkeypatch):
    original = [(47.5, 19), (47.504, 19.004)]
    proposed = [(47.5, 19), (47.502, 19.002), (47.504, 19.004)]
    returned = [(47.5, 19.00001), (47.502, 19.0021), (47.504, 19.004)]
    state = WorkflowState("line", intent=Intent("line", None, "Budapest", "run", 1, None),
        shape=Shape("line", [[(0, 0), (1, 1)]], False),
        route_draft=RouteDraft(47.5, 19, 500, 0, 0, 0, 0, original, False))
    graph = street_graph.StreetGraph({}, {}, revision="synthetic-test")
    monkeypatch.setattr(street_graph, "graph_for_state", lambda state: graph)
    monkeypatch.setattr(street_graph, "shape_route", lambda *a, **kw:
        street_graph.GraphProposal(proposed, 550, 500, 10, graph.revision))
    calls = []

    def directions(points, **kwargs):
        assert kwargs.get("guide_budget") == 50
        calls.append(points)
        return returned, 560, True, RouteReadiness()

    monkeypatch.setattr(ors_client, "snap_route_detailed", directions)
    SnapAgent().run(state)
    assert calls == [proposed]
    assert state.snapped.points == returned
    assert state.route_draft.waypoints == original


def test_rejected_graph_proposal_falls_back_without_claiming_road_evidence(monkeypatch):
    original = [(47.5, 19), (47.504, 19.004)]
    proposed = [original[0], (47.502, 19.002), original[-1]]
    state = WorkflowState("line", intent=Intent("line", None, "Budapest", "run", 1, None),
        shape=Shape("line", [[(0, 0), (1, 1)]], False),
        route_draft=RouteDraft(47.5, 19, 500, 0, 0, 0, 0, original, False))
    monkeypatch.setattr(street_graph, "graph_for_state", lambda state: street_graph.StreetGraph({}, {}))
    monkeypatch.setattr(street_graph, "shape_route", lambda *a, **kw:
        street_graph.GraphProposal(proposed, 550, 500, 10, "test"))
    calls = []

    def fail(points, **kwargs):
        assert kwargs.get("guide_budget") == (50 if points == proposed else None)
        calls.append(points)
        return points, 500, False, RouteReadiness()

    monkeypatch.setattr(ors_client, "snap_route_detailed", fail)
    SnapAgent().run(state)
    assert calls == [proposed, original]
    assert not state.snapped.snapped


@pytest.mark.parametrize("direct_wins", [True, False])
@pytest.mark.parametrize("recoverable", [True, False])
def test_graph_and_direct_routes_are_both_measured_and_retained(
    monkeypatch, direct_wins, recoverable,
):
    original = [(47.5, 19), (47.502, 19.004), (47.504, 19)]
    distorted = [original[0], (47.502, 19.02), original[-1]]
    proposed = [original[0], (47.502, 19.003), original[-1]]
    state = WorkflowState("line", intent=Intent("line", None, "Budapest", "run", 1, None),
        shape=Shape("line", [[(0, 0), (1, 1)]], False),
        route_draft=RouteDraft(47.5, 19, 500, 0, 0, 0, 0, original, False))
    monkeypatch.setattr(street_graph, "graph_for_state", lambda state: street_graph.StreetGraph({}, {}))
    monkeypatch.setattr(street_graph, "shape_route", lambda *a, **kw:
        street_graph.GraphProposal(proposed, 1000, 1000, 10, "test"))
    calls = []

    def directions(points, **kwargs):
        assert kwargs.get("guide_budget") == (50 if points == proposed else None)
        calls.append(points)
        good = (points == original) == direct_wins
        return original if good else distorted, 1000, True, RouteReadiness()

    monkeypatch.setattr(ors_client, "snap_route_detailed", directions)
    Orchestrator._measure_route_variants(
        state, {"snap": SnapAgent(), "validation": ValidationAgent()},
        recoverable=recoverable,
    )
    assert calls == [proposed, original]
    assert state.snapped.points == original
    assert state.route_draft.waypoints == original
    assert state.pending_direct_guides is None
    assert state.pending_direct_guide_budget is None
    assert state.candidate_count == 2
    assert len(state.candidates) == 2
    assert {tuple(c.points) for c in state.candidates} == {tuple(original), tuple(distorted)}
    assert state.validation.shape_fidelity > 0.99


def test_street_repair_budget_is_consumed_without_changing_next_drawing(monkeypatch):
    original = [(47.5, 19), (47.502, 19.004), (47.504, 19)]
    repaired = [original[0], (47.502, 19.003), original[-1]]
    state = WorkflowState("line", intent=Intent("line", None, "Budapest", "run", 1, None),
        shape=Shape("line", [[(0, 0), (1, 1)]], False),
        route_draft=RouteDraft(47.5, 19, 500, 0, 0, 0, 0, original, False),
        pending_direct_guides=repaired, pending_direct_guide_budget=50)
    monkeypatch.setattr(street_graph, "graph_for_state", lambda state: None)
    calls = []

    def directions(points, **kwargs):
        calls.append((points, kwargs.get("guide_budget")))
        return points, 1000, True, RouteReadiness()

    monkeypatch.setattr(ors_client, "snap_route_detailed", directions)
    shell = Orchestrator._measurement_shell(state)
    assert shell.pending_direct_guides is None
    assert shell.pending_direct_guide_budget is None
    SnapAgent().run(state)
    assert state.snapped.points == repaired
    assert state.route_draft.waypoints == original
    assert state.pending_direct_guides is None
    assert state.pending_direct_guide_budget is None
    SnapAgent().run(state)
    assert calls == [(repaired, 50), (original, None)]


@pytest.mark.parametrize("deadline", [True, False])
def test_shape_polish_preserves_incumbent_and_obeys_budget(monkeypatch, deadline):
    from dataclasses import replace

    from gps_art_wizzard.agents.preflight_agent import PreflightAgent
    from gps_art_wizzard.config import get_settings

    original = [(47.5, 19), (47.502, 19.004), (47.504, 19)]
    state = WorkflowState("line", intent=Intent("line", None, "Budapest", "run", 1, None),
        shape=Shape("line", [[(0, 0), (1, 1)]], False),
        route_draft=RouteDraft(47.5, 19, 500, 0, 0, 0, 0, original, False))
    monkeypatch.setattr(street_graph, "graph_for_state", lambda state: None)
    monkeypatch.setattr(ors_client, "snap_route_detailed", lambda points, **kw:
        (original, 1000, True, RouteReadiness()))
    nodes = {"snap": SnapAgent(), "validation": ValidationAgent()}
    Orchestrator._measure_route_variants(state, nodes)
    component = replace(state.candidates[0],
                        validation=replace(state.validation, turning_similarity=0.5),
                        rotation_deg=25, lon_offset_m=40)
    state.candidates.append(component)
    state.validation.turning_similarity = 0.1  # a failed gate keeps refinement active
    incumbent = state.validation
    state.preflight_count = 180
    cfg = get_settings().workflow
    monkeypatch.setattr(cfg, "preflight_adaptive", True)
    monkeypatch.setattr(cfg, "shape_polish_candidates", 100)  # hard cap is four
    drafts = [state.route_draft] * 16
    monkeypatch.setattr(PreflightAgent, "_refined_drafts", lambda *a: drafts[:a[4]])
    results = [SimpleNamespace(candidate_index=i, score=0.9) for i in range(16)]
    monkeypatch.setattr(PreflightAgent, "_valid_results", lambda *a: results)
    monkeypatch.setattr(PreflightAgent, "_diverse_shortlist", lambda self, r, d, limit: r[:limit])
    screened = []
    def preflight(points, **kwargs):
        screened.append(len(points))
        return results
    monkeypatch.setattr(ors_client, "preflight_route_candidates", preflight)
    monkeypatch.setattr(ors_client, "snap_route_detailed", lambda points, **kw:
        ([original[0], (47.502, 19.03), original[-1]], 9000, True, RouteReadiness()))
    Orchestrator()._polish_shape(state, nodes, SimpleNamespace(deadline_exceeded=lambda: deadline))
    assert state.validation is incumbent
    assert state.snapped.points == original
    assert screened == ([] if deadline else [16])
    assert len(state.candidates) == (2 if deadline else 6)


def test_component_polish_seed_uses_a_usable_candidate_that_improves_failed_cue():
    points = [(47.5, 19), (47.501, 19.001), (47.5, 19)]
    draft = RouteDraft(47.5, 19, 500, 0, 0, 0, 0, points, True, 1)
    incumbent = Validation(0.8, 1, 0.8, 0.75, turning_similarity=0.5,
                           spatial_similarity=0.8, coverage_similarity=0.8,
                           landmark_similarity=0.8, length_similarity=0.8,
                           extent_similarity=0.8, reversal_similarity=1)
    state = WorkflowState("circle", shape=Shape("circle", [[(0, 0), (1, 0)]], True),
                          route_draft=draft, validation=incumbent)

    def candidate(turning, distance_fit, rotation, east):
        validation = Validation(0.8, 1, distance_fit, 0.75, turning_similarity=turning,
                                spatial_similarity=0.8, coverage_similarity=0.8,
                                landmark_similarity=0.8, length_similarity=0.8,
                                extent_similarity=0.8, reversal_similarity=1,
                                actual_distance_km=0.9)
        return EvaluatedCandidate("circle", "template", points, points, 1000, True, True, 1,
                                  validation, rotation, 600, 20, east)

    state.candidates = [candidate(0.65, 0.8, 55, 40), candidate(0.9, 0.5, 90, 900)]
    seed_result = Orchestrator._component_polish_seed(state)
    assert seed_result is not None
    seed, measured_km = seed_result
    assert (seed.rotation_deg, seed.scale_m, seed.lat_offset_m, seed.lon_offset_m) == (55, 600, 20, 40)
    assert measured_km == 0.9
    assert state.route_draft is draft
    state.candidates = [candidate(0.51, 0.8, 55, 40)]
    assert Orchestrator._component_polish_seed(state) is None


def test_component_polish_adds_one_challenger_without_displacing_four_incumbent_candidates(monkeypatch):
    from dataclasses import replace

    from gps_art_wizzard.agents.preflight_agent import PreflightAgent
    from gps_art_wizzard.config import get_settings

    points = [(47.5, 19), (47.501, 19.001), (47.5, 19)]
    validation = Validation(0.8, 1, 0.8, 0.75, turning_similarity=0.5,
                            spatial_similarity=0.8, coverage_similarity=0.8,
                            landmark_similarity=0.8, length_similarity=0.8,
                            extent_similarity=0.8, reversal_similarity=1)
    draft = RouteDraft(47.5, 19, 500, 0, 0, 0, 0, points, True, 1)
    state = WorkflowState("circle", intent=Intent("circle", None, "Budapest", "run", 1, None),
                          shape=Shape("circle", [[(0, 0), (1, 0), (0, 0)]], True),
                          route_draft=draft, snapped=SimpleNamespace(points=points),
                          validation=validation, preflight_count=1)
    state.candidates = [EvaluatedCandidate(
        "circle", "template", points, points, 1000, True, True, 1,
        replace(validation, turning_similarity=0.65), 30, 500, 0, 40,
    )]
    cfg = get_settings().workflow
    monkeypatch.setattr(cfg, "preflight_adaptive", True)
    monkeypatch.setattr(cfg, "shape_polish_candidates", 4)
    incumbent_drafts = [replace(draft, rotation_deg=index) for index in range(16)]
    monkeypatch.setattr(PreflightAgent, "_refined_drafts", lambda *args: incumbent_drafts)
    results = [SimpleNamespace(candidate_index=index, score=1 - index / 100) for index in range(16)]
    monkeypatch.setattr(PreflightAgent, "_valid_results", lambda *args: results)
    def shortlist(self, rows, drafts, limit):
        assert all(row.candidate_index < 16 for row in rows)
        return rows[:limit]
    monkeypatch.setattr(PreflightAgent, "_diverse_shortlist", shortlist)
    monkeypatch.setattr(ors_client, "preflight_route_candidates", lambda *args, **kwargs: results)
    graph = street_graph.StreetGraph({1: points[0], 2: points[1]}, {}, revision="test")
    monkeypatch.setattr(street_graph, "graph_for_state", lambda state: graph)
    monkeypatch.setattr(street_graph, "shape_route", lambda graph, guides, **kwargs:
                        street_graph.GraphProposal(guides, 1000, 1, 1, "test"))
    monkeypatch.setattr(shape_similarity, "similarity_diagnostics_between_routes",
                        lambda reference, candidate, **kwargs:
                        SimpleNamespace(fidelity=geo.path_distance_m(reference)))
    measured = []
    def measure(candidate_state, nodes):
        measured.append((candidate_state.route_draft.rotation_deg,
                         candidate_state.route_draft.lon_offset_m,
                         candidate_state.route_draft.scale_m))
        candidate_state.validation = replace(validation, shape_fidelity=0.7)
    monkeypatch.setattr(Orchestrator, "_measure_route_variants", staticmethod(measure))
    Orchestrator()._polish_shape(state, {}, SimpleNamespace(deadline_exceeded=lambda: False))
    assert measured[:4] == [(0, 0, 500), (1, 0, 500), (2, 0, 500), (3, 0, 500)]
    assert len(measured) == 5
    assert measured[-1][0] not in {0, 1, 2, 3}
    assert measured[-1][2] == 625


@pytest.mark.parametrize("latitude", [0.0, 70.0])
def test_directions_vertices_survive_snapping_validation_and_export(monkeypatch, latitude):
    import gpxpy

    from gps_art_wizzard.agents.export_agent import ExportAgent
    from gps_art_wizzard.tools import geo

    # Small street bends would disappear under the former 25 m simplification.
    points = [geo.unit_to_latlon(x, y, latitude, 19, 1)
              for x, y in [(0, 0), (40, 2), (80, 0), (120, 14), (160, 0), (200, 0)]]
    state = WorkflowState("line", intent=Intent("line", None, "Budapest", "run", 1, None),
        shape=Shape("line", [[(0, 0), (1, 0)]], False),
        route_draft=RouteDraft(latitude, 19, 500, 0, 0, 0, 25, points, False))
    monkeypatch.setattr(street_graph, "graph_for_state", lambda state: None)
    monkeypatch.setattr(ors_client, "snap_route_detailed", lambda *a, **kw:
        (points, geo.path_distance_m(points), True, RouteReadiness()))
    Orchestrator._measure_route_variants(state, {"snap": SnapAgent(), "validation": ValidationAgent()})
    ExportAgent().run(state)
    assert state.snapped.points == points
    assert state.candidates[0].points == points
    parsed = gpxpy.parse(state.export.gpx)
    exported = [(point.latitude, point.longitude) for point in parsed.tracks[0].segments[0].points]
    assert len(exported) == len(points)
    assert all(geo.haversine(*actual, *expected) < 0.001
               for actual, expected in zip(exported, points, strict=True))


@pytest.mark.parametrize("routed,validated", [(False, False), (False, True), (True, False)])
def test_no_road_evidence_cannot_export_even_with_high_shape_score(monkeypatch, routed, validated):
    from gps_art_wizzard.agents.export_agent import ExportAgent
    from gps_art_wizzard.state import SnappedRoute, Validation
    from gps_art_wizzard.tools import gpx_writer

    state = WorkflowState("line", intent=Intent("line", None, "Budapest", "run", 1, None),
        snapped=SnappedRoute([(47, 19), (47.001, 19)], 1000, routed),
        validation=Validation(1, 1, 1, 1, on_roads=validated))
    monkeypatch.setattr(gpx_writer, "to_gpx", lambda *a, **kw: pytest.fail("must not serialize"))
    ExportAgent().run(state)
    assert state.export is None


@pytest.mark.parametrize("kind", ["multipoint", "zero_length", "skipped_warning", "skipped_query", "valid"])
def test_provider_success_requires_complete_street_linestring(kind):
    coordinates = [[19, 47], [19.001, 47]]
    geometry = {"type": "LineString", "coordinates": coordinates}
    properties = {"summary": {"distance": 100}, "warnings": [{"code": 4}]}
    data = {"features": [{"geometry": geometry, "properties": properties}]}
    if kind == "multipoint":
        geometry["type"] = "MultiPoint"
    elif kind == "zero_length":
        geometry["coordinates"] = [coordinates[0], coordinates[0]]
    elif kind == "skipped_warning":
        properties["warnings"] = [{"code": 3}]
    elif kind == "skipped_query":
        data["metadata"] = {"query": {"skip_segments": [1]}}
    response = SimpleNamespace(status_code=200, json=lambda: data)
    client = SimpleNamespace(post=lambda *a, **kw: response)
    result = ors_client._ors_request(
        "https://routing.test/geojson", {}, coordinates, preference="recommended",
        continue_straight=False, radius=120, client=client,
    )
    assert isinstance(result, ors_client._ORSRouteResult) == (kind == "valid")


def test_edited_route_map_and_download_keep_more_than_500_street_vertices(monkeypatch):
    from gps_art_wizzard.api.routes import EditedRouteRequest, edit_route
    from gps_art_wizzard.tools import geo

    points = [(47 + i * 0.00001, 19 + (i % 2) * 0.000005) for i in range(620)]
    monkeypatch.setattr(ors_client, "snap_route_detailed", lambda *a, **kw:
        (points, geo.path_distance_m(points), True, RouteReadiness()))
    response = edit_route(EditedRouteRequest(
        control_points=[list(points[0]), list(points[-1])], sport="run", closed=False,
    ))
    assert response["points_preview"] == [list(point) for point in points]
    assert response["gpx"].count("<trkpt") == len(points)


def test_road_guide_budget_is_bounded_and_has_its_own_directions_cache(monkeypatch):
    from gps_art_wizzard.tools import geo

    config = SimpleNamespace(ors_api_key="", ors_base_url="http://ors.internal/ors",
                             snap_radius_m=120, preference="recommended", continue_straight=False)
    monkeypatch.setattr(ors_client, "get_settings", lambda: SimpleNamespace(routing=config))
    monkeypatch.setattr(
        ors_client,
        "active_workflow_runtime",
        lambda: SimpleNamespace(cache_scope="guide-budget-test"),
    )
    calls = []

    def router(url, headers, coordinates, **kwargs):
        calls.append(coordinates)
        points = [(p[1], p[0]) for p in coordinates]
        return points, geo.path_distance_m(points)

    monkeypatch.setattr(ors_client, "_ors_request", router)
    points = [(47 + i * 0.0001, 19 + (i % 2) * (i % 7 + 1) * 0.0001) for i in range(60)]
    ors_client.clear_directions_cache()
    ors_client.snap_route_detailed(points, guide_budget=24)
    ors_client.snap_route_detailed(points, guide_budget=50)
    ors_client.snap_route_detailed(points, guide_budget=50)
    assert len(calls) == 2
    assert len(calls[0]) <= 24
    assert 24 < len(calls[1]) <= 50
    for invalid in (0, 1, 51, True, 24.5):
        with pytest.raises(ValueError, match="guide_budget"):
            ors_client.snap_route_detailed(points, guide_budget=invalid)
    assert len(calls) == 2
