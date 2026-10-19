"""Spatial variety, concurrent latency, budgets and unchanged routing evidence."""
from __future__ import annotations

import copy
import threading
from dataclasses import replace

import pytest
from pydantic import ValidationError

from gps_art_wizzard.agents.placement_agent import PlacementAgent
from gps_art_wizzard.agents.preflight_agent import PreflightAgent
from gps_art_wizzard.api.routes import GenerateRequest
from gps_art_wizzard.config import get_settings
from gps_art_wizzard.orchestrator import Orchestrator
from gps_art_wizzard.state import (
    Intent,
    MapPlacement,
    Plan,
    RouteDraft,
    Shape,
    SnappedRoute,
    Validation,
    WorkflowState,
)
from gps_art_wizzard.tools import ors_client
from gps_art_wizzard.tools.route_diversity import diverse_route_order
from gps_art_wizzard.workflow_runtime import WorkflowRuntime


def search_state(seed=1):
    shape = Shape("triangle", [[(-0.5, -0.5), (0.5, -0.5), (0, 0.5), (-0.5, -0.5)]], True)
    draft = RouteDraft(47.5, 19, 600, 0, 0, 0, 0.8, [], True, 3)
    draft.waypoints = PlacementAgent().project(shape, draft)
    return WorkflowState("triangle in Budapest", search_seed=seed,
                         intent=Intent("triangle", None, "Budapest", "run", 3, None),
                         shape=shape, route_draft=draft,
                         plan=Plan("template", city_bbox=(47.47, 47.53, 18.95, 19.05)))


def test_seed_reproduces_search_but_new_seed_changes_city_positions():
    agent = PreflightAgent()
    first = agent._candidate_drafts(search_state(123))
    again = agent._candidate_drafts(search_state(123))
    another = agent._candidate_drafts(search_state(456))
    def signatures(drafts):
        return [agent._signature(draft) for draft in drafts]
    assert signatures(first) == signatures(again)
    assert signatures(first) != signatures(another)
    assert len(first) <= get_settings().workflow.preflight_max_placements
    assert len({draft.rotation_deg for draft in first}) == 12
    assert len({draft.scale_m for draft in first}) == 3
    assert len({(draft.lat_offset_m, draft.lon_offset_m) for draft in first}) >= 16
    assert all(agent._inside_bbox(draft, search_state().plan.city_bbox) for draft in first)


@pytest.mark.parametrize("constraint", ["manual", "anchor", "heading"])
def test_varied_search_respects_user_constraints(constraint):
    state = search_state()
    if constraint == "manual":
        state.map_placement = MapPlacement(47.5, 19, 600, 0, 100)
    elif constraint == "anchor":
        state.route_draft.anchored_start = (47.501, 19.001)
    else:
        state.route_draft.preferred_start_direction_deg = 90
    drafts = PreflightAgent()._candidate_drafts(state)
    assert drafts
    if constraint == "heading":
        assert {draft.rotation_deg for draft in drafts} == {0}
    elif constraint == "anchor":
        assert all(draft.waypoints[0] == (47.501, 19.001) for draft in drafts)
    else:
        assert all((draft.lat_offset_m**2 + draft.lon_offset_m**2)**0.5 <= 100.001 for draft in drafts)
        state.search_seed = 999
        assert [draft.waypoints for draft in drafts] == [draft.waypoints for draft in PreflightAgent()._candidate_drafts(state)]


def test_shortlist_reserves_comparable_different_areas_before_local_rotations():
    base = search_state().route_draft
    drafts = [base, replace(base, rotation_deg=90), replace(base, lon_offset_m=1500),
              replace(base, lat_offset_m=-1500)]
    results = [ors_client.SnapPreflightResult(i, score, 1, 0, score, 1, 1, 1)
               for i, score in enumerate((0.95, 0.94, 0.92, 0.91))]
    chosen = PreflightAgent._diverse_shortlist(results, drafts, 3)
    assert [result.candidate_index for result in chosen] == [0, 2, 3]


def test_parallel_initial_search_starts_three_routes_before_any_finishes(monkeypatch):
    cfg = get_settings().workflow
    monkeypatch.setattr(cfg, "measurement_workers", 3)
    monkeypatch.setattr(cfg, "initial_placement_candidates", 3)
    state = search_state()
    state.errors = ["An earlier shape warning must survive."]
    state.placement_candidates = [replace(state.route_draft, lon_offset_m=value) for value in (1000, 2000, 3000)]
    barrier = threading.Barrier(3)

    class Snap:
        def run(self, trial):
            barrier.wait(timeout=3)
            trial.candidate_count += 1
            trial.snapped = SnappedRoute(trial.route_draft.waypoints, 3000, True)

    class Validate:
        def run(self, trial):
            score = 0.8 + trial.route_draft.lon_offset_m / 20_000
            trial.validation = Validation(score, 1, 1, score, on_roads=True)
            trial.history.append({"measured_area": trial.route_draft.lon_offset_m})

    runtime = WorkflowRuntime(state, max_duration_seconds=175, max_llm_calls=0)
    extra = Orchestrator({})._measure_initial_placements(state, {"snap": Snap(), "validation": Validate()}, runtime)
    assert extra == 2  # Counts against serial placement refinements, avoiding duplicate work.
    assert state.candidate_count == 3
    assert state.route_draft.lon_offset_m == 2000
    assert [draft.lon_offset_m for draft in state.placement_candidates] == [3000]
    assert state.errors == ["An earlier shape warning must survive."]
    assert len([row for row in state.history if "measured_area" in row]) == 3


def test_soft_search_budget_stops_new_optimisation_but_keeps_mandatory_steps():
    elapsed = [0.0]
    state = search_state()
    runtime = WorkflowRuntime(state, max_duration_seconds=175, max_llm_calls=1,
                              optimization_budget_seconds=35, clock=lambda: elapsed[0])
    elapsed[0] = 36
    assert runtime.deadline_exceeded()
    assert runtime.llm_budget_status() == (True, None)
    assert runtime.run_step("validation", lambda: "measured") == "measured"
    assert runtime.run_step("export", lambda: "still gated by ExportAgent") == "still gated by ExportAgent"
    assert runtime.trace.max_duration_seconds == 175
    assert "optimization_budget_exhausted" in runtime.trace.degraded_reasons


def test_expired_budget_does_not_start_queued_alternatives(monkeypatch):
    monkeypatch.setattr(get_settings().workflow, "measurement_workers", 1)
    state = search_state()
    state.placement_candidates = [replace(state.route_draft, lon_offset_m=value) for value in (1000, 2000, 3000)]
    elapsed = [0.0]
    calls = []

    class Snap:
        def run(self, trial):
            calls.append(trial.route_draft.lon_offset_m)
            elapsed[0] = 36
            trial.candidate_count += 1
            trial.snapped = SnappedRoute(trial.route_draft.waypoints, 3000, True)

    class Validate:
        def run(self, trial):
            trial.validation = Validation(0.8, 1, 1, 0.8)

    runtime = WorkflowRuntime(state, max_duration_seconds=175, max_llm_calls=0,
                              optimization_budget_seconds=35, clock=lambda: elapsed[0])
    Orchestrator({})._measure_initial_placements(state, {"snap": Snap(), "validation": Validate()}, runtime)
    assert calls == [0]
    assert state.candidate_count == 1
    assert state.validation.on_roads
    assert [draft.lon_offset_m for draft in state.placement_candidates] == [1000, 2000, 3000]


@pytest.mark.parametrize(("elapsed_seconds", "expected_batches"), [(36, 3), (175, 1)])
def test_adaptive_accuracy_search_uses_the_original_full_budget(monkeypatch, elapsed_seconds, expected_batches):
    state = search_state()
    elapsed = [0.0]
    runtime = WorkflowRuntime(state, max_duration_seconds=175, max_llm_calls=0,
                              optimization_budget_seconds=35, clock=lambda: elapsed[0])
    calls = []

    def measure(routes, **kwargs):
        calls.append(len(routes))
        elapsed[0] = elapsed_seconds
        return [ors_client.SnapPreflightResult(0, 0.9, 1, 0, 0.9, 1, 1, 1)]

    monkeypatch.setattr(ors_client, "preflight_route_candidates", measure)
    with runtime.activate():
        PreflightAgent().run(state)
    assert len(calls) == expected_batches
    assert state.route_draft.preflight_score == 0.9


def test_unconnected_route_can_still_recover_after_the_short_exploration_budget(monkeypatch):
    monkeypatch.setattr(get_settings().workflow, "measurement_workers", 1)
    state = search_state()
    state.snapped = SnappedRoute(state.route_draft.waypoints, 3000, False)
    state.validation = Validation(0.3, 1, 1, 0.3, on_roads=False)
    state.placement_candidates = [replace(state.route_draft, lon_offset_m=value) for value in (1000, 2000)]
    elapsed = [0.0]
    calls = []

    class Snap:
        def run(self, trial):
            calls.append(trial.route_draft.lon_offset_m)
            trial.candidate_count += 1
            trial.snapped = SnappedRoute(trial.route_draft.waypoints, 3000, True)

    class Validate:
        def run(self, trial):
            trial.validation = Validation(0.9, 1, 1, 0.9, on_roads=True)

    runtime = WorkflowRuntime(state, max_duration_seconds=175, max_llm_calls=0,
                              optimization_budget_seconds=35, clock=lambda: elapsed[0])
    elapsed[0] = 40
    Orchestrator({})._recover_unroutable_placement(state, {"snap": Snap(), "validation": Validate()}, runtime)
    assert calls == [1000, 2000]
    assert state.snapped.snapped
    assert state.route_draft.lon_offset_m == 1000


def test_live_progress_counts_real_areas_and_unique_connected_candidates():
    state = search_state()
    events = []
    runtime = WorkflowRuntime(state, max_duration_seconds=175, max_llm_calls=0, event_sink=events.append)
    state.preflight_count = 90
    state.search_areas = 16
    runtime.publish_search_progress()
    assert events[-1]["search_areas"] == 16
    assert events[-1]["preflight_count"] == 90
    state.validation = Validation(0.8, 1, 1, 0.8, on_roads=True)
    state.snapped = SnappedRoute(state.route_draft.waypoints, 3000, False)
    runtime.publish_preview(state)
    runtime.publish_search_progress()
    assert events[-1]["connected_candidates"] == 0
    state.snapped.snapped = True
    runtime.publish_preview(state)
    runtime.publish_preview(state)
    runtime.publish_search_progress()
    assert events[-1]["connected_candidates"] == 1
    assert "gpx" not in events[-1]


def route_candidate(name, points, score=0.9, passed=True):
    return {"id": name, "points_preview": points, "validation": {"shape_fidelity": score},
            "verification": {"passed": passed}, "gpx": f"{name}-unchanged"}


def test_cards_show_distinct_area_before_near_duplicate_and_retain_every_route():
    points = [(47.5, 19), (47.51, 19), (47.51, 19.01)]
    candidates = [route_candidate("best", points, 0.95),
                  route_candidate("near", [(lat + 0.0001, lon) for lat, lon in points], 0.94),
                  route_candidate("far", [(lat + 0.04, lon) for lat, lon in points], 0.90),
                  route_candidate("review", [(lat - 0.04, lon) for lat, lon in points], 0.60, False)]
    before = copy.deepcopy(candidates)
    ordered = diverse_route_order(candidates)
    assert ordered[0]["id"] == "best"
    assert ordered[1]["id"] == "far"
    assert ordered[2]["id"] == "near"
    assert ordered[3]["id"] == "review"
    assert candidates == before
    assert {id(candidate) for candidate in candidates} == {id(candidate) for candidate in ordered}


@pytest.mark.parametrize("seed", [-1, 2**32, True, "12", 1.5])
def test_api_rejects_invalid_search_seed(seed):
    with pytest.raises(ValidationError):
        GenerateRequest(prompt="heart in Budapest", search_seed=seed)


def test_api_accepts_reproducible_seed_zero():
    assert GenerateRequest(prompt="heart in Budapest", search_seed=0).search_seed == 0


def test_zero_seed_explores_the_same_number_of_city_sectors_as_other_seeds():
    agent = PreflightAgent()
    for seed in (0, 1, 123):
        drafts = agent._candidate_drafts(search_state(seed))
        assert len({(d.lat_offset_m, d.lon_offset_m) for d in drafts}) >= 16


def test_quality_repairs_retain_the_full_budget_after_exploration_stops():
    elapsed = [0.0]
    runtime = WorkflowRuntime(search_state(), max_duration_seconds=175, max_llm_calls=0,
                              optimization_budget_seconds=35, clock=lambda: elapsed[0])
    elapsed[0] = 36
    assert runtime.deadline_exceeded()
    assert not runtime.deadline_exceeded(quality_required=True)
    elapsed[0] = 175
    assert runtime.deadline_exceeded(quality_required=True)


def test_api_forwards_explicit_zero_seed_to_the_workflow(monkeypatch):
    from gps_art_wizzard.api import routes

    captured = {}

    def generate(prompt, **options):
        captured.update(options)
        state = search_state(options["search_seed"])
        state.snapped = SnappedRoute(state.route_draft.waypoints, 3000, True)
        return state

    monkeypatch.setattr(routes, "generate", generate)
    monkeypatch.setattr(routes, "_state_to_response", lambda state: {"search_seed": state.search_seed})
    assert routes._generate_route_sync(GenerateRequest(prompt="triangle in Budapest", search_seed=0)) == {"search_seed": 0}
    assert captured["search_seed"] == 0


def test_budget_limited_benchmark_is_marked_incomplete_and_keeps_the_seed():
    from gps_art_wizzard.generation_benchmark import benchmark_cases, result_record

    state = search_state(123)
    runtime = WorkflowRuntime(state, max_duration_seconds=175, max_llm_calls=0)
    runtime.trace.degraded_reasons.append("optimization_budget_exhausted")
    record = result_record(benchmark_cases()[0], state, 36)
    assert not record["search_complete"]
    assert "optimization_budget_exhausted" in record["search_incomplete_reasons"]
    assert record["search_seed"] == 123


def test_paired_benchmark_variants_reuse_the_same_sampling_seed():
    from gps_art_wizzard.generation_benchmark import benchmark_cases, run_cases

    captured = []

    def run(prompt, **options):
        captured.append(options["search_seed"])
        return search_state(options["search_seed"])

    cases = benchmark_cases()[:2]
    run_cases(cases, variant="baseline", runner=run)
    run_cases(cases, variant="adaptive", runner=run)
    assert captured[:2] == captured[2:]
    assert captured[0] != captured[1]
