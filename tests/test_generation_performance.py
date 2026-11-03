"""Optimisations must preserve metric values, evidence, and resource lifetime."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from gps_art_wizzard.orchestrator import Orchestrator
from gps_art_wizzard.state import WorkflowState
from gps_art_wizzard.tools import ors_client, shape_similarity
from gps_art_wizzard.workflow_runtime import WorkflowRuntime


@pytest.mark.parametrize("changed_input", ["coordinates", "bearing"])
def test_directions_memoisation_never_merges_distinct_provider_inputs(monkeypatch, changed_input):
    cfg = ors_client.get_settings().routing
    monkeypatch.setattr(cfg, "ors_api_key", "test-no-network")
    calls = []

    def request(_url, _headers, coords, **kwargs):
        calls.append((coords, kwargs["start_direction_deg"]))
        return [(lat, lon) for lon, lat in coords], 150

    monkeypatch.setattr(ors_client, "_ors_request", request)
    runtime = WorkflowRuntime(WorkflowState("heart"), max_duration_seconds=175, max_llm_calls=0)
    first = [(47.5, 19), (47.501, 19.001)]
    second = [(47.50000001, 19), first[1]] if changed_input == "coordinates" else first
    second_bearing = 10.0001 if changed_input == "bearing" else 10
    ors_client.clear_directions_cache()
    try:
        with runtime.activate():
            ors_client.snap_route_detailed(first, start_direction_deg=10)
            expected = ors_client.snap_route_detailed(second, start_direction_deg=second_bearing)
            cached = ors_client.snap_route_detailed(second, start_direction_deg=second_bearing)
        assert len(calls) == 2
        assert expected == cached
    finally:
        runtime.close_routing_client()
        ors_client.clear_directions_cache()


@pytest.mark.parametrize(("n", "m"), [(1, 1), (1, 5), (5, 1), (3, 5), (64, 64), (96, 72), (256, 256)])
def test_batched_frechet_is_bit_identical_to_independent_dynamic_programs(n, m):
    rng = np.random.default_rng(123)
    reference = rng.normal(size=(n, 2))
    candidates = tuple(rng.normal(size=(m, 2)) for _ in range(4))
    expected = [shape_similarity.discrete_frechet(reference, c) for c in candidates]
    actual = shape_similarity._discrete_frechet_batch(reference, candidates)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize(("n", "m"), [(0, 0), (0, 5), (5, 0), (1, 5), (64, 64)])
def test_native_frechet_preserves_empty_and_zero_length_curves(n, m):
    reference = np.zeros((n, 2))
    candidates = tuple(np.zeros((m, 2)) for _ in range(2))
    expected = [shape_similarity.discrete_frechet(reference, c) for c in candidates]
    np.testing.assert_array_equal(shape_similarity._discrete_frechet_batch(reference, candidates), expected)


def test_complete_diagnostics_keep_the_same_scores_for_every_phase(monkeypatch):
    reference = np.asarray([(0, 0), (1, 0), (1, 1), (0, 0), (-1, 0), (-1, -1), (0, 0)])
    reference = shape_similarity.resample(reference, 256)
    candidate = reference + np.random.default_rng(42).normal(0, 0.01, reference.shape)
    measured = shape_similarity._diagnostics(reference, candidate)
    monkeypatch.setattr(shape_similarity, "_discrete_frechet_batch", lambda ref, variants:
                        np.asarray([shape_similarity.discrete_frechet(ref, v) for v in variants]))
    assert measured == shape_similarity._diagnostics(reference, candidate)


@pytest.mark.parametrize(("n", "m"), [(1, 1), (3, 65), (63, 64), (64, 129), (256, 256)])
def test_outline_metrics_share_each_distance_without_changing_results(monkeypatch, n, m):
    import math

    rng = np.random.default_rng(17)
    reference, candidate = rng.normal(size=(n, 2)), rng.normal(size=(m, 2))
    distances = np.linalg.norm(reference[:, None, :] - candidate[None, :, :], axis=2)
    deviation = math.sqrt(0.5 * (
        float(np.mean(np.square(distances.min(axis=1))))
        + float(np.mean(np.square(distances.min(axis=0))))
    ))
    expected = (shape_similarity.hausdorff(reference, candidate), math.exp(-deviation / 0.16), deviation)
    norm = np.linalg.norm
    evaluated_pairs = []

    def counted_norm(array, **kwargs):
        evaluated_pairs.append(array.shape[0] * array.shape[1])
        return norm(array, **kwargs)

    monkeypatch.setattr(np.linalg, "norm", counted_norm)
    assert shape_similarity._outline_components(reference, candidate) == expected
    assert sum(evaluated_pairs) == n * m


@pytest.mark.parametrize("n", [16, 64, 256])
@pytest.mark.parametrize("variant", ["identity", "reversed", "shifted", "noisy", "open"])
def test_orientation_pruning_matches_exhaustive_full_diagnostics(monkeypatch, n, variant):
    reference = shape_similarity.resample(np.asarray([
        (0., 0.), (1., 0.), (0.5, 0.2), (1., 1.), (0., 0.),
        (-1., 0.), (-1., -1.), (0., 0.),
    ]), n)
    candidate = reference.copy()
    if variant == "reversed":
        candidate = candidate[::-1]
    elif variant == "shifted":
        core = np.roll(candidate[:-1], n // 3, axis=0)
        candidate = np.vstack((core, core[0]))
    elif variant == "noisy":
        candidate += np.random.default_rng(42).normal(0, 0.02, candidate.shape)
    elif variant == "open":
        candidate = shape_similarity.resample(candidate[:n // 2], n)
    orientations = shape_similarity._candidate_orientations(reference, candidate)
    actual = shape_similarity._diagnostics(reference, candidate)
    # Score each variant alone so none can be pruned by another incumbent.
    scores = []
    for oriented in orientations:
        monkeypatch.setattr(shape_similarity, "_candidate_orientations", lambda *_, v=oriented: (v,))
        scores.append(shape_similarity._diagnostics(reference, candidate))
    assert actual == max(scores, key=lambda score: score.fidelity)


def test_unbeatable_orientation_skips_landmarks_but_keeps_full_diagnostics(monkeypatch):
    reference = shape_similarity.resample(
        np.asarray([(0., 0.), (1., 0.), (0.2, 0.3), (0., 0.)]), 64,
    )
    original = shape_similarity._landmark_similarity
    calls = []

    def landmarks(ref, candidate):
        calls.append(candidate)
        return original(ref, candidate)

    monkeypatch.setattr(shape_similarity, "_landmark_similarity", landmarks)
    measured = shape_similarity._diagnostics(reference, reference)
    assert measured.fidelity == pytest.approx(1.0)
    assert len(calls) == 1
    assert len(shape_similarity._candidate_orientations(reference, reference)) > 1


def test_orientation_bound_keeps_a_later_winner_with_better_landmarks(monkeypatch):
    reference = shape_similarity.resample(
        np.asarray([(0., 0.), (1., 0.), (0.2, 0.3), (0., 0.)]), 64,
    )
    monkeypatch.setattr(shape_similarity, "_candidate_orientations", lambda *_: (reference,) * 3)
    calls = []

    def landmarks(*_):
        score = 0.1 if not calls else 1.0
        calls.append(score)
        return score

    monkeypatch.setattr(shape_similarity, "_landmark_similarity", landmarks)
    measured = shape_similarity._diagnostics(reference, reference)
    assert measured.landmark_similarity == 1.0
    assert calls == [0.1, 1.0]  # retain the later winner; skip only the final tie


def test_landmark_reference_is_reused_across_distinct_candidates(monkeypatch):
    reference = shape_similarity.resample(
        np.asarray([(0., 0.), (1., 0.), (1., 1.), (0., 0.)]), 64,
    )
    original = shape_similarity._salient_indices
    calls = []

    def salient(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    shape_similarity._landmark_reference.cache_clear()
    monkeypatch.setattr(shape_similarity, "_salient_indices", salient)
    for offset in (0.01, 0.02):
        candidate = reference + offset
        shape_similarity._landmark_similarity(reference, candidate)
    assert len(calls) == 2  # two observation scales, independent of candidates
    reference[1, 0] += 0.1
    shape_similarity._landmark_similarity(reference, candidate)
    assert len(calls) == 4  # changed coordinates must never reuse old features


@pytest.mark.parametrize("closed", [False, True])
@pytest.mark.parametrize("span", [2, 4])
def test_cached_landmark_reference_preserves_exact_features_and_is_immutable(closed, span):
    reference = np.random.default_rng(127).normal(size=(64, 2))
    expected = shape_similarity._signed_turns(reference, span)
    turns, landmarks = shape_similarity._landmark_reference(
        reference.tobytes(), reference.dtype.str, span, closed,
    )
    np.testing.assert_array_equal(turns, expected)
    assert landmarks == tuple(shape_similarity._salient_indices(expected, span=span, closed=closed))
    with pytest.raises(ValueError):
        turns[0] = 42


def test_routing_workers_reuse_one_pool_and_a_new_run_gets_a_new_pool(monkeypatch):
    clients = []

    class Client:
        closed = False

        def __init__(self, **kwargs):
            clients.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setattr("gps_art_wizzard.workflow_runtime.httpx.Client", Client)
    runtime = WorkflowRuntime(WorkflowState("heart"), max_duration_seconds=175, max_llm_calls=0)
    with ThreadPoolExecutor(max_workers=3) as pool:
        returned = list(pool.map(lambda _: runtime.routing_client(), range(9)))
    assert len(clients) == 1
    assert all(client is clients[0] for client in returned)
    with runtime.activate(), ors_client._routing_client() as client:
        assert client is clients[0]
    assert not client.closed
    runtime.close_routing_client()
    assert client.closed
    runtime.close_routing_client()  # safe on every exit path
    next_run = WorkflowRuntime(WorkflowState("heart"), max_duration_seconds=175, max_llm_calls=0)
    assert next_run.routing_client() is not client
    next_run.close_routing_client()


def test_orchestrator_closes_the_pool_even_when_a_non_node_operation_fails(monkeypatch):
    closed = []
    monkeypatch.setattr(WorkflowRuntime, "close_routing_client", lambda self: closed.append(True))

    def fail(*args, **kwargs):
        raise ValueError("test failure")

    monkeypatch.setattr(Orchestrator, "_run_workflow", fail)
    with pytest.raises(ValueError, match="test failure"):
        Orchestrator({}).run("heart")
    assert closed == [True]


def test_connectivity_retries_continue_after_exploration_budget_without_faking_roads(monkeypatch):
    cfg = ors_client.get_settings().routing
    monkeypatch.setattr(cfg, "ors_api_key", "test-no-network")
    elapsed = [0.0]
    runtime = WorkflowRuntime(WorkflowState("heart"), max_duration_seconds=175, max_llm_calls=0,
                              optimization_budget_seconds=35, clock=lambda: elapsed[0])
    calls = []

    def request(*args, **kwargs):
        calls.append(kwargs["radius"])
        elapsed[0] = 40
        if len(calls) == 1:
            return ors_client._ORSFailure(404, 2010, "Point not found")
        return [(47.5, 19), (47.501, 19.001)], 150

    monkeypatch.setattr(ors_client, "_ors_request", request)
    try:
        with runtime.activate():
            route, distance, snapped, _ = ors_client.snap_route_detailed([(47.5, 19), (47.501, 19.001)])
        assert len(calls) == 2
        assert snapped and distance == 150
        assert route == [(47.5, 19), (47.501, 19.001)]
    finally:
        runtime.close_routing_client()
