"""Tests for the generation performance mechanisms.

Covers the concurrent candidate measurements, the ORS Directions memo cache,
the similarity-diagnostics memo, and the vectorised geometry math those paths
depend on. Every test here must preserve the invariant that drove the work:
identical inputs produce identical selected routes and scores regardless of
worker count.
"""

from __future__ import annotations

import math
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from gps_art_wizzard.config import get_settings
from gps_art_wizzard.orchestrator import Orchestrator
from gps_art_wizzard.state import (
    Intent,
    Plan,
    RouteDraft,
    Shape,
    SnappedRoute,
    Validation,
    WorkflowState,
)
from gps_art_wizzard.tools import ors_client
from gps_art_wizzard.tools import shape_similarity as ss
from gps_art_wizzard.workflow_runtime import WorkflowRuntime

# --------------------------------------------------------------------------- #
# Vectorised geometry math                                                    #
# --------------------------------------------------------------------------- #


def _frechet_scalar_reference(p: np.ndarray, q: np.ndarray) -> float:
    """The pre-optimisation scalar DP, kept here as the parity oracle."""
    n, m = len(p), len(q)
    if n == 0 or m == 0:
        return float("inf")
    distances = np.linalg.norm(q - p[0], axis=1)
    previous = np.empty(m)
    previous[0] = distances[0]
    for j in range(1, m):
        previous[j] = max(previous[j - 1], distances[j])
    for i in range(1, n):
        distances = np.linalg.norm(q - p[i], axis=1)
        current = np.empty(m)
        current[0] = max(previous[0], distances[0])
        for j in range(1, m):
            current[j] = max(
                min(previous[j], previous[j - 1], current[j - 1]),
                distances[j],
            )
        previous = current
    return float(previous[-1])


@pytest.mark.parametrize("n,m", [(1, 1), (1, 7), (7, 1), (2, 2), (5, 13), (33, 64)])
def test_discrete_frechet_matches_the_scalar_reference_exactly(n: int, m: int):
    rng = np.random.default_rng(n * 100 + m)
    p = rng.normal(size=(n, 2))
    q = rng.normal(size=(m, 2))

    assert ss.discrete_frechet(p, q) == _frechet_scalar_reference(p, q)


def test_discrete_frechet_handles_empty_and_degenerate_inputs():
    point = np.array([[0.0, 0.0]])
    empty = np.zeros((0, 2))
    assert ss.discrete_frechet(point, empty) == float("inf")
    assert ss.discrete_frechet(empty, point) == float("inf")
    # A single-point candidate collapses to the maximum point distance.
    two = np.array([[0.0, 0.0], [3.0, 4.0]])
    assert ss.discrete_frechet(two, point) == pytest.approx(5.0)


def test_signed_turns_matches_a_scalar_reference_for_open_and_closed_paths():
    def reference(points: np.ndarray, span: int) -> np.ndarray:
        count = len(points)
        turns = np.zeros(count)
        closed = count >= 3 and bool(
            np.linalg.norm(points[0] - points[-1]) <= 0.05
        )
        core_count = count - 1 if closed else count
        if core_count < 2 * span + 1:
            return turns
        indices = range(core_count) if closed else range(span, core_count - span)
        for index in indices:
            prev_i = (index - span) % core_count if closed else index - span
            next_i = (index + span) % core_count if closed else index + span
            incoming = points[index] - points[prev_i]
            outgoing = points[next_i] - points[index]
            if (
                float(np.linalg.norm(incoming)) <= 1e-9
                or float(np.linalg.norm(outgoing)) <= 1e-9
            ):
                continue
            cross = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
            dot = float(np.dot(incoming, outgoing))
            turns[index] = math.atan2(cross, dot)
        if closed:
            turns[-1] = turns[0]
        return turns

    rng = np.random.default_rng(11)
    open_path = np.cumsum(rng.normal(size=(40, 2)) * 0.1, axis=0)
    ring = np.vstack([open_path[:32], open_path[0]])
    duplicated = ring.copy()
    duplicated[5] = duplicated[4]  # zero-length chord must stay zero

    for points in (open_path, ring, duplicated):
        for span in (2, 3, 8):
            # The vectorised dot product can differ from the scalar reference
            # by one floating-point rounding step across NumPy/Python builds.
            # The algorithmic contract is numerical equivalence, not identical
            # machine-bit evaluation order.
            np.testing.assert_allclose(
                ss._signed_turns(points, span),
                reference(points, span),
                rtol=1e-12,
                atol=1e-15,
            )


# --------------------------------------------------------------------------- #
# ORS Directions memo cache                                                   #
# --------------------------------------------------------------------------- #


@pytest.fixture
def routing_stub(monkeypatch):
    """Private ORS endpoint with a key so the real request path executes."""
    routing = SimpleNamespace(
        ors_api_key="test-key",
        ors_base_url="http://ors.internal/ors",
        snap_radius_m=120,
        preference="recommended",
        continue_straight=False,
    )
    monkeypatch.setattr(
        ors_client, "get_settings", lambda: SimpleNamespace(routing=routing)
    )
    return routing


class RequestCounter:
    def __init__(self):
        self.calls: list[list[list[float]]] = []

    def responder(self, polyline):
        def fake_request(_url, _headers, coords, **_kwargs):
            self.calls.append(coords)
            return list(polyline), 1_000.0

        return fake_request


def test_directions_memo_serves_identical_requests_from_cache(routing_stub, monkeypatch):
    counter = RequestCounter()
    waypoints = [(47.5, 19.0), (47.51, 19.01)]
    monkeypatch.setattr(
        ors_client, "_ors_request", counter.responder([(47.5, 19.0), (47.51, 19.005)])
    )

    first = ors_client.snap_route_detailed(waypoints)
    second = ors_client.snap_route_detailed(list(waypoints))

    assert len(counter.calls) == 1  # only one network round trip
    assert first == second
    assert first[0] is not second[0]  # callers never share mutable geometry
    assert first[2] is True


def test_directions_memo_distinguishes_every_request_input(routing_stub, monkeypatch):
    counter = RequestCounter()
    straight = [(47.5, 19.0), (47.51, 19.01)]
    monkeypatch.setattr(
        ors_client, "_ors_request", counter.responder([(47.5, 19.0), (47.51, 19.01)])
    )

    ors_client.snap_route_detailed(straight)
    ors_client.snap_route_detailed([(47.5, 19.0), (47.52, 19.02)])  # other geometry
    ors_client.snap_route_detailed(straight, sport="bike")  # other profile
    ors_client.snap_route_detailed(straight, route_preferences=None)  # same as before
    ors_client.snap_route_detailed(straight, start_direction_deg=90.0)  # other bearing

    assert len(counter.calls) == 4  # geometry, profile, and bearing all change the key


def test_directions_memo_reuses_equivalent_wrapped_headings(routing_stub, monkeypatch):
    counter = RequestCounter()
    straight = [(47.5, 19.0), (47.51, 19.01)]
    monkeypatch.setattr(
        ors_client, "_ors_request", counter.responder([(47.5, 19.0), (47.51, 19.01)])
    )

    ors_client.snap_route_detailed(straight, start_direction_deg=90.0)
    ors_client.snap_route_detailed(straight, start_direction_deg=450.0)

    assert len(counter.calls) == 1


def test_directions_memo_never_caches_failures(routing_stub, monkeypatch):
    attempts = {"count": 0}

    def flaky(_url, _headers, coords, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return None  # network-style failure -> status None -> no retry loop exit
        return [(47.5, 19.0), (47.51, 19.01)], 900.0

    monkeypatch.setattr(ors_client, "_ors_request", flaky)
    waypoints = [(47.5, 19.0), (47.51, 19.01)]

    failed = ors_client.snap_route_detailed(waypoints)
    recovered = ors_client.snap_route_detailed(waypoints)

    assert failed[2] is False  # straight-line fallback
    assert recovered[2] is True
    assert attempts["count"] >= 2  # the failure was not memoised


def test_directions_cache_honours_ttl_and_manual_clear(routing_stub, monkeypatch):
    counter = RequestCounter()
    monkeypatch.setattr(
        ors_client, "_ors_request", counter.responder([(47.5, 19.0), (47.51, 19.01)])
    )
    waypoints = [(47.5, 19.0), (47.51, 19.01)]

    ors_client.snap_route_detailed(waypoints)
    monkeypatch.setattr(ors_client, "_DIRECTIONS_CACHE_TTL_S", -1.0)
    ors_client.snap_route_detailed(waypoints)
    assert len(counter.calls) == 2  # expired entries refetch

    ors_client.clear_directions_cache()
    ors_client.snap_route_detailed(waypoints)
    assert len(counter.calls) == 3


def test_directions_cache_evicts_least_recently_used_entries(routing_stub):
    routes = [
        [(47.40 + index * 0.01, 19.40), (47.41 + index * 0.01, 19.41)]
        for index in range(4)
    ]
    keys = [
        ors_client._directions_cache_key(  # noqa: SLF001
            route,
            profile="foot-walking",
            closed=True,
            start_radius=120,
            route_preferences=None,
        )
        for route in routes
    ]
    monkeypatch_max = 2
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(ors_client, "_DIRECTIONS_CACHE_MAX", monkeypatch_max)
        for index, key in enumerate(keys):
            ors_client._directions_cache_put(key, routes[index], 100.0, True, None)  # noqa: SLF001
        cached_keys = set(ors_client._directions_cache)
    assert cached_keys == set(keys[-monkeypatch_max:])


# --------------------------------------------------------------------------- #
# Similarity diagnostics memo                                                 #
# --------------------------------------------------------------------------- #


def _demo_routes():
    t = np.linspace(0.0, 2.0 * math.pi, 60)
    reference = [
        (47.480 + 0.004 * math.cos(x), 19.030 + 0.003 * math.sin(2 * x)) for x in t
    ]
    snapped = [(lat + 0.00015, lon - 0.00012) for lat, lon in reference]
    return reference, snapped


def test_similarity_diagnostics_reuses_one_result_object_for_equal_inputs():
    reference, snapped = _demo_routes()

    first = ss.similarity_diagnostics_between_routes(reference, snapped)
    second = ss.similarity_diagnostics_between_routes(list(reference), list(snapped))

    assert first is second  # frozen dataclass shared from the LRU
    assert first.fidelity > 0.9

    ss._similarity_diagnostics_cached.cache_clear()  # noqa: SLF001
    third = ss.similarity_diagnostics_between_routes(reference, snapped)
    assert third is not second
    assert third == second  # recomputation stays deterministic


def test_similarity_diagnostics_treats_sample_settings_as_part_of_the_key():
    reference, snapped = _demo_routes()
    coarse = ss.similarity_diagnostics_between_routes(
        reference, snapped, n=64, closed_sample_floor=64
    )
    fine = ss.similarity_diagnostics_between_routes(reference, snapped, n=128)
    dense = ss.similarity_diagnostics_between_routes(
        reference, snapped, n=64, closed_sample_floor=256
    )
    assert coarse is not fine
    assert coarse is not dense  # the closed-loop floor changes the computation


def test_similarity_diagnostics_falls_back_for_unhashable_rows():
    reference, snapped = _demo_routes()
    expected = ss.similarity_diagnostics_between_routes(reference, snapped)
    as_lists = [[lat, lon] for lat, lon in reference], [
        [lat, lon] for lat, lon in snapped
    ]

    actual = ss.similarity_diagnostics_between_routes(*as_lists)

    assert actual == expected


# --------------------------------------------------------------------------- #
# Concurrent candidate measurement                                            #
# --------------------------------------------------------------------------- #


def _draft(rotation: float) -> RouteDraft:
    return RouteDraft(
        47.5,
        19.0,
        700.0,
        rotation,
        0.0,
        0.0,
        0.8,
        [(47.5, 19.0), (47.501, 19.001)],
        False,
        8.0,
        preflight_score=0.9 - rotation / 1_000.0,
    )


def _unroutable_state(candidates: list[RouteDraft]) -> WorkflowState:
    points = [(47.5, 19.0), (47.501, 19.001)]
    return WorkflowState(
        prompt="heart in Budapest",
        route_draft=_draft(0.0),
        placement_candidates=candidates,
        snapped=SnappedRoute(points, 100.0, snapped=False),
        validation=Validation(0.4, 1.0, 0.3, 0.3, on_roads=False),
        errors=["snap: primary failed"],
    )


class ScriptedSnap:
    """Snap node whose per-rotation behaviour and pacing are scripted."""

    def __init__(self, script: dict[float, dict]):
        self.script = script
        self.started: dict[float, threading.Event] = {
            rotation: threading.Event() for rotation in script
        }

    def run(self, state: WorkflowState) -> WorkflowState:
        rotation = state.route_draft.rotation_deg
        self.started[rotation].set()
        step = self.script[rotation]
        if "wait_for" in step:
            step["wait_for"].wait(timeout=10)
        connected = step.get("connected", False)
        if step.get("raise"):
            raise ValueError("scripted draft failure")
        state.errors = [e for e in state.errors if not e.startswith("snap:")]
        state.snapped = SnappedRoute(state.route_draft.waypoints, 8_000.0, snapped=connected)
        return state


class ConnectedValidation:
    def run(self, state: WorkflowState) -> WorkflowState:
        routed = state.snapped.snapped
        state.validation = Validation(
            0.84 if routed else 0.4,
            1.0,
            0.94 if routed else 0.3,
            0.82 if routed else 0.3,
            on_roads=routed,
        )
        return state


@pytest.fixture
def three_workers(monkeypatch):
    workflow = get_settings().workflow
    monkeypatch.setattr(workflow, "measurement_workers", 3)


@pytest.mark.parametrize(
    ("configured", "job_count", "expected"),
    [
        (0, 4, 1),
        (-3, 4, 1),
        ("not-a-number", 4, 1),
        (99, 8, 6),  # hard cap for API-rate-limit safety
        (99, 2, 2),  # never more workers than jobs
        (3, 5, 3),
        (4, 1, 1),
    ],
)
def test_measurement_worker_count_is_clamped(monkeypatch, configured, job_count, expected):
    workflow = get_settings().workflow
    monkeypatch.setattr(workflow, "measurement_workers", configured)
    assert Orchestrator(nodes={})._measurement_worker_count(job_count) == expected


def test_recovery_prefers_priority_order_over_completion_order(three_workers):
    """A slow top-ranked placement must beat a fast lower-ranked one."""

    class BranchingSnap:
        """Both placements connect; priority 1 deliberately completes last."""

        def __init__(self):
            self.fast_done = threading.Event()

        def run(self, state: WorkflowState) -> WorkflowState:
            rotation = state.route_draft.rotation_deg
            if rotation == 30.0:
                # Priority-1 candidate returns only after #2 has finished.
                self.fast_done.wait(timeout=10)
            else:
                self.fast_done.set()
            state.errors = [e for e in state.errors if not e.startswith("snap:")]
            state.snapped = SnappedRoute(
                state.route_draft.waypoints, 8_000.0, snapped=True
            )
            return state

    snap = BranchingSnap()
    state = _unroutable_state([_draft(30.0), _draft(90.0)])

    Orchestrator(nodes={})._recover_unroutable_placement(
        state,
        {"snap": snap, "validation": ConnectedValidation()},
    )
    assert snap.fast_done.is_set()  # the pair genuinely overlapped

    assert state.route_draft.rotation_deg == 30.0  # priority beat completion order
    assert state.snapped.snapped is True
    assert [entry["attempt"] for entry in state.history] == [1, 2]


def test_recovery_keeps_placements_ranked_behind_the_winner(three_workers):
    snap = ScriptedSnap({30.0: {}, 60.0: {"connected": True}, 90.0: {"connected": True}})
    state = _unroutable_state([_draft(30.0), _draft(60.0), _draft(90.0)])

    Orchestrator(nodes={})._recover_unroutable_placement(
        state,
        {"snap": snap, "validation": ConnectedValidation()},
    )

    assert state.route_draft.rotation_deg == 60.0
    # The placement ranked behind the winner survives for refinement.
    assert [draft.rotation_deg for draft in state.placement_candidates] == [90.0]


def test_recovery_leaves_no_candidates_when_every_alternative_fails():
    snap = ScriptedSnap({30.0: {}, 60.0: {}})
    state = _unroutable_state([_draft(30.0), _draft(60.0)])

    Orchestrator(nodes={})._recover_unroutable_placement(
        state,
        {"snap": snap, "validation": ConnectedValidation()},
    )

    assert state.route_draft.rotation_deg == 0.0
    assert state.snapped.snapped is False
    assert state.placement_candidates == []
    assert [entry["attempt"] for entry in state.history] == [1, 2]
    assert all(entry["on_roads"] is False for entry in state.history)
    assert state.errors == ["snap: primary failed"]


def test_recovery_records_scripted_failures_and_uses_the_next_placement():
    snap = ScriptedSnap({30.0: {"raise": True}, 90.0: {"connected": True}})
    state = _unroutable_state([_draft(30.0), _draft(90.0)])

    Orchestrator(nodes={})._recover_unroutable_placement(
        state,
        {"snap": snap, "validation": ConnectedValidation()},
    )

    assert state.route_draft.rotation_deg == 90.0
    assert state.history[0]["error_type"] == "ValueError"
    assert state.history[0]["attempt"] == 1
    assert state.history[1]["on_roads"] is True
    assert state.errors == []  # winner's snap cleared the stale primary error


def test_recoverable_candidate_failure_does_not_finalise_the_workflow(three_workers):
    state = _unroutable_state([_draft(30.0)])
    runtime = WorkflowRuntime(state, max_duration_seconds=600, max_llm_calls=8)
    nodes = runtime.instrument_nodes(
        {
            "snap": ScriptedSnap({30.0: {"raise": True}}),
            "validation": ConnectedValidation(),
        }
    )

    Orchestrator(nodes={})._recover_unroutable_placement(state, nodes)

    assert state.workflow.status.value == "running"
    assert state.workflow.step_failures == 1
    runtime.finish(state)
    assert state.workflow.status.value == "completed"


def _suggestion_state(validation_score: float) -> tuple[WorkflowState, Plan]:
    points = [(47.0, 19.0), (47.01, 19.01)]
    plan = Plan(
        shape_strategy="template",
        suggested_shape="crown",
        suggestion_candidates=["crown", "triangle", "diamond"],
        suggestion_reasons={
            "crown": "Crown reason.",
            "triangle": "Triangle reason.",
            "diamond": "Diamond reason.",
        },
        notes="Crown reason.",
    )
    state = WorkflowState(
        prompt="suggest a run",
        intent=Intent("crown", None, "Eger", "run", 10.0, None),
        plan=plan,
        shape=Shape("crown", [], True),
        route_draft=RouteDraft(
            47.0, 19.0, 1_000.0, 0.0, 0.0, 0.0, 0.8, points, True, 10.0
        ),
        snapped=SnappedRoute(points, 10_000.0, snapped=True),
        validation=Validation(
            validation_score,
            1.0,
            0.9,
            validation_score - 0.05,
            on_roads=True,
            spatial_similarity=validation_score - 0.05,
            coverage_similarity=validation_score - 0.05,
            turning_similarity=validation_score - 0.05,
            landmark_similarity=validation_score - 0.05,
            length_similarity=validation_score - 0.05,
            extent_similarity=validation_score - 0.05,
        ),
    )
    return state, plan


class MustNotRun:
    def run(self, _state):  # pragma: no cover - assertion guard
        pytest.fail("deadline-gated search must not measure any candidate")


def _blown_deadline_runtime(state: WorkflowState) -> WorkflowRuntime:
    clock_values = {"now": 0.0}

    def clock() -> float:
        return clock_values["now"]

    runtime = WorkflowRuntime(
        state,
        max_duration_seconds=5,
        max_llm_calls=8,
        clock=clock,
    )
    clock_values["now"] = 60.0  # far past the deadline
    return runtime


def test_suggestion_search_skips_measurement_after_the_workflow_deadline():
    state, _plan = _suggestion_state(validation_score=0.44)

    Orchestrator(nodes={})._evaluate_suggestion_candidates(
        state,
        {"shape": MustNotRun(), "placement": MustNotRun(), "snap": MustNotRun(),
         "validation": MustNotRun()},
        runtime=_blown_deadline_runtime(state),
    )

    assert state.shape.name == "crown"  # primary retained untouched
    assert state.history == []
    assert state.candidates == []


def test_fallback_search_skips_measurement_after_the_workflow_deadline():
    points = [(47.0, 19.0), (47.01, 19.01)]
    plan = Plan(
        shape_strategy="template",
        fallback_candidates=["triangle", "diamond"],
    )
    state = WorkflowState(
        prompt="a unicorn run",
        requested_shape="cat",  # requested != selected -> substitution search engages
        intent=Intent("unicorn", None, "Tatabánya", "run", 10.0, None),
        plan=plan,
        shape=Shape("unicorn", [], True),
        route_draft=RouteDraft(
            47.0, 19.0, 1_000.0, 0.0, 0.0, 0.0, 0.8, points, True, 10.0
        ),
        snapped=SnappedRoute(points, 10_000.0, snapped=True),
        validation=Validation(
            0.48,
            1.0,
            0.9,
            0.42,
            on_roads=True,
            coverage_similarity=0.45,
            turning_similarity=0.40,
            length_similarity=0.50,
            extent_similarity=0.60,
            route_length_ratio=1.4,
        ),
    )

    Orchestrator(nodes={})._evaluate_fallback_candidates(
        state,
        {"shape": MustNotRun(), "placement": MustNotRun(), "preflight": MustNotRun(),
         "snap": MustNotRun(), "validation": MustNotRun()},
        runtime=_blown_deadline_runtime(state),
    )

    assert state.shape.name == "unicorn"  # requested shape retained for review
    assert state.fit_decision.substituted is False
    assert state.fit_decision.candidates_tested == []


def test_suggestion_search_selects_the_strongest_template_through_the_pool(
    three_workers,
):
    state, plan = _suggestion_state(validation_score=0.44)
    points = [(47.0, 19.0), (47.01, 19.01)]
    fidelity_by_shape = {"triangle": 0.58, "diamond": 0.76}
    measured: list[str] = []
    lock = threading.Lock()

    def shape_node(current: WorkflowState) -> None:
        name = current.intent.shape
        with lock:
            measured.append(name)
        current.shape = Shape(name, [], True)

    def placement_node(current: WorkflowState) -> None:
        current.route_draft = RouteDraft(
            47.0, 19.0, 1_000.0, 0.0, 0.0, 0.0, 0.8, list(points), True, 10.0
        )

    def snap_node(current: WorkflowState) -> None:
        current.snapped = SnappedRoute(points, 10_000.0, snapped=True)
        current.errors = []

    def validation_node(current: WorkflowState) -> None:
        fidelity = fidelity_by_shape[current.shape.name]
        current.validation = Validation(
            0.8 if fidelity >= 0.7 else 0.6,
            1.0,
            0.9,
            fidelity,
            on_roads=True,
            spatial_similarity=fidelity,
            coverage_similarity=fidelity,
            turning_similarity=fidelity,
            landmark_similarity=fidelity,
            length_similarity=fidelity,
            extent_similarity=fidelity,
        )

    class Node:
        def __init__(self, operation):
            self.operation = operation

        def run(self, current):
            self.operation(current)
            return current

    Orchestrator(nodes={})._evaluate_suggestion_candidates(
        state,
        {
            "shape": Node(shape_node),
            "placement": Node(placement_node),
            "snap": Node(snap_node),
            "validation": Node(validation_node),
        },
    )

    assert sorted(measured) == ["diamond", "triangle"]  # both alternatives ran
    assert state.shape.name == "diamond"
    assert state.intent.shape == "diamond"
    assert plan.suggested_shape == "diamond"
    assert plan.notes == "Diamond reason."
    assert state.validation.shape_fidelity == pytest.approx(0.76)
    assert {entry["shape"] for entry in state.history} == {"triangle", "diamond"}


# --------------------------------------------------------------------------- #
# WorkflowRuntime deadline + thread safety                                    #
# --------------------------------------------------------------------------- #


def test_runtime_deadline_flag_flips_at_the_exact_budget_boundary():
    state = WorkflowState(prompt="boundary")
    clock_values = {"now": 0.0}
    runtime = WorkflowRuntime(
        state,
        max_duration_seconds=10,
        max_llm_calls=8,
        clock=lambda: clock_values["now"],
    )

    clock_values["now"] = 9.99
    assert runtime.deadline_exceeded() is False
    clock_values["now"] = 10.0
    assert runtime.deadline_exceeded() is True


def test_runtime_counters_stay_consistent_under_concurrent_steps():
    state = WorkflowState(prompt="concurrency smoke")
    runtime = WorkflowRuntime(state, max_duration_seconds=600, max_llm_calls=500)
    stages = ["snap", "validation", "refinement"]
    threads_ready = threading.Barrier(9)

    def worker(index: int) -> None:
        threads_ready.wait()
        stage = stages[index % len(stages)]
        runtime.run_step(stage, lambda: None)
        runtime.record_llm_attempt("opencode")
        runtime.record_llm_success({"prompt_tokens": 3})

    workers = [threading.Thread(target=worker, args=(i,)) for i in range(9)]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join()

    trace = runtime.trace
    assert sum(trace.step_attempts.values()) == 9
    for stage in stages:
        assert trace.step_attempts[stage] == 3
    assert trace.llm_attempts == 9
    assert trace.llm_successes == 9
    assert trace.llm_usage["prompt_tokens"] == 27
    sequences = [event.sequence for event in trace.events]
    assert len(set(sequences)) == len(sequences) == 18  # RUNNING+COMPLETED per step
