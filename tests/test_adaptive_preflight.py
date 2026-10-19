"""Measured search behaviour, provider degradation, and placement constraints."""
from dataclasses import replace

import pytest

from gps_art_wizzard.agents.placement_agent import PlacementAgent
from gps_art_wizzard.agents.preflight_agent import PreflightAgent
from gps_art_wizzard.config import Settings
from gps_art_wizzard.state import Intent, MapPlacement, Plan, RouteDraft, Shape, WorkflowState
from gps_art_wizzard.tools import ors_client


def search_state():
    shape = Shape("triangle", [[(-0.5, -0.5), (0.5, -0.5), (0, 0.5), (-0.5, -0.5)]], True)
    draft = RouteDraft(47.5, 19.0, 600, 0, 0, 0, 0.8, [], True)
    draft.waypoints = PlacementAgent().project(shape, draft)
    return WorkflowState(
        "triangle", intent=Intent("triangle", None, "Budapest", "run", 3, None),
        shape=shape, route_draft=draft,
        plan=Plan("template", city_bbox=(47.47, 47.53, 18.95, 19.05)),
    )


def test_adaptive_rounds_improve_measured_result_without_exceeding_budget(monkeypatch):
    cfg = Settings()
    monkeypatch.setattr("gps_art_wizzard.agents.preflight_agent.get_settings", lambda: cfg)
    batches = []

    def measure(routes, **kwargs):
        batches.append(routes)
        # A narrow optimum between the coarse grid points.
        results = []
        for i, route in enumerate(routes):
            lat = sum(p[0] for p in route) / len(route)
            score = max(0, 1 - abs(lat - 47.4996) * 200)
            results.append(ors_client.SnapPreflightResult(i, score, 1, 0, score, 1, 1, 1))
        return sorted(results, key=lambda r: -r.score)

    monkeypatch.setattr(ors_client, "preflight_route_candidates", measure)
    state = search_state()
    PreflightAgent().run(state)
    assert len(batches) == 3
    assert sum(map(len, batches)) <= cfg.workflow.preflight_max_placements + cfg.workflow.preflight_creative_placements
    assert state.preflight_count == sum(map(len, batches))
    coarse_best = max(1 - abs(sum(p[0] for p in r) / len(r) - 47.4996) * 200 for r in batches[0])
    assert state.route_draft.preflight_score > coarse_best
    assert len({tuple(route) for batch in batches for route in batch}) == state.preflight_count
    assert all(PreflightAgent._inside_bbox(replace(state.route_draft, waypoints=r), state.plan.city_bbox)
               for batch in batches for r in batch)


def test_failed_fine_batch_retains_coarse_winner(monkeypatch):
    cfg = Settings()
    monkeypatch.setattr("gps_art_wizzard.agents.preflight_agent.get_settings", lambda: cfg)
    calls = []

    def measure(routes, **kwargs):
        calls.append(routes)
        return [ors_client.SnapPreflightResult(0, 0.8, 1, 0, 0.8, 1, 1, 1)] if len(calls) == 1 else None

    monkeypatch.setattr(ors_client, "preflight_route_candidates", measure)
    state = search_state()
    PreflightAgent().run(state)
    assert len(calls) == 2
    assert state.route_draft.preflight_score == 0.8
    assert state.route_draft.waypoints == calls[0][0]


@pytest.mark.parametrize("anchor", [False, True])
def test_fine_search_respects_manual_radius_and_start_direction(anchor):
    state = search_state()
    state.map_placement = MapPlacement(47.5, 19, 600, 0, 100)
    state.route_draft.preferred_start_direction_deg = 15
    if anchor:
        state.route_draft.anchored_start = (47.501, 19.001)
    seed = ors_client.SnapPreflightResult(0, 1, 1, 0, 1, 1, 1, 1)
    drafts = PreflightAgent()._refined_drafts(state, [state.route_draft], [seed], 30, 1)
    assert drafts
    for draft in drafts:
        assert draft.rotation_deg == 0
        assert (draft.lat_offset_m**2 + draft.lon_offset_m**2)**0.5 <= 100
        if anchor:
            assert draft.waypoints[0] == state.route_draft.anchored_start


def test_coarse_sample_covers_scale_and_orientation():
    drafts = PreflightAgent()._candidate_drafts(search_state())
    selected = PreflightAgent._spread_drafts(drafts, 20)
    assert {d.scale_m for d in selected} == {d.scale_m for d in drafts}
    assert len({d.rotation_deg for d in selected}) >= 5


def test_creative_samples_preserve_every_established_search_round(monkeypatch):
    cfg = Settings()
    monkeypatch.setattr("gps_art_wizzard.agents.preflight_agent.get_settings", lambda: cfg)
    monkeypatch.setattr("gps_art_wizzard.tools.street_graph.graph_for_state", lambda state: None)
    batches = []

    def measure(routes, **kwargs):
        batches.append(routes)
        return [ors_client.SnapPreflightResult(i, 1 / (1 + abs(route[0][0] - 47.5)),
                                              1, 0, 0.8, 1, 1, 1)
                for i, route in enumerate(routes)]

    monkeypatch.setattr(ors_client, "preflight_route_candidates", measure)
    cfg.workflow.preflight_creative_placements = 0
    PreflightAgent().run(search_state())
    established = list(batches)
    batches.clear()
    cfg.workflow.preflight_creative_placements = 90
    PreflightAgent().run(search_state())
    assert len(batches) == len(established) == 3
    for before, after in zip(established, batches, strict=True):
        assert after[:len(before)] == before


def test_entire_established_shortlist_survives_better_creative_proxies(monkeypatch):
    cfg = Settings()
    cfg.workflow.preflight_adaptive = False
    monkeypatch.setattr("gps_art_wizzard.agents.preflight_agent.get_settings", lambda: cfg)
    monkeypatch.setattr("gps_art_wizzard.tools.street_graph.graph_for_state", lambda state: None)
    state = search_state()
    agent = PreflightAgent()
    established = agent._candidate_drafts(state, legacy=True)

    def measure(routes, **kwargs):
        return [ors_client.SnapPreflightResult(i, 0.6 if i < len(established) else 0.9,
                                              1, 0, 0.8, 1, 1, 1)
                for i in range(len(routes))]

    monkeypatch.setattr(ors_client, "preflight_route_candidates", measure)
    expected = agent._diverse_shortlist(measure([d.waypoints for d in established]), established,
                                         cfg.workflow.preflight_shortlist, reserve_areas=False)
    agent.run(state)
    shortlisted = [d.waypoints for d in [state.route_draft, *state.placement_candidates]]
    assert all(established[r.candidate_index].waypoints in shortlisted for r in expected)
    assert len(shortlisted) == cfg.workflow.preflight_shortlist + 2


def test_strongest_creative_proxy_is_kept_even_when_near_established_area(monkeypatch):
    cfg = Settings()
    cfg.workflow.preflight_adaptive = False
    cfg.workflow.preflight_shortlist = 3
    monkeypatch.setattr("gps_art_wizzard.agents.preflight_agent.get_settings", lambda: cfg)
    monkeypatch.setattr("gps_art_wizzard.tools.street_graph.graph_for_state", lambda state: None)
    state = search_state()
    projector = PlacementAgent()

    def draft(east):
        result = replace(state.route_draft, lon_offset_m=east)
        result.waypoints = projector.project(state.shape, result)
        return result

    established = [draft(east) for east in (0, 1000, 2000)]
    creative = [draft(east) for east in (20, 3000, -3000)]
    monkeypatch.setattr(PreflightAgent, "_candidate_drafts",
                        lambda self, state, *, legacy=False: established if legacy else creative)

    def measure(routes, **kwargs):
        return [ors_client.SnapPreflightResult(i, score, 1, 0, score, 1, 1, 1)
                for i, score in enumerate((0.8, 0.79, 0.78, 0.99, 0.98, 0.97))]

    monkeypatch.setattr(ors_client, "preflight_route_candidates", measure)
    PreflightAgent().run(state)
    initial = [state.route_draft, *state.placement_candidates[:2]]
    assert creative[0].waypoints in [d.waypoints for d in initial]
    assert all(d.waypoints in [r.waypoints for r in [state.route_draft, *state.placement_candidates]]
               for d in established)


@pytest.mark.parametrize(("far_score", "expected_east"), [(0.97, -3000), (0.3, 10)])
def test_initial_finalists_compare_areas_with_the_established_winner(monkeypatch, far_score, expected_east):
    cfg = Settings()
    cfg.workflow.preflight_adaptive = False
    cfg.workflow.preflight_shortlist = 3
    monkeypatch.setattr("gps_art_wizzard.agents.preflight_agent.get_settings", lambda: cfg)
    monkeypatch.setattr("gps_art_wizzard.tools.street_graph.graph_for_state", lambda state: None)
    state = search_state()

    def draft(east):
        result = replace(state.route_draft, lon_offset_m=east)
        result.waypoints = PlacementAgent().project(state.shape, result)
        return result

    established = [draft(east) for east in (0, 1000, 2000)]
    creative = [draft(east) for east in (3000, 10, -3000)]
    monkeypatch.setattr(PreflightAgent, "_candidate_drafts",
                        lambda self, state, *, legacy=False: established if legacy else creative)

    def measure(routes, **kwargs):
        return [ors_client.SnapPreflightResult(i, score, 1, 0, score, 1, 1, 1)
                for i, score in enumerate((0.8, 0.79, 0.78, 0.99, 0.98, far_score))]

    monkeypatch.setattr(ors_client, "preflight_route_candidates", measure)
    PreflightAgent().run(state)
    finalists = [state.route_draft, *state.placement_candidates]
    assert [d.lon_offset_m for d in finalists[:3]] == [0, 3000, expected_east]
    assert len(finalists) == 5
    assert all(d.waypoints in [r.waypoints for r in finalists] for d in established)
