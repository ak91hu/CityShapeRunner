"""Run-scoped lifecycle, budgets, and telemetry for the agent workflow.

The route algorithm deliberately stays in :mod:`orchestrator`.  This module
wraps its nodes without changing their inputs or outputs, giving every run a
small, typed operational record and a shared budget for optional LLM calls.
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

import httpx

if TYPE_CHECKING:
    from .state import WorkflowState

log = logging.getLogger(__name__)

_SAFE_METRIC_KEY = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,63}$")
_T = TypeVar("_T")


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class StepStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class WorkflowEvent:
    """One bounded, prompt-free lifecycle event."""

    sequence: int
    stage: str
    attempt: int
    status: StepStatus
    elapsed_ms: int
    duration_ms: int | None = None
    error_category: str | None = None


@dataclass
class WorkflowTrace:
    """Typed operational summary attached to one ``WorkflowState``."""

    run_id: str
    request_id: str | None
    status: WorkflowStatus
    started_at: str
    max_duration_seconds: float
    max_llm_calls: int
    optimization_budget_seconds: float | None = None
    duration_ms: int | None = None
    step_attempts: dict[str, int] = field(default_factory=dict)
    step_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    step_failures: int = 0
    llm_attempts: int = 0
    llm_successes: int = 0
    deterministic_fallbacks: int = 0
    provider_attempts: dict[str, int] = field(default_factory=dict)
    llm_usage: dict[str, int] = field(default_factory=dict)
    routing_requests: dict[str, int] = field(default_factory=dict)
    routing_failures: dict[str, int] = field(default_factory=dict)
    degraded_reasons: list[str] = field(default_factory=list)
    events: list[WorkflowEvent] = field(default_factory=list)
    dropped_events: int = 0
    error_category: str | None = None

    @property
    def mode(self) -> str:
        if self.llm_successes and self.deterministic_fallbacks:
            return "hybrid"
        if self.llm_successes:
            return "ai"
        return "deterministic"

    def public_summary(self) -> dict[str, Any]:
        """Return stable, safe fields suitable for the HTTP response."""

        completed_stages = [
            event.stage
            for event in self.events
            if event.status is StepStatus.COMPLETED
        ]
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "mode": self.mode,
            "duration_ms": self.duration_ms,
            "limits": {
                "max_duration_seconds": self.max_duration_seconds,
                "max_llm_calls": self.max_llm_calls,
                "optimization_budget_seconds": self.optimization_budget_seconds,
            },
            "steps": {
                "attempts": dict(self.step_attempts),
                "completed": completed_stages,
                "failures": self.step_failures,
                "dropped_events": self.dropped_events,
                "metrics": {
                    stage: {
                        "duration_ms": metric["duration_ms"],
                        "routing_requests": dict(metric["routing_requests"]),
                    }
                    for stage, metric in self.step_metrics.items()
                },
            },
            "ai": {
                "attempts": self.llm_attempts,
                "successful_calls": self.llm_successes,
                "deterministic_fallbacks": self.deterministic_fallbacks,
                "provider_attempts": dict(self.provider_attempts),
                "usage": dict(self.llm_usage),
            },
            "degraded_reasons": list(self.degraded_reasons),
            "routing_requests": dict(self.routing_requests),
            "routing_failures": dict(self.routing_failures),
            "error_category": self.error_category,
        }


class RunnableNode(Protocol):
    def run(self, state: WorkflowState) -> WorkflowState: ...


class _InstrumentedNode:
    def __init__(self, stage: str, node: RunnableNode, runtime: WorkflowRuntime):
        self._stage = stage
        self._node = node
        self._runtime = runtime

    def run(self, state: WorkflowState) -> WorkflowState:
        result = self._runtime.run_step(
            self._stage,
            lambda: self._node.run(state),
        )
        if self._stage == "validation":
            self._runtime.publish_preview(state)
        return result

    def run_recoverable(self, state: WorkflowState) -> WorkflowState:
        """Record a speculative candidate failure without finalising the run."""

        result = self._runtime.run_step(
            self._stage,
            lambda: self._node.run(state),
            recoverable=True,
        )
        if self._stage == "validation":
            self._runtime.publish_preview(state)
        return result


_ACTIVE_RUNTIME: ContextVar[WorkflowRuntime | None] = ContextVar(
    "gps_art_workflow_runtime",
    default=None,
)
_ACTIVE_STAGES: ContextVar[tuple[str, ...]] = ContextVar(
    "gps_art_workflow_stages", default=()
)
_CANCELLATION_SIGNAL: ContextVar[threading.Event | None] = ContextVar(
    "gps_art_cancellation", default=None
)


class WorkflowCancelledError(asyncio.CancelledError):
    """Cancellation is control flow; provider fallback handlers must not swallow it."""


@contextmanager
def cancellation_scope(signal: threading.Event):
    token = _CANCELLATION_SIGNAL.set(signal)
    try:
        yield
    finally:
        _CANCELLATION_SIGNAL.reset(token)


def check_cancellation() -> None:
    signal = _CANCELLATION_SIGNAL.get()
    if signal is not None and signal.is_set():
        raise WorkflowCancelledError()


def active_workflow_runtime() -> WorkflowRuntime | None:
    """Return the runtime bound to the currently executing workflow node."""

    return _ACTIVE_RUNTIME.get()


class WorkflowRuntime:
    """Instrument nodes and coordinate the optional-AI budget for one run."""

    def __init__(
        self,
        state: WorkflowState,
        *,
        max_duration_seconds: float,
        max_llm_calls: int,
        max_events: int = 256,
        optimization_budget_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
        preview_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._state = state
        self._clock = clock
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._started = clock()
        # Candidate measurements run in a bounded worker pool; every trace
        # mutation goes through this lock so telemetry stays consistent.
        # Reentrant: finalisation degrades the trace while holding the lock.
        self._lock = threading.RLock()
        self._max_events = max(8, int(max_events))
        self._sequence = 0
        self._deadline_noted = False
        self._finished = False
        self._event_sink = event_sink
        self._preview_sink = preview_sink
        self._preview_sent = False
        self._connected_routes: set[int] = set()
        self._routing_client: httpx.Client | None = None
        # A caller may reuse its request ID; memoised routing must never cross
        # the boundary between two distinct workflow executions.
        self.cache_scope = uuid.uuid4().hex
        request_id = state.request_id
        self.trace = WorkflowTrace(
            run_id=request_id or uuid.uuid4().hex,
            request_id=request_id,
            status=WorkflowStatus.RUNNING,
            started_at=self._wall_clock().isoformat(),
            max_duration_seconds=max(1.0, float(max_duration_seconds)),
            # -1 is the explicit unlimited sentinel used by cost-zero models.
            # Zero remains useful for deterministic-only runs and tests.
            max_llm_calls=max(-1, int(max_llm_calls)),
            optimization_budget_seconds=(
                min(max(1.0, float(optimization_budget_seconds)), max(1.0, float(max_duration_seconds)))
                if optimization_budget_seconds is not None else None
            ),
        )
        state.workflow = self.trace
        log.info(
            "Workflow started",
            extra={
                "event": "workflow.started",
                "workflow_run_id": self.trace.run_id,
                "workflow_max_duration_seconds": self.trace.max_duration_seconds,
                "workflow_max_llm_calls": self.trace.max_llm_calls,
            },
        )

    def instrument_nodes(
        self,
        nodes: Mapping[str, RunnableNode],
    ) -> dict[str, RunnableNode]:
        return {
            stage: _InstrumentedNode(stage, node, self)
            for stage, node in nodes.items()
        }

    def record_routing_request(self, endpoint: str) -> None:
        with self._lock:
            self.trace.routing_requests[endpoint] = self.trace.routing_requests.get(endpoint, 0) + 1
            for stage in _ACTIVE_STAGES.get():
                metric = self.trace.step_metrics.setdefault(
                    stage, {"duration_ms": 0, "routing_requests": {}}
                )
                requests = metric["routing_requests"]
                requests[endpoint] = requests.get(endpoint, 0) + 1
            stages = _ACTIVE_STAGES.get()
            active_stage = stages[-1] if stages else None
            attempt = self.trace.step_attempts.get(active_stage, 1) if active_stage else 1
        # Publish before waiting on the provider, including retries. Otherwise
        # the visible request count can remain at zero throughout a slow call.
        if active_stage is not None:
            self._emit(active_stage, attempt, StepStatus.RUNNING)

    def routing_client(self) -> httpx.Client:
        """Share HTTP connections across this run's bounded routing workers."""
        with self._lock:
            if self._routing_client is None:
                self._routing_client = httpx.Client(
                    limits=httpx.Limits(max_connections=6, max_keepalive_connections=6),
                )
            return self._routing_client

    def close_routing_client(self) -> None:
        with self._lock:
            client, self._routing_client = self._routing_client, None
        if client is not None:
            client.close()

    def routing_rate_limited(self, endpoint: str) -> bool:
        """Stop new calls to an exhausted endpoint for this workflow only."""
        check_cancellation()
        with self._lock:
            return self.trace.routing_failures.get(f"{endpoint}.http_429", 0) > 0

    def record_routing_failure(self, endpoint: str, category: str) -> None:
        key = f"{endpoint}.{category}"
        with self._lock:
            self.trace.routing_failures[key] = self.trace.routing_failures.get(key, 0) + 1

    def publish_preview(self, state: WorkflowState) -> None:
        """Show only the first provider-routed, connected candidate; never expose an export."""
        snapped = state.snapped
        validation = state.validation
        if not snapped or not validation or not validation.on_roads or not snapped.snapped:
            return
        from .tools import route_safety

        if not route_safety.is_provider_routed_geometry(
            snapped.points, snapped.total_distance_m, routed=True
        ):
            return
        with self._lock:
            self._connected_routes.add(hash(tuple(tuple(point) for point in snapped.points)))
            if self._preview_sent or self._preview_sink is None:
                return
            self._preview_sent = True
        payload = {
            "points": [[lat, lon] for lat, lon in snapped.points],
            "distance_km": round(snapped.total_distance_m / 1000, 2),
            "shape_name": state.shape.name if state.shape else None,
            "status": "checking",
        }
        try:
            self._preview_sink(payload)
        except Exception:  # noqa: BLE001 - preview delivery must not stop route generation
            log.warning("Workflow preview listener failed", exc_info=True)

    @contextmanager
    def activate(self):
        token = _ACTIVE_RUNTIME.set(self)
        try:
            yield
        finally:
            _ACTIVE_RUNTIME.reset(token)

    def run_step(
        self,
        stage: str,
        operation: Callable[[], _T],
        *,
        recoverable: bool = False,
    ) -> _T:
        check_cancellation()
        with self._lock:
            attempt = self.trace.step_attempts.get(stage, 0) + 1
            self.trace.step_attempts[stage] = attempt
        started = self._clock()
        self._note_deadline_if_needed()
        self._emit(stage, attempt, StepStatus.RUNNING)
        log.info(
            "Workflow step started: %s",
            stage,
            extra={
                "event": "workflow.step.started",
                "workflow_run_id": self.trace.run_id,
                "workflow_stage": stage,
                "workflow_attempt": attempt,
            },
        )
        try:
            with self.activate():
                token = _ACTIVE_STAGES.set((*_ACTIVE_STAGES.get(), stage))
                try:
                    result = operation()
                finally:
                    _ACTIVE_STAGES.reset(token)
        except Exception as exc:
            duration_ms = self._milliseconds(self._clock() - started)
            category = classify_error(exc)
            with self._lock:
                self.trace.step_failures += 1
                self._record_step_duration(stage, duration_ms)
            self._emit(
                stage,
                attempt,
                StepStatus.FAILED,
                duration_ms=duration_ms,
                error_category=category,
            )
            log.error(
                "Workflow step failed: %s",
                stage,
                extra={
                    "event": "workflow.step.failed",
                    "workflow_run_id": self.trace.run_id,
                    "workflow_stage": stage,
                    "workflow_attempt": attempt,
                    "workflow_duration_ms": duration_ms,
                    "workflow_error_category": category,
                    "workflow_error_type": type(exc).__name__,
                },
            )
            if not recoverable:
                self.fail(exc)
            raise

        duration_ms = self._milliseconds(self._clock() - started)
        with self._lock:
            routing_requests = self._record_step_duration(stage, duration_ms)
        self._emit(
            stage,
            attempt,
            StepStatus.COMPLETED,
            duration_ms=duration_ms,
        )
        log.info(
            "Workflow step completed: %s",
            stage,
            extra={
                "event": "workflow.step.completed",
                "workflow_run_id": self.trace.run_id,
                "workflow_stage": stage,
                "workflow_attempt": attempt,
                "workflow_duration_ms": duration_ms,
                "workflow_routing_requests": routing_requests,
            },
        )
        return result

    def _record_step_duration(self, stage: str, duration_ms: int) -> dict[str, int]:
        """Accumulate timings and return a stable copy of the stage's ORS counts."""
        with self._lock:
            metric = self.trace.step_metrics.setdefault(
                stage, {"duration_ms": 0, "routing_requests": {}}
            )
            metric["duration_ms"] += duration_ms
            return dict(metric["routing_requests"])

    def llm_budget_status(self) -> tuple[bool, str | None]:
        check_cancellation()
        if self._elapsed() >= self.trace.max_duration_seconds:
            self._note_deadline_if_needed()
            return False, "deadline_exceeded"
        with self._lock:
            exhausted = (
                self.trace.max_llm_calls >= 0
                and self.trace.llm_attempts >= self.trace.max_llm_calls
            )
        if exhausted:
            self._degrade("llm_call_budget_exhausted")
            return False, "call_budget_exhausted"
        return True, None

    def deadline_exceeded(self, *, quality_required: bool = False) -> bool:
        """Stop optional optimisation without bypassing routing or export gates.

        An in-flight provider request is allowed to finish. This is a search
        budget, not a promise of a maximum HTTP response time.
        """

        check_cancellation()
        # The shorter exploration budget must not take time away from repairing
        # a weak drawing or obtaining connected Directions evidence. Those
        # operations retain the original workflow budget.
        budget = self.trace.max_duration_seconds if quality_required else (
            self.trace.optimization_budget_seconds or self.trace.max_duration_seconds
        )
        exceeded = self._elapsed() >= budget
        if exceeded and not quality_required and self.trace.optimization_budget_seconds is not None:
            self._degrade("optimization_budget_exhausted")
        return exceeded

    def publish_search_progress(self) -> None:
        """Publish real batch completions while the preflight node is running."""
        self._emit("preflight", self.trace.step_attempts.get("preflight", 1), StepStatus.RUNNING)

    def record_llm_attempt(self, provider: str) -> None:
        with self._lock:
            self.trace.llm_attempts += 1
            self.trace.provider_attempts[provider] = (
                self.trace.provider_attempts.get(provider, 0) + 1
            )

    def reserve_llm_attempt(self, provider: str) -> tuple[bool, str | None]:
        """Atomically reserve one call across concurrent candidate workers."""
        with self._lock:
            allowed, reason = self.llm_budget_status()
            if not allowed:
                return False, reason
            self.record_llm_attempt(provider)
            return True, None

    def record_llm_success(self, usage: Mapping[str, Any] | None) -> None:
        with self._lock:
            self.trace.llm_successes += 1
            for key, value in (usage or {}).items():
                if (
                    isinstance(key, str)
                    and _SAFE_METRIC_KEY.fullmatch(key)
                    and isinstance(value, int)
                    and not isinstance(value, bool)
                    and value >= 0
                ):
                    self.trace.llm_usage[key] = self.trace.llm_usage.get(key, 0) + value

    def record_deterministic_fallback(self, reason: str) -> None:
        with self._lock:
            self.trace.deterministic_fallbacks += 1
        self._degrade(f"llm_fallback:{reason}")

    def finish(self, state: WorkflowState) -> None:
        """Finalise once; quality outcome is separate from execution failures."""

        with self._lock:
            if self._finished:
                return
            self.trace.duration_ms = self._milliseconds(self._elapsed())
            if state.validation is None:
                self.trace.status = WorkflowStatus.FAILED
                self.trace.error_category = self.trace.error_category or "quality"
            elif state.below_threshold:
                self.trace.status = WorkflowStatus.NEEDS_REVIEW
                self._degrade("quality_gates_not_met")
                self.trace.error_category = None
            else:
                self.trace.status = WorkflowStatus.COMPLETED
                self.trace.error_category = None
            self._finished = True
        self._log_finished()

    def fail(self, exc: Exception) -> None:
        """Finalise a failed run without retaining exception text."""

        with self._lock:
            if self._finished:
                return
            self.trace.duration_ms = self._milliseconds(self._elapsed())
            self.trace.status = WorkflowStatus.FAILED
            self.trace.error_category = classify_error(exc)
            self._finished = True
        self._log_finished(error_type=type(exc).__name__)

    def _log_finished(self, *, error_type: str | None = None) -> None:
        log.info(
            "Workflow finished",
            extra={
                "event": "workflow.finished",
                "workflow_run_id": self.trace.run_id,
                "workflow_status": self.trace.status.value,
                "workflow_mode": self.trace.mode,
                "workflow_duration_ms": self.trace.duration_ms,
                "workflow_step_failures": self.trace.step_failures,
                "workflow_llm_attempts": self.trace.llm_attempts,
                "workflow_llm_fallbacks": self.trace.deterministic_fallbacks,
                "workflow_error_category": self.trace.error_category,
                "workflow_error_type": error_type,
            },
        )

    def _elapsed(self) -> float:
        return max(0.0, self._clock() - self._started)

    @staticmethod
    def _milliseconds(seconds: float) -> int:
        return max(0, round(seconds * 1000))

    def _emit(
        self,
        stage: str,
        attempt: int,
        status: StepStatus,
        *,
        duration_ms: int | None = None,
        error_category: str | None = None,
    ) -> None:
        with self._lock:
            self._sequence += 1
            event = WorkflowEvent(
                sequence=self._sequence,
                stage=stage,
                attempt=attempt,
                status=status,
                elapsed_ms=self._milliseconds(self._elapsed()),
                duration_ms=duration_ms,
                error_category=error_category,
            )
            phase = stage if stage.startswith("polish.") else next(
                (active for active in reversed(_ACTIVE_STAGES.get()) if active.startswith("polish.")),
                None,
            )
            phase_metric = self.trace.step_metrics.get(phase, {}) if phase else {}
            if len(self.trace.events) >= self._max_events:
                self.trace.dropped_events += 1
            else:
                self.trace.events.append(event)
            sink = self._event_sink
            payload = {
                "sequence": event.sequence,
                "stage": event.stage,
                "attempt": event.attempt,
                "status": event.status.value,
                "elapsed_ms": event.elapsed_ms,
                "duration_ms": event.duration_ms,
                "routing_requests": dict(self.trace.routing_requests),
                "preflight_count": self._state.preflight_count,
                "search_areas": self._state.search_areas,
                "connected_candidates": len(self._connected_routes),
                "optimization_budget_seconds": self.trace.optimization_budget_seconds,
                "phase": phase,
                "phase_routing_requests": dict(phase_metric.get("routing_requests", {})),
            }
        if sink is not None:
            try:
                sink(payload)
            except Exception:  # noqa: BLE001 - telemetry must not stop route generation
                log.warning("Workflow progress listener failed", exc_info=True)

    def _note_deadline_if_needed(self) -> None:
        with self._lock:
            if self._deadline_noted or self._elapsed() < self.trace.max_duration_seconds:
                return
            self._deadline_noted = True
        self._degrade("workflow_deadline_exceeded")
        log.warning(
            "Workflow advisory deadline exceeded; optional AI calls will use fallback",
            extra={
                "event": "workflow.budget.deadline_exceeded",
                "workflow_run_id": self.trace.run_id,
            },
        )

    def _degrade(self, reason: str) -> None:
        with self._lock:
            if reason not in self.trace.degraded_reasons:
                self.trace.degraded_reasons.append(reason)


def classify_error(exc: Exception) -> str:
    """Coarse error taxonomy; deliberately excludes exception messages."""

    if isinstance(exc, (TimeoutError, ConnectionError)):
        return "dependency"
    if isinstance(exc, (TypeError, ValueError)):
        return "input"
    if exc.__class__.__name__ in {"LLMError", "NoProviderError"}:
        return "dependency"
    return "internal"


def trace_asdict(trace: WorkflowTrace) -> dict[str, Any]:
    """Full internal representation for diagnostics and tests."""

    return asdict(trace)


def record_routing_request(endpoint: str) -> None:
    """Count actual attempts, including retries, without recording credentials."""
    check_cancellation()
    runtime = _ACTIVE_RUNTIME.get()
    if runtime is not None:
        runtime.record_routing_request(endpoint)


def record_routing_failure(endpoint: str, category: str) -> None:
    """Record fixed operational categories, never provider bodies or secrets."""
    runtime = _ACTIVE_RUNTIME.get()
    if runtime is not None:
        runtime.record_routing_failure(endpoint, category)
