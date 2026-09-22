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
    assert sum(map(len, batches)) <= cfg.workflow.preflight_max_placements
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
