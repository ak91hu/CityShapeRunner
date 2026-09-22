"""Benchmark evidence is paired, preserves failures and never invents human labels."""
from dataclasses import asdict

import pytest

from gps_art_wizzard.generation_benchmark import (
    attach_human_labels,
    benchmark_cases,
    compare,
    result_record,
    run_cases,
    summary,
)
from gps_art_wizzard.state import Shape, SnappedRoute, WorkflowState
from gps_art_wizzard.tools.shape_library import SHAPES
from gps_art_wizzard.workflow_runtime import WorkflowRuntime, record_routing_request


def test_cases_cover_full_cross_product_with_known_templates():
    cases = benchmark_cases()
    assert len(cases) == len({case.id for case in cases}) == 200
    assert len({case.city for case in cases}) == 5
    assert all(case.shape in SHAPES for case in cases)


def test_summary_reports_measured_fidelity_without_inventing_missing_scores():
    records = [{"failure_stage": None, "validation": {"shape_fidelity": value}}
               for value in (0.6, 0.8, None)]
    assert summary(records)["mean_shape_fidelity"] == pytest.approx(0.7)


def test_offline_preview_is_not_counted_as_connected_or_human_recognized():
    state = WorkflowState("heart", shape=Shape("heart", [], True),
                          snapped=SnappedRoute([(47, 19), (47.1, 19.1)], 1000, False))
    row = result_record(benchmark_cases()[0], state, 1)
    report = summary([row])
    assert report["connected_routes"] == 0
    assert report["human_recognition_rate"] is None
    assert row["failure_stage"] == "street_connectivity"


def test_connected_text_fallback_still_reports_shape_generation_failure():
    state = WorkflowState("heart", shape=Shape("text:heart", [], True, source="fallback"),
                          snapped=SnappedRoute([(47, 19), (47.1, 19.1)], 1000, True))
    row = result_record(benchmark_cases()[0], state, 1)
    assert row["failure_stage"] == "shape_generation"


def test_result_record_retains_graph_reconnection_evidence():
    state = WorkflowState("heart", shape=Shape("heart", [], True))
    state.history.append({"agent": "contour_graph", "accepted": True, "proxy_fidelity": 0.8})
    row = result_record(benchmark_cases()[0], state, 1)
    assert row["search_diagnostics"]["graph_reconnections"] == [state.history[0]]


def test_labels_are_bound_to_exact_route_and_unlabeled_rows_stay_unknown():
    row = {"case": {"id": "a"}, "route_hash": "123", "human_recognized": None}
    labels = [{"case_id": "a", "route_hash": "old", "recognized": True}]
    assert attach_human_labels([row], labels)[0]["human_recognized"] is None
    labels[0]["route_hash"] = "123"
    assert attach_human_labels([row], labels)[0]["human_recognized"] is True
    assert row["human_recognized"] is None


def test_comparison_rejects_unmatched_cases_or_network_revisions():
    a = {"network_revision": "r1", "records": []}
    with pytest.raises(ValueError, match="revisions"):
        compare(a, {"network_revision": "r2", "records": []})
    with pytest.raises(ValueError, match="case set"):
        compare(a, {"network_revision": "r1", "records": [{"case": {"id": "extra"}}]})


def test_runner_checkpoints_failures_and_restores_configuration():
    from gps_art_wizzard.config import get_settings
    before = get_settings().workflow.preflight_adaptive
    checkpoints = []

    def fail(*args, **kwargs):
        raise RuntimeError("secret provider response must not be serialized")

    result = run_cases(benchmark_cases()[:2], variant="baseline", runner=fail,
                       checkpoint=lambda r: checkpoints.append(len(r["records"])))
    assert checkpoints == [1, 2]
    assert result["summary"]["failures"] == {"execution_error": 2}
    assert result["summary"]["mean_api_attempts"] is None
    assert "secret" not in str(result)
    assert get_settings().workflow.preflight_adaptive == before
    assert result["shape_metric_revision"] == "closed-phase-v2"


def test_comparison_rejects_scores_from_different_metric_revisions():
    old = {"records": []}
    new = {"records": [], "shape_metric_revision": "closed-phase-v2"}
    with pytest.raises(ValueError, match="shape metric revisions differ"):
        compare(old, new)
    assert compare(new, new)["shape_metric_revision"] == "closed-phase-v2"


def test_request_counts_include_retries_and_are_run_scoped():
    state = WorkflowState("triangle")
    runtime = WorkflowRuntime(state, max_duration_seconds=10, max_llm_calls=0, max_events=20)
    with runtime.activate():
        record_routing_request("snap")
        record_routing_request("directions")
        record_routing_request("directions")
    record_routing_request("snap")
    assert asdict(runtime.trace)["routing_requests"] == {"snap": 1, "directions": 2}


def test_parallel_workers_cannot_exceed_shared_ai_call_budget():
    from concurrent.futures import ThreadPoolExecutor
    runtime = WorkflowRuntime(WorkflowState("triangle"), max_duration_seconds=10, max_llm_calls=3, max_events=20)
    with ThreadPoolExecutor(max_workers=12) as pool:
        reservations = list(pool.map(lambda _: runtime.reserve_llm_attempt("opencode"), range(30)))
    assert sum(allowed for allowed, _ in reservations) == 3
    assert runtime.trace.llm_attempts == 3


@pytest.mark.parametrize("endpoint", ["snap", "directions"])
@pytest.mark.parametrize("status", [403, 404, 413, 429, 503])
def test_provider_limit_or_outage_marks_search_incomplete_without_recording_body(endpoint, status):
    import httpx

    from gps_art_wizzard.tools import ors_client

    state = WorkflowState("heart", shape=Shape("heart", [], True))
    runtime = WorkflowRuntime(state, max_duration_seconds=10, max_llm_calls=0, max_events=20)
    with httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(status, json={"error": "private provider details"}))) as client, runtime.activate():
        if endpoint == "snap":
            ors_client._snap_request("https://routing.test/snap", {}, [[19, 47]], radius=120, client=client)
        else:
            ors_client._ors_request("https://routing.test/directions", {}, [[19, 47], [19.01, 47]],
                                    preference="shortest", continue_straight=False, radius=120, client=client)
    row = result_record(benchmark_cases()[0], state, 1)
    assert row["search_complete"] is False
    assert f"{endpoint}.http_{status}" in row["search_incomplete_reasons"]
    assert row["workflow"]["routing_requests"] == {endpoint: 1}
    assert row["workflow"]["routing_failures"] == {f"{endpoint}.http_{status}": 1}
    assert "private provider" not in str(row)
    assert summary([row])["incomplete_searches"] == 1


def test_expected_disconnected_candidate_is_not_a_provider_outage():
    import httpx

    from gps_art_wizzard.tools import ors_client

    state = WorkflowState("heart")
    runtime = WorkflowRuntime(state, max_duration_seconds=10, max_llm_calls=0, max_events=20)
    with httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(400, json={"error": {"code": 2009, "message": "route not found"}}))) as client, runtime.activate():
        ors_client._ors_request("https://routing.test/directions", {}, [[19, 47], [19.01, 47]],
                                preference="shortest", continue_straight=False, radius=120, client=client)
    assert runtime.trace.routing_failures == {}
    assert result_record(benchmark_cases()[0], state, 1)["search_complete"] is True


@pytest.mark.parametrize("endpoint", ["snap", "directions"])
@pytest.mark.parametrize("category", ["transport", "invalid_response"])
def test_routing_transport_and_malformed_response_are_recorded(endpoint, category):
    import httpx

    from gps_art_wizzard.tools import ors_client

    def respond(request):
        if category == "transport":
            raise httpx.ReadTimeout("private transport detail", request=request)
        return httpx.Response(200, json={})
    state = WorkflowState("heart")
    runtime = WorkflowRuntime(state, max_duration_seconds=10, max_llm_calls=0, max_events=20)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client, runtime.activate():
        if endpoint == "snap":
            ors_client._snap_request("https://routing.test/snap", {}, [[19, 47]], radius=120, client=client)
        else:
            ors_client._ors_request("https://routing.test/directions", {}, [[19, 47], [19.01, 47]],
                                    preference="shortest", continue_straight=False, radius=120, client=client)
    assert runtime.trace.routing_failures == {f"{endpoint}.{category}": 1}
    assert "private" not in str(runtime.trace.public_summary())


def test_comparison_rejects_incomplete_and_legacy_unverified_searches():
    from gps_art_wizzard.workflow_runtime import record_routing_failure

    state = WorkflowState("heart")
    runtime = WorkflowRuntime(state, max_duration_seconds=10, max_llm_calls=0, max_events=20)
    with runtime.activate():
        record_routing_request("directions")
    complete = result_record(benchmark_cases()[0], state, 1)
    with runtime.activate():
        record_routing_failure("directions", "transport")
        record_routing_request("directions")  # a later attempt cannot erase a missing measurement
    incomplete = result_record(benchmark_cases()[0], state, 1)
    assert compare({"records": [complete]}, {"records": [complete]})["paired_cases"] == 1
    for invalid in (incomplete, {key: value for key, value in complete.items() if key != "search_complete"}):
        with pytest.raises(ValueError, match="complete searches"):
            compare({"records": [complete]}, {"records": [invalid]})
    fresh = WorkflowRuntime(WorkflowState("heart"), max_duration_seconds=10, max_llm_calls=0, max_events=20)
    assert fresh.trace.routing_failures == {}
