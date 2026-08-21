"""Contract tests for run-scoped workflow lifecycle and AI guardrails."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gps_art_wizzard.llm import factory as llm_factory
from gps_art_wizzard.llm.base import LLMResponse
from gps_art_wizzard.state import Validation, WorkflowState
from gps_art_wizzard.workflow_runtime import (
    StepStatus,
    WorkflowRuntime,
    WorkflowStatus,
    active_workflow_runtime,
    trace_asdict,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def _runtime(
    state: WorkflowState,
    *,
    clock: MutableClock | None = None,
    max_llm_calls: int = 8,
    max_events: int = 256,
) -> WorkflowRuntime:
    return WorkflowRuntime(
        state,
        max_duration_seconds=10,
        max_llm_calls=max_llm_calls,
        max_events=max_events,
        clock=clock or MutableClock(),
        wall_clock=lambda: datetime(2026, 8, 20, tzinfo=UTC),
    )


def _passing_validation() -> Validation:
    return Validation(
        score=0.9,
        closure=1.0,
        distance_fit=0.95,
        shape_fidelity=0.88,
    )


def test_instrumented_node_records_a_typed_balanced_lifecycle() -> None:
    state = WorkflowState(prompt="a heart", request_id="request-42")
    clock = MutableClock()
    runtime = _runtime(state, clock=clock)

    class Node:
        def run(self, received: WorkflowState) -> WorkflowState:
            assert active_workflow_runtime() is runtime
            clock.value = 0.125
            return received

    result = runtime.instrument_nodes({"shape": Node()})["shape"].run(state)
    state.validation = _passing_validation()
    runtime.finish(state)

    assert result is state
    assert state.workflow is runtime.trace
    assert runtime.trace.run_id == "request-42"
    assert runtime.trace.status is WorkflowStatus.COMPLETED
    assert runtime.trace.step_attempts == {"shape": 1}
    assert [event.status for event in runtime.trace.events] == [
        StepStatus.RUNNING,
        StepStatus.COMPLETED,
    ]
    assert [event.sequence for event in runtime.trace.events] == [1, 2]
    assert runtime.trace.events[-1].duration_ms == 125
    assert active_workflow_runtime() is None


def test_failed_step_is_classified_without_recording_exception_text() -> None:
    state = WorkflowState(prompt="private prompt")
    clock = MutableClock()
    runtime = _runtime(state, clock=clock)

    def fail() -> WorkflowState:
        clock.value = 0.25
        raise ValueError("provider-secret-value")

    with pytest.raises(ValueError, match="provider-secret-value"):
        runtime.run_step("planning", fail)

    assert runtime.trace.status is WorkflowStatus.FAILED
    assert runtime.trace.error_category == "input"
    assert runtime.trace.duration_ms == 250
    assert runtime.trace.step_failures == 1
    assert runtime.trace.events[-1].status is StepStatus.FAILED
    assert "provider-secret-value" not in str(trace_asdict(runtime.trace))
    assert "private prompt" not in str(trace_asdict(runtime.trace))


def test_finalisation_is_idempotent_after_a_failed_step() -> None:
    state = WorkflowState(prompt="a star")
    runtime = _runtime(state)

    with pytest.raises(RuntimeError):
        runtime.run_step(
            "shape",
            lambda: (_ for _ in ()).throw(RuntimeError("generation failed")),
        )

    state.validation = _passing_validation()
    runtime.finish(state)

    assert runtime.trace.status is WorkflowStatus.FAILED
    assert runtime.trace.error_category == "internal"


def test_event_storage_is_bounded_without_losing_step_counters() -> None:
    state = WorkflowState(prompt="a star")
    runtime = _runtime(state, max_events=8)

    for _ in range(6):
        runtime.run_step("validation", lambda: state)

    assert len(runtime.trace.events) == 8
    assert runtime.trace.dropped_events == 4
    assert runtime.trace.step_attempts == {"validation": 6}


def test_llm_call_budget_switches_subsequent_calls_to_local_fallback(
    monkeypatch,
) -> None:
    state = WorkflowState(prompt="a custom animal")
    runtime = _runtime(state, max_llm_calls=1)

    class Provider:
        name = "test-provider"

        def __init__(self) -> None:
            self.calls = 0

        def is_available(self) -> bool:
            return True

        def complete(self, **_kwargs) -> LLMResponse:
            self.calls += 1
            return LLMResponse(
                "generated",
                self.name,
                "test-model",
                usage={"input_tokens": 7, "output_tokens": 3},
            )

    provider = Provider()
    monkeypatch.setattr(llm_factory, "available_providers", lambda: (provider,))
    llm_factory.reset_sticky()
    try:
        with runtime.activate():
            first = llm_factory.try_complete(lambda: "fallback", messages=[])
            second = llm_factory.try_complete(lambda: "fallback", messages=[])
    finally:
        llm_factory.reset_sticky()

    assert first.text == "generated"
    assert second == "fallback"
    assert provider.calls == 1
    assert runtime.trace.llm_attempts == 1
    assert runtime.trace.llm_successes == 1
    assert runtime.trace.deterministic_fallbacks == 1
    assert runtime.trace.provider_attempts == {"test-provider": 1}
    assert runtime.trace.llm_usage == {"input_tokens": 7, "output_tokens": 3}
    assert "llm_call_budget_exhausted" in runtime.trace.degraded_reasons
    assert "llm_fallback:call_budget_exhausted" in runtime.trace.degraded_reasons


def test_expired_deadline_blocks_only_optional_ai_work() -> None:
    state = WorkflowState(prompt="a custom animal")
    clock = MutableClock()
    runtime = _runtime(state, clock=clock)
    clock.value = 11.0

    allowed, reason = runtime.llm_budget_status()
    deterministic_result = runtime.run_step("placement", lambda: "still-runs")

    assert allowed is False
    assert reason == "deadline_exceeded"
    assert deterministic_result == "still-runs"
    assert runtime.trace.llm_attempts == 0
    assert runtime.trace.degraded_reasons == ["workflow_deadline_exceeded"]


def test_public_summary_separates_execution_mode_from_quality_outcome() -> None:
    state = WorkflowState(prompt="a heart")
    runtime = _runtime(state)
    state.validation = _passing_validation()
    state.below_threshold = True

    runtime.finish(state)
    summary = runtime.trace.public_summary()

    assert summary["status"] == "needs_review"
    assert summary["mode"] == "deterministic"
    assert summary["degraded_reasons"] == ["quality_gates_not_met"]
    assert "events" not in summary
    assert "request_id" not in summary
    assert "prompt" not in summary
