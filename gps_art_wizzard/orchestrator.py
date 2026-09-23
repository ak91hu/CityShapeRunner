"""Orchestrator: the graph/loop engine.

Pipeline::

    intent -> planning -> shape -> placement -> preflight -> snap -> validation
                                    ^       shortlist             |
                                    |          refine <-----------+
                                    v
                                 export   (uses the best measured street route)

The refinement loop never regresses: every candidate starts from the best
known draft, and weaker candidates are discarded while the bounded search
continues with another deterministic transform.
"""

from __future__ import annotations

import contextvars
import copy
import logging
import math
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

from .config import get_settings
from .graph import build_nodes
from .logging_config import current_request_id
from .quality import (
    distance_fit_minimum,
    passes_quality_gates,
    quality_gate_report,
    route_quality_rank,
)
from .state import (
    FitDecision,
    Intent,
    LatLon,
    MapPlacement,
    RoutePreferences,
    Shape,
    WorkflowState,
)
from .workflow_runtime import WorkflowRuntime

log = logging.getLogger(__name__)

# Upper bound for the candidate-measurement worker pool. Public routing APIs
# enforce per-minute quotas; a small pool already collapses the wall-clock
# time of the recovery/suggestion/fallback searches from a sum to a maximum.
_MAX_MEASUREMENT_WORKERS = 6

# Equal-arc diagnostics use 256 samples. Local street edits can therefore
# produce real but sub-0.0005 component gains near a phase boundary. Let those
# bounded candidates reach authoritative Directions validation; the normal
# quality rank still rejects any routed regression and the stage remains
# limited to two measurements.
_MIN_GRAPH_PROXY_PROGRESS = 0.00025
_GRAPH_BALANCED_OVERRIDE = 0.002
_GRAPH_BOTTLENECK_COMPONENTS = (
    "spatial_similarity",
    "coverage_similarity",
    "turning_similarity",
    "landmark_similarity",
    "reversal_similarity",
    "length_similarity",
    "extent_similarity",
)
_GRAPH_PRESERVED_COMPONENTS = (
    "coverage_similarity",
    "landmark_similarity",
    "extent_similarity",
    "reversal_similarity",
)


class _ShapeDiagnostics(Protocol):
    @property
    def fidelity(self) -> float: ...

    @property
    def spatial_similarity(self) -> float: ...

    @property
    def coverage_similarity(self) -> float: ...

    @property
    def turning_similarity(self) -> float: ...

    @property
    def landmark_similarity(self) -> float: ...

    @property
    def reversal_similarity(self) -> float: ...

    @property
    def length_similarity(self) -> float: ...

    @property
    def extent_similarity(self) -> float: ...


def _promising_graph_proxy(
    baseline: _ShapeDiagnostics,
    candidate: _ShapeDiagnostics,
) -> tuple[float, float] | None:
    """Return balanced proxy rank/bottleneck or reject the local graph edit.

    This mirrors partial routed-candidate ordering: a local edit may trade a
    small weakest-component loss for a substantially more recognisable whole
    silhouette. Directions and the authoritative quality rank still decide
    whether that speculative graph path is retained.
    """
    baseline_bottleneck = min(
        getattr(baseline, metric) for metric in _GRAPH_BOTTLENECK_COMPONENTS
    )
    candidate_bottleneck = min(
        getattr(candidate, metric) for metric in _GRAPH_BOTTLENECK_COMPONENTS
    )
    if (
        candidate_bottleneck + candidate.fidelity
        < baseline_bottleneck + baseline.fidelity + _MIN_GRAPH_PROXY_PROGRESS
        or candidate.fidelity < 0.98 * baseline.fidelity
        or any(
            getattr(candidate, metric) < 0.98 * getattr(baseline, metric)
            for metric in _GRAPH_PRESERVED_COMPONENTS
        )
    ):
        return None
    return candidate_bottleneck + candidate.fidelity, candidate_bottleneck


def _graph_proxy_priority(
    proxy_rank: float,
    bottleneck: float,
    fidelity: float,
    turning: float,
    length: float,
    *,
    near_gate: bool,
) -> tuple[float, float, float, float, float]:
    """Prefer gate closure near the threshold, balanced progress otherwise."""
    if near_gate:
        return bottleneck, proxy_rank, fidelity, turning, length
    return proxy_rank, bottleneck, fidelity, turning, length


def _balanced_proxy_overrides(*, balanced_rank: float, bottleneck_rank: float) -> bool:
    """Allow a material whole-shape gain to beat a marginal gate advantage."""
    return balanced_rank >= bottleneck_rank + _GRAPH_BALANCED_OVERRIDE


def _densify_local_guides(guides: list[LatLon]) -> list[LatLon]:
    """Add one midpoint per local guide segment without moving endpoints."""
    if len(guides) < 2:
        return list(guides)
    dense = [guides[0]]
    for first, second in zip(guides, guides[1:], strict=False):
        dense.append(((first[0] + second[0]) / 2, (first[1] + second[1]) / 2))
        dense.append(second)
    return dense


class WorkflowNode(Protocol):
    def run(self, state: WorkflowState) -> WorkflowState: ...


class Orchestrator:
    def __init__(self, nodes: Mapping[str, WorkflowNode] | None = None):
        self.nodes = build_nodes() if nodes is None else nodes

    def run(
        self,
        prompt: str,
        *,
        intent_override: Intent | None = None,
        start_point: LatLon | None = None,
        start_label: str | None = None,
        start_direction_deg: float | None = None,
        route_preferences: RoutePreferences | None = None,
        reference_shape: Shape | None = None,
        reference_image_data_url: str | None = None,
        reference_name: str | None = None,
        reference_kind: str | None = None,
        map_placement: MapPlacement | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
        preview_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> WorkflowState:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")
        prompt = " ".join(prompt.split())
        if not prompt:
            raise ValueError("prompt must not be empty")
        if len(prompt) > 500:
            raise ValueError("prompt must not exceed 500 characters")

        state = WorkflowState(
            prompt=prompt,
            request_id=current_request_id(),
            route_preferences=route_preferences or RoutePreferences(),
            start_point=start_point,
            start_label=start_label,
            start_direction_deg=start_direction_deg,
            reference_shape=copy.deepcopy(reference_shape),
            reference_image_data_url=reference_image_data_url,
            reference_name=reference_name,
            reference_kind=reference_kind,
            map_placement=copy.deepcopy(map_placement),
        )
        cfg = get_settings().workflow
        runtime = WorkflowRuntime(
            state,
            max_duration_seconds=cfg.max_duration_seconds,
            max_llm_calls=cfg.max_llm_calls,
            max_events=cfg.max_trace_events,
            event_sink=event_sink,
            preview_sink=preview_sink,
        )
        n = runtime.instrument_nodes(self.nodes)

        # --- linear pass --------------------------------------------------- #
        n["intent"].run(state)
        if intent_override is not None:
            state.intent = copy.deepcopy(intent_override)
            state.history.append(
                {
                    "agent": "intent",
                    "note": "user-confirmed structured interpretation applied",
                }
            )
        if state.intent is not None:
            state.requested_shape = (
                f"text:{state.intent.text}"
                if state.intent.text
                else state.intent.shape
            )
        n["planning"].run(state)
        if state.map_placement is not None:
            state.history.append(
                {
                    "agent": "planning",
                    "note": "user-positioned map footprint applied",
                    "center_lat": state.map_placement.center_lat,
                    "center_lon": state.map_placement.center_lon,
                    "scale_m": state.map_placement.scale_m,
                    "rotation_deg": state.map_placement.rotation_deg,
                    "search_radius_m": state.map_placement.search_radius_m,
                }
            )
        n["shape"].run(state)
        n["placement"].run(state)
        n["preflight"].run(state)
        self._measure_route_variants(state, n)
        self._recover_unroutable_placement(state, n, runtime=runtime)
        self._evaluate_suggestion_candidates(state, n, runtime=runtime)

        threshold = cfg.validation_score_threshold
        max_iter = cfg.max_refinement_iterations

        best_v = state.validation
        best_snapped = copy.deepcopy(state.snapped)
        best_draft = copy.deepcopy(state.route_draft)
        best_errors = list(state.errors)
        if best_v is None:
            state.errors.append("validation produced no score")
            runtime.finish(state)
            return state

        # --- refinement loop ----------------------------------------------- #
        # Geometry tweaks cannot turn the explicit no-road-data preview into a
        # feasible route. Skipping those no-op iterations keeps offline/local
        # use fast and avoids implying that refinement solved road access.
        # Once the run's wall-clock budget is exhausted, further speculative
        # iterations cannot finish before the client timeout anyway; the best
        # measured route so far is kept instead.
        while (
            best_v.on_roads
            and not self._passes_quality(best_v)
            and not runtime.deadline_exceeded()
            and state.iterations < max_iter
        ):
            state.iterations += 1
            log.info(
                "refinement iteration %d (quality gates not met: "
                "score=%.3f/%.2f fidelity=%.3f distance_fit=%.3f closure=%.3f)",
                state.iterations,
                best_v.score,
                threshold,
                best_v.shape_fidelity,
                best_v.distance_fit,
                best_v.closure,
            )

            # Restore the best measured route before the refiner either takes
            # the next road-fit shortlist entry or proposes a measured tweak.
            state.route_draft = copy.deepcopy(best_draft)
            state.snapped = copy.deepcopy(best_snapped)
            state.validation = copy.deepcopy(best_v)
            draft_before = copy.deepcopy(state.route_draft)
            n["refinement"].run(state)     # mutates route_draft params
            if self._draft_params_eq(state.route_draft, draft_before):
                log.info("refinement proposed no change; trying next candidate")
                state.route_draft = draft_before
                state.errors = list(best_errors)
                continue
            n["placement"].run(state)      # recompute waypoints from new params
            self._measure_route_variants(state, n)

            new_v = state.validation
            if new_v is None:
                state.errors.append("refinement validation produced no score")
                state.route_draft = best_draft
                break
            state.history.append(_iter_snapshot(state, new_v, best_v))
            if self._candidate_is_better(new_v, best_v):
                best_v = new_v
                best_snapped = copy.deepcopy(state.snapped)
                best_draft = copy.deepcopy(state.route_draft)
                best_errors = list(state.errors)
            else:
                # Regression: roll back, but keep exploring other bounded
                # rotations/offsets instead of accepting the first failure.
                log.info(
                    "refinement candidate scored below the current best "
                    "(%.3f < %.3f); retaining it for user comparison",
                    new_v.score,
                    best_v.score,
                )
                state.route_draft = copy.deepcopy(best_draft)
                state.snapped = copy.deepcopy(best_snapped)
                state.validation = copy.deepcopy(best_v)
                state.errors = list(best_errors)

        # --- finalise ------------------------------------------------------ #
        state.validation = best_v
        state.snapped = best_snapped
        state.route_draft = best_draft
        state.errors = list(best_errors)

        if best_v.on_roads:
            runtime.run_step("polish.shape", lambda: self._polish_shape(state, n, runtime))
            runtime.run_step("polish.reversals", lambda: self._repair_reversals(state, n, runtime))
            runtime.run_step("polish.detours", lambda: self._repair_detours(state, n, runtime))
            runtime.run_step("polish.contour", lambda: self._reconnect_contour(state, n, runtime))
            runtime.run_step(
                "polish.reference_contour",
                lambda: self._reconnect_contour(state, n, runtime, reference_guided=True),
            )
            contour_inputs_before_late_repairs = self._contour_inputs(state)
            runtime.run_step("polish.turns", lambda: self._repair_turns_directly(state, n, runtime))
            runtime.run_step("polish.graph", lambda: self._repair_contour_with_graph(state, n, runtime))
            # Turn and graph repairs change the incumbent after the original
            # reconnect screens were built. One final candidate per reconnect
            # mode can remove a newly exposed detour without reopening the
            # broad search or changing the drawing reference.
            self._post_graph_reconnect_if_changed(state, n, runtime, contour_inputs_before_late_repairs)
            runtime.run_step("polish.distance", lambda: self._repair_distance(state, n, runtime))

        # If an explicitly requested drawing still fails the recognition
        # gates, route a small city-aware set of simpler shapes.  A replacement
        # is accepted only after it passes the same street, silhouette,
        # distance, and closure checks as the original.
        self._evaluate_fallback_candidates(state, n, runtime=runtime)
        from .tools.route_review import review_finalists
        if state.snapped and state.snapped.snapped and cfg.ai_route_verifier_enabled:
            runtime.run_step("route_review", lambda: review_finalists(state), recoverable=True)
        if state.validation is not None:
            best_v = state.validation
        best_snapped = copy.deepcopy(state.snapped)
        best_draft = copy.deepcopy(state.route_draft)

        state.best_validation = copy.deepcopy(best_v)
        state.best_snapped = copy.deepcopy(best_snapped)
        state.below_threshold = not self._passes_quality(best_v)
        state.history.append(state.snapshot())

        n["export"].run(state)
        final_report = quality_gate_report(
            best_v,
            closed=bool(state.shape and state.shape.closed),
            candidate_shape=state.shape.name if state.shape else None,
            selected_shape=state.shape.name if state.shape else None,
        )
        decision = "verified" if final_report["passed"] else "review"
        log.info(
            (
                "Generation complete: shape=%s in %s, decision=%s, "
                "street matched=%s, overall=%.1f%%, likeness=%.1f%%, "
                "distance=%.2f km, iterations=%d, full candidates=%d, "
                "failed checks=%s, GPX prepared=%s."
            ),
            state.shape.name if state.shape else "unknown",
            state.intent.city if state.intent and state.intent.city else "unspecified city",
            decision,
            "yes" if best_v.on_roads else "no",
            best_v.score * 100,
            best_v.shape_fidelity * 100,
            best_v.actual_distance_km,
            state.iterations,
            len(state.candidates),
            ", ".join(final_report["failed_gates"]) or "none",
            "yes" if state.export else "no",
            extra={
                "event": "generation.completed",
                "shape": state.shape.name if state.shape else None,
                "city": state.intent.city if state.intent else None,
                "sport": state.intent.sport if state.intent else None,
                "candidate_count": len(state.candidates),
                "preflight_count": state.preflight_count,
                "score": best_v.score,
                "fidelity": best_v.shape_fidelity,
                "snapped": bool(state.snapped and state.snapped.snapped),
                "decision": decision,
                "verified": final_report["passed"],
                "failed_gates": final_report["failed_gates"],
                "distance_km": best_v.actual_distance_km,
                "target_distance_km": best_v.target_distance_km,
                "distance_fit": best_v.distance_fit,
                "closure": best_v.closure,
                "route_point_count": best_v.route_point_count,
                "guide_point_count": best_v.guide_point_count,
                "export_mode": "verified" if final_report["passed"] else "user_acceptance",
            },
        )
        runtime.finish(state)
        return state

    def _measurement_worker_count(self, job_count: int) -> int:
        try:
            configured = int(get_settings().workflow.measurement_workers)
        except (TypeError, ValueError):
            configured = 1
        return max(1, min(configured, _MAX_MEASUREMENT_WORKERS, max(1, job_count)))

    @staticmethod
    def _contour_inputs(state: WorkflowState) -> tuple[tuple[LatLon, ...], tuple[LatLon, ...]]:
        """The only geometry the post-graph reconnect screens depend on."""
        return (
            tuple(state.route_draft.waypoints) if state.route_draft else (),
            tuple(state.snapped.points) if state.snapped else (),
        )

    def _post_graph_reconnect_if_changed(
        self,
        state: WorkflowState,
        nodes: Mapping[str, WorkflowNode],
        runtime: WorkflowRuntime,
        previous: tuple[tuple[LatLon, ...], tuple[LatLon, ...]],
    ) -> None:
        if self._contour_inputs(state) == previous:
            return
        runtime.run_step(
            "polish.post_graph_contour",
            lambda: self._reconnect_contour(state, nodes, runtime, limit=1, stage="post_graph"),
        )
        runtime.run_step(
            "polish.post_graph_reference",
            lambda: self._reconnect_contour(
                state, nodes, runtime, reference_guided=True, limit=1, stage="post_graph"
            ),
        )

    def _measure_candidates(
        self,
        jobs: list[tuple[str, WorkflowState, str]],
        nodes: Mapping[str, WorkflowNode],
        *,
        fallback_sources: list[WorkflowState] | None = None,
    ) -> list[tuple[WorkflowState, Exception | None]]:
        """Measure independent candidate pipelines concurrently, in input order.

        Each job owns a prepared clone state, so the shared agents stay
        thread-safe while ORS Directions round trips overlap. Results are
        returned in the caller's priority order together with any candidate
        error, keeping selection semantics identical to the sequential walk
        this replaces. The third tuple element names fallback candidates.
        """
        if not jobs:
            return []
        workers = self._measurement_worker_count(len(jobs))
        if fallback_sources is None:
            measurement_sources: list[WorkflowState] = [job[1] for job in jobs]
        else:
            measurement_sources = fallback_sources
        contexts = [contextvars.copy_context() for _ in jobs]

        def execute(index: int) -> tuple[WorkflowState, Exception | None]:
            label, job_state, shape_name = jobs[index]
            source = measurement_sources[index]
            context = contexts[index]
            try:
                if label == "fallback":
                    measured = context.run(
                        self._measure_fallback_shape,
                        source,
                        shape_name,
                        nodes,
                    )
                    return measured, None
                if label == "road_recovery":
                    def recover_route() -> WorkflowState:
                        Orchestrator._measure_route_variants(job_state, nodes, recoverable=True)
                        return job_state

                    return context.run(recover_route), None
                measured = context.run(
                    self._run_candidate_pipeline, job_state, nodes
                )
                return measured, None
            except (RuntimeError, TypeError, ValueError) as exc:
                # One broken alternative must not abort the whole search; the
                # sequential implementation skipped such candidates too.
                return job_state, exc

        if workers <= 1:
            return [execute(index) for index in range(len(jobs))]
        with ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="gps-art-measure",
        ) as pool:
            return list(pool.map(execute, range(len(jobs))))

    @staticmethod
    def _run_candidate_pipeline(
        state: WorkflowState,
        nodes: Mapping[str, WorkflowNode],
    ) -> WorkflowState:
        """Run shape→placement→preflight→snap→validation on one clone state."""
        Orchestrator._run_candidate_node(nodes["shape"], state)
        Orchestrator._run_candidate_node(nodes["placement"], state)
        preflight = nodes.get("preflight")
        if preflight is not None:
            Orchestrator._run_candidate_node(preflight, state)
        Orchestrator._measure_route_variants(state, nodes, recoverable=True)
        return state

    def _repair_reversals(self, state, nodes, runtime) -> None:
        """Measure one edge-reuse-averse graph challenger for excess backtracking."""
        from .tools import ors_client, street_graph

        cfg = get_settings()
        if (not state.route_draft or not state.snapped or not state.validation
                or not state.validation.on_roads or not cfg.routing.shape_graph_enabled
                or state.validation.reversal_similarity >= cfg.workflow.min_shape_fidelity
                or state.route_draft.anchored_start is not None
                or state.route_draft.preferred_start_direction_deg is not None
                or runtime.deadline_exceeded()):
            return
        graph = street_graph.graph_for_state(state)
        if graph is None or runtime.deadline_exceeded():
            return
        draft = state.route_draft
        proposal = street_graph.shape_route(
            graph, ors_client._subsample(draft.waypoints, closed=draft.closed, max_points=18),
            target_m=draft.target_distance_km * 1000 if draft.target_distance_km else None,
            closed=draft.closed, seconds=cfg.routing.shape_graph_seconds, reuse_penalty=3,
        )
        if proposal is None or runtime.deadline_exceeded():
            return
        best = (state.snapped, state.validation, list(state.errors))
        state.pending_direct_guides = proposal.points
        state.pending_direct_guide_budget = 50
        self._measure_route_variants(state, nodes)
        accepted = state.validation is not None and self._shape_repair_is_better(state.validation, best[1])
        state.history.append({"agent": "reversal_repair", "accepted": accepted,
                              "graph_revision": graph.revision, "graph_expansions": proposal.expanded,
                              "shape_fidelity": state.validation.shape_fidelity if state.validation else None})
        if not accepted:
            state.snapped, state.validation, state.errors = best

    def _repair_detours(self, state, nodes, runtime) -> None:
        from .tools.detour_repair import detour_guides

        if (not state.route_draft or not state.snapped or not state.validation
                or not state.validation.on_roads or self._passes_quality(state.validation)
                or runtime.deadline_exceeded()):
            return
        proposals = detour_guides(state.route_draft.waypoints, state.snapped.points)
        for guides in proposals:
            if runtime.deadline_exceeded():
                break
            best = (state.snapped, state.validation, list(state.errors))
            state.pending_direct_guides = guides
            # Repairs retain the incumbent's street geometry. Give them the
            # same guide budget as graph proposals so rerouting does not
            # discard the road choices that the repair preserved.
            state.pending_direct_guide_budget = 50
            self._measure_route_variants(state, nodes)
            accepted = state.validation is not None and self._shape_repair_is_better(state.validation, best[1])
            state.history.append({"agent": "detour_repair", "accepted": accepted,
                                  "shape_fidelity": state.validation.shape_fidelity
                                  if state.validation else None})
            if not accepted:
                state.snapped, state.validation, state.errors = best
            if self._passes_quality(state.validation):
                break

    def _reconnect_contour(
        self,
        state,
        nodes,
        runtime,
        *,
        reference_guided: bool = False,
        limit: int = 2,
        stage: str = "initial",
    ) -> None:
        from .tools.detour_repair import reconnect_guides

        if (not state.route_draft or not state.snapped or not state.validation
                or not state.validation.on_roads or self._passes_quality(state.validation)
                or runtime.deadline_exceeded()):
            return
        proposals = reconnect_guides(
            state.route_draft.waypoints,
            state.snapped.points,
            limit=limit,
            reference_guided=reference_guided,
        )
        for guides in proposals:
            if runtime.deadline_exceeded():
                break
            best = (state.snapped, state.validation, list(state.errors))
            state.pending_direct_guides = guides
            state.pending_direct_guide_budget = 50
            self._measure_route_variants(state, nodes)
            accepted = state.validation is not None and self._shape_repair_is_better(state.validation, best[1])
            state.history.append({"agent": "contour_reference" if reference_guided else "contour_reconnect",
                                  "stage": stage,
                                  "accepted": accepted,
                                  "shape_fidelity": state.validation.shape_fidelity
                                  if state.validation else None})
            if not accepted:
                state.snapped, state.validation, state.errors = best
            if self._passes_quality(state.validation):
                break

    def _repair_turns_directly(self, state, nodes, runtime) -> None:
        """Try a few reference-guided turn repairs without a graph detour.

        A local graph proposal can return to the incumbent street path even
        when an original-contour guide steers Directions to a better turn.
        Screen the bounded turning windows cheaply, then keep only genuinely
        better connected ORS routes. The drawing itself never changes.
        """
        from .tools import shape_similarity
        from .tools.detour_repair import turning_repair_guides

        cfg = get_settings().workflow
        if (not state.route_draft or not state.route_draft.closed
                or not state.snapped or not state.validation
                or not state.validation.on_roads
                or state.validation.turning_similarity >= cfg.min_shape_fidelity
                or state.route_draft.anchored_start is not None
                or state.route_draft.preferred_start_direction_deg is not None
                or runtime.deadline_exceeded()):
            return
        reference = state.route_draft.waypoints
        baseline = shape_similarity.similarity_diagnostics_between_routes(
            reference, state.snapped.points,
        )
        screened = []
        for index, guides in enumerate(
            turning_repair_guides(reference, state.snapped.points), start=1,
        ):
            proxy = shape_similarity.similarity_diagnostics_between_routes(
                reference, guides,
            )
            if (proxy.turning_similarity <= baseline.turning_similarity + 0.002
                    or proxy.fidelity < 0.98 * baseline.fidelity):
                continue
            screened.append((proxy.fidelity + proxy.turning_similarity
                             + proxy.length_similarity, index, guides, proxy))
        screened.sort(key=lambda row: (-row[0], row[1]))
        for _, index, guides, proxy in screened[:3]:
            if runtime.deadline_exceeded():
                return
            best = (state.snapped, state.validation, list(state.errors))
            state.pending_direct_guides = guides
            state.pending_direct_guide_budget = 50
            self._measure_route_variants(state, nodes)
            accepted = bool(state.validation and self._shape_repair_is_better(
                state.validation, best[1],
            ))
            state.history.append({
                "agent": "turning_direct", "window": index,
                "proxy_fidelity": proxy.fidelity,
                "proxy_turning": proxy.turning_similarity,
                "accepted": accepted,
                "shape_fidelity": state.validation.shape_fidelity if state.validation else None,
            })
            if not accepted:
                state.snapped, state.validation, state.errors = best
            if self._passes_quality(state.validation):
                return

    def _repair_contour_with_graph(self, state, nodes, runtime) -> None:
        """Measure up to three local graph repairs after reconnection stalls.

        The existing reconnection passes identify promising weak windows, and
        equal-arc turning diagnostics add bounded candidates around separated
        high-error phases when the turn gate fails.  The local graph chooses a
        contour-following street path inside one window. An accepted repair
        can expose another weak section, so at most two recomputed follow-ups
        are allowed while either turning or detour length still fails.
        Endpoints and every guide outside each window stay fixed;
        Directions still supplies the authoritative route.
        """
        from .tools import geo, shape_similarity, street_graph
        from .tools.detour_repair import reconnect_guides, turning_repair_guides

        cfg = get_settings()
        if (not state.route_draft or not state.snapped or not state.validation
                or not state.validation.on_roads or not cfg.routing.shape_graph_enabled
                or (state.validation.turning_similarity >= cfg.workflow.min_shape_fidelity
                    and state.validation.length_similarity >= cfg.workflow.min_shape_fidelity)
                or state.route_draft.anchored_start is not None
                or state.route_draft.preferred_start_direction_deg is not None
                or runtime.deadline_exceeded()):
            return
        graph = street_graph.graph_for_state(state)
        if graph is None or runtime.deadline_exceeded():
            return

        reference = state.route_draft.waypoints
        for attempt in range(1, 4):
            if runtime.deadline_exceeded():
                return
            route = state.snapped.points
            baseline = shape_similarity.similarity_diagnostics_between_routes(reference, route)
            candidates = (
                [(candidate, True) for candidate in turning_repair_guides(reference, route)]
                if state.validation.turning_similarity < cfg.workflow.min_shape_fidelity
                else []
            )
            candidates.extend(
                (candidate, False) for candidate in reconnect_guides(reference, route)
            )
            candidates.extend(
                (candidate, False)
                for candidate in reconnect_guides(reference, route, reference_guided=True)
            )
            screened = []
            seen = set()
            screened_guides = set()
            for candidate, phase_targeted in candidates:
                if runtime.deadline_exceeded():
                    break
                signature = tuple(candidate)
                if signature in seen:
                    continue
                seen.add(signature)

                prefix = 0
                while (prefix < min(len(candidate), len(route))
                       and candidate[prefix] == route[prefix]):
                    prefix += 1
                suffix = 0
                while (suffix < min(len(candidate), len(route)) - prefix
                       and candidate[-1 - suffix] == route[-1 - suffix]):
                    suffix += 1
                start = max(0, prefix - 1)
                end = len(route) - suffix
                middle_end = len(candidate) - suffix
                if not (0 <= start < end < len(route)):
                    continue
                local_guides = [route[start], *candidate[prefix:middle_end], route[end]]
                if len(local_guides) < 2:
                    continue
                target_m = (
                    0.9 * geo.path_distance_m(route[start : end + 1])
                    if phase_targeted
                    else geo.path_distance_m(local_guides)
                )
                guide_variants = [(local_guides, False)]
                if phase_targeted:
                    guide_variants.append((_densify_local_guides(local_guides), True))
                for graph_guides, dense_guides in guide_variants:
                    proposal = street_graph.shape_route(
                        graph,
                        graph_guides,
                        target_m=max(150.0, target_m),
                        closed=False,
                        seconds=min(0.6, cfg.routing.shape_graph_seconds),
                        max_expansions=12000,
                    )
                    if proposal is None:
                        continue
                    # Keep the incumbent street endpoints on both sides of the local
                    # graph path. This makes the edit local even when the graph's
                    # nearest node is tens of metres from an endpoint.
                    guides = route[:start + 1] + proposal.points + route[end:]
                    guide_signature = tuple(guides)
                    if guide_signature in screened_guides:
                        continue
                    screened_guides.add(guide_signature)
                    diagnostics = shape_similarity.similarity_diagnostics_between_routes(
                        reference, guides,
                    )
                    proxy_progress = _promising_graph_proxy(baseline, diagnostics)
                    if proxy_progress is None:
                        continue
                    proxy_rank, proxy_bottleneck = proxy_progress
                    screened.append((proxy_rank, proxy_bottleneck, diagnostics.fidelity,
                                     diagnostics.turning_similarity,
                                     diagnostics.length_similarity, guides, proposal,
                                     phase_targeted, dense_guides))

            if not screened or runtime.deadline_exceeded():
                return
            baseline_bottleneck = min(
                getattr(baseline, metric) for metric in _GRAPH_BOTTLENECK_COMPONENTS
            )
            near_gate = baseline_bottleneck >= 0.95 * cfg.workflow.min_shape_fidelity
            balanced_winner = max(
                screened,
                key=lambda row: _graph_proxy_priority(
                    row[0], row[1], row[2], row[3], row[4], near_gate=False,
                ),
            )
            selection_mode = "balanced"
            winner = balanced_winner
            if near_gate:
                bottleneck_winner = max(
                    screened,
                    key=lambda row: _graph_proxy_priority(
                        row[0], row[1], row[2], row[3], row[4], near_gate=True,
                    ),
                )
                winner = bottleneck_winner
                selection_mode = "bottleneck"
                if _balanced_proxy_overrides(
                    balanced_rank=balanced_winner[0],
                    bottleneck_rank=bottleneck_winner[0],
                ):
                    winner = balanced_winner
                    selection_mode = "balanced_override"
            proxy_rank, proxy_bottleneck, proxy_fidelity, proxy_turning, _, guides, proposal, phase_targeted, dense_guides = winner
            best = (state.snapped, state.validation, list(state.errors))
            state.pending_direct_guides = guides
            state.pending_direct_guide_budget = 50
            self._measure_route_variants(state, nodes)
            accepted = state.validation is not None and self._shape_repair_is_better(
                state.validation, best[1],
            )
            state.history.append({
                "agent": "contour_graph",
                "attempt": attempt,
                "accepted": accepted,
                "graph_revision": graph.revision,
                "graph_expansions": proposal.expanded,
                "proxy_rank": proxy_rank,
                "proxy_bottleneck": proxy_bottleneck,
                "proxy_fidelity": proxy_fidelity,
                "proxy_turning": proxy_turning,
                "selection_mode": selection_mode,
                "phase_targeted": phase_targeted,
                "dense_guides": dense_guides,
                "shape_fidelity": state.validation.shape_fidelity if state.validation else None,
            })
            if not accepted:
                state.snapped, state.validation, state.errors = best
                return
            if (self._passes_quality(state.validation)
                    or (state.validation.turning_similarity >= cfg.workflow.min_shape_fidelity
                        and state.validation.length_similarity >= cfg.workflow.min_shape_fidelity)):
                return

    def _repair_distance(self, state, nodes, runtime) -> None:
        """Correct a late shape repair that pushed an otherwise usable route off target.

        Shape polish and contour repairs run after the normal refinement loop.
        They can improve the silhouette while shortening the route below the
        distance gate. Measure at most four scaled drawings through Directions,
        and retain one only if it restores distance without losing recognition
        cues or the user's fixed map footprint.
        """
        incumbent = state.validation
        draft = state.route_draft
        snapped = state.snapped
        if (incumbent is None or draft is None or snapped is None or not incumbent.on_roads
                or incumbent.distance_fit >= distance_fit_minimum(incumbent.target_distance_km)
                or state.map_placement is not None
                or draft.target_distance_km is None or draft.target_distance_km <= 0
                or snapped.total_distance_m <= 0 or runtime.deadline_exceeded()):
            return
        ratio = draft.target_distance_km * 1000 / snapped.total_distance_m
        if not math.isfinite(ratio) or abs(ratio - 1.0) < 0.02:
            return

        original = (copy.deepcopy(draft), copy.deepcopy(snapped),
                    copy.deepcopy(incumbent), list(state.errors))
        # A bridge or one-way street can change the routed distance abruptly.
        # Probe the interval before the square-root correction instead of
        # jumping immediately to a scale that may destroy the silhouette.
        damped = math.sqrt(ratio)
        factors = (1 + (damped - 1) / 3, 1 + 2 * (damped - 1) / 3,
                   damped, ratio)
        tried_scales: set[float] = set()
        for factor in factors:
            if runtime.deadline_exceeded():
                break
            scale = min(200_000.0, max(25.0, original[0].scale_m * min(1.4, max(0.7, factor))))
            if round(scale, 1) in tried_scales:
                continue
            tried_scales.add(round(scale, 1))
            state.route_draft = copy.deepcopy(original[0])
            state.route_draft.scale_m = scale
            state.pending_direct_guides = None
            state.pending_direct_guide_budget = None
            nodes["placement"].run(state)
            self._measure_route_variants(state, nodes)
            trial = state.validation
            accepted = bool(trial and self._distance_repair_is_better(trial, original[2]))
            state.history.append({
                "agent": "distance_repair", "accepted": accepted,
                "scale_factor": scale / original[0].scale_m,
                "distance_km": trial.actual_distance_km if trial else None,
                "distance_fit": trial.distance_fit if trial else None,
                "shape_fidelity": trial.shape_fidelity if trial else None,
                "failed_gates": quality_gate_report(trial, closed=draft.closed)["failed_gates"]
                if trial else None,
            })
            if accepted:
                return
            state.route_draft = copy.deepcopy(original[0])
            state.snapped = copy.deepcopy(original[1])
            state.validation = copy.deepcopy(original[2])
            state.errors = list(original[3])

    @staticmethod
    def _distance_repair_is_better(candidate, incumbent) -> bool:
        """Require the distance gate without trading away the drawing."""
        if (not candidate.on_roads or candidate.distance_fit
                < distance_fit_minimum(candidate.target_distance_km)):
            return False
        if passes_quality_gates(candidate, closed=True):
            return True
        if candidate.shape_fidelity < max(0.7, incumbent.shape_fidelity - 0.05):
            return False
        if candidate.score < incumbent.score - 0.03:
            return False
        shape_components = (
            "spatial_similarity", "coverage_similarity", "turning_similarity",
            "landmark_similarity", "reversal_similarity", "length_similarity",
            "extent_similarity",
        )
        if any(getattr(candidate, component) < getattr(incumbent, component) - 0.05
               for component in shape_components):
            return False
        before = quality_gate_report(incumbent, closed=True)
        after = quality_gate_report(candidate, closed=True)
        shape_gates = {gate["key"] for gate in before["gates"] if gate["group"] == "shape"}
        new_shape_failures = (set(after["failed_gates"]) - set(before["failed_gates"])) & shape_gates
        return not new_shape_failures

    def _polish_shape(self, state, nodes, runtime) -> None:
        """Screen a small neighbourhood of the best *routed* placement."""
        from types import SimpleNamespace

        from .agents.placement_agent import PlacementAgent
        from .agents.preflight_agent import PreflightAgent
        from .tools import ors_client, shape_similarity, street_graph

        cfg = get_settings().workflow
        limit = min(4, max(0, cfg.shape_polish_candidates))
        if (not limit or not cfg.preflight_adaptive or not state.preflight_count
                or not state.route_draft or not state.validation or not state.intent
                or not state.validation.on_roads or self._passes_quality(state.validation)
                or runtime.deadline_exceeded()):
            return
        preflight = PreflightAgent()
        drafts = preflight._refined_drafts(
            state, [state.route_draft], [SimpleNamespace(candidate_index=0)], 16, 2,
        )
        if not drafts:
            return
        results = ors_client.preflight_route_candidates(
            [draft.waypoints for draft in drafts], sport=state.intent.sport,
            closed=state.route_draft.closed, max_guide_points=cfg.preflight_guide_points,
        )
        state.preflight_count += len(drafts)
        if not results:
            return
        results = preflight._valid_results(results, len(drafts))
        shortlisted = preflight._diverse_shortlist(results, drafts, limit)
        for result in shortlisted:
            if runtime.deadline_exceeded():
                break
            best = (state.route_draft, state.snapped, state.validation, list(state.errors))
            state.route_draft = drafts[result.candidate_index]
            self._measure_route_variants(state, nodes)
            state.history.append({"agent": "shape_polish", "proxy_score": result.score,
                                  "shape_fidelity": state.validation.shape_fidelity
                                  if state.validation else None})
            if state.validation is None or not self._shape_repair_is_better(state.validation, best[2]):
                state.route_draft, state.snapped, state.validation, state.errors = best
            if self._passes_quality(state.validation):
                break

        # A routed local candidate may reveal a much better failed component
        # even when its aggregate rank loses. Explore that measured location
        # only after preserving the established four-candidate search. These
        # eight placements use the local graph, not another provider Snap call.
        component_seed_result = self._component_polish_seed(state)
        forced_draft = None
        forced_score = None
        if (component_seed_result is not None and not self._passes_quality(state.validation)
                and not runtime.deadline_exceeded()):
            component_seed, measured_km = component_seed_result
            projector = PlacementAgent()
            step = min(80.0, max(25.0, component_seed.scale_m * 0.035))
            target_km = component_seed.target_distance_km or measured_km
            direction = 1 if measured_km <= target_km else -1
            scale_factors = tuple(1 + direction * change for change in (0.10, 0.20, 0.25))
            variants = ((5, 0, step, 1.0),
                        *((5, 0, step, factor) for factor in scale_factors),
                        (-5, 0, -step, 1.0), (5, 0, -step, 1.0),
                        (-5, 0, step, 1.0), (5, step, 0, 1.0))
            component_drafts = []
            seen = {preflight._signature(draft) for draft in drafts}
            for rotation, north, east, scale_factor in variants:
                draft = copy.copy(component_seed)
                draft.rotation_deg = (draft.rotation_deg + rotation) % 360
                draft.scale_m *= scale_factor
                draft.lat_offset_m += north
                draft.lon_offset_m += east
                draft.waypoints = projector.project(state.shape, draft)
                signature = preflight._signature(draft)
                if signature not in seen:
                    seen.add(signature)
                    component_drafts.append(draft)
            state.preflight_count += len(component_drafts)
            state.history.append({"agent": "component_polish", "phase": "seed",
                                  "rotation_deg": component_seed.rotation_deg,
                                  "lat_offset_m": component_seed.lat_offset_m,
                                  "lon_offset_m": component_seed.lon_offset_m,
                                  "placements": len(component_drafts)})
            graph = street_graph.graph_for_state(state)
            screened = []
            if graph is not None:
                for draft in component_drafts:
                    if runtime.deadline_exceeded():
                        break
                    proposal = street_graph.shape_route(
                        graph,
                        ors_client._subsample(draft.waypoints, closed=draft.closed, max_points=18),
                        target_m=draft.target_distance_km * 1000 if draft.target_distance_km else None,
                        closed=draft.closed, seconds=min(0.6, get_settings().routing.shape_graph_seconds),
                        max_expansions=12000,
                    )
                    if proposal is None:
                        continue
                    diagnostics = shape_similarity.similarity_diagnostics_between_routes(
                        draft.waypoints, proposal.points, n=64, closed_sample_floor=64,
                    )
                    screened.append((diagnostics.fidelity, draft))
            if screened:
                forced_score, forced_draft = max(screened, key=lambda row: row[0])
                state.history.append({"agent": "component_polish", "phase": "graph_screen",
                                      "rotation_deg": forced_draft.rotation_deg,
                                      "lat_offset_m": forced_draft.lat_offset_m,
                                      "lon_offset_m": forced_draft.lon_offset_m,
                                      "graph_fidelity": forced_score})
        if (forced_draft is not None and not self._passes_quality(state.validation)
                and not runtime.deadline_exceeded()):
            best = (state.route_draft, state.snapped, state.validation, list(state.errors))
            state.route_draft = forced_draft
            self._measure_route_variants(state, nodes)
            accepted = state.validation is not None and self._shape_repair_is_better(state.validation, best[2])
            state.history.append({"agent": "shape_polish", "component_challenger": True,
                                  "graph_fidelity": forced_score, "accepted": accepted,
                                  "shape_fidelity": state.validation.shape_fidelity
                                  if state.validation else None})
            if not accepted:
                state.route_draft, state.snapped, state.validation, state.errors = best

    @staticmethod
    def _component_polish_seed(state: WorkflowState):
        """Return a usable measured placement that improves a failed shape cue."""
        if not state.validation or not state.route_draft or not state.shape:
            return None
        threshold = get_settings().workflow.min_shape_fidelity
        components = ("spatial_similarity", "coverage_similarity", "turning_similarity",
                      "landmark_similarity", "length_similarity", "extent_similarity",
                      "reversal_similarity")
        failed = [name for name in components if getattr(state.validation, name) < threshold]
        if not failed:
            return None
        candidates = [candidate for candidate in state.candidates
                      if candidate.shape_name == state.shape.name and candidate.validation.on_roads
                      and candidate.validation.distance_fit >= distance_fit_minimum(candidate.validation.target_distance_km)
                      and (not candidate.closed or candidate.validation.closure >= 0.6)]
        if not candidates:
            return None
        seed = max(candidates, key=lambda candidate: max(
            getattr(candidate.validation, name) - getattr(state.validation, name) for name in failed
        ))
        improvement = max(getattr(seed.validation, name) - getattr(state.validation, name) for name in failed)
        if improvement < 0.02:
            return None
        draft = copy.copy(state.route_draft)
        draft.rotation_deg = seed.rotation_deg
        draft.scale_m = seed.scale_m
        draft.lat_offset_m = seed.lat_offset_m
        draft.lon_offset_m = seed.lon_offset_m
        return draft, seed.validation.actual_distance_km

    @staticmethod
    def _measure_route_variants(
        state: WorkflowState,
        nodes: Mapping[str, WorkflowNode],
        *,
        recoverable: bool = False,
    ) -> None:
        """Measure graph and original guides against the same unchanged drawing.

        At most one additional Directions request per graph proposal. Both
        evaluations remain in candidates, including the losing street route.
        """
        def run(name: str) -> None:
            if recoverable:
                Orchestrator._run_candidate_node(nodes[name], state)
            else:
                nodes[name].run(state)

        run("snap")
        run("validation")
        if state.pending_direct_guides is None:
            return
        incumbent = state.validation
        snapped = state.snapped
        errors = list(state.errors)
        run("snap")
        run("validation")
        if incumbent is not None and (
            state.validation is None
            or not Orchestrator._candidate_is_better(state.validation, incumbent)
        ):
            state.validation = incumbent
            state.snapped = snapped
            state.errors = errors

    @staticmethod
    def _run_candidate_node(node: WorkflowNode, state: WorkflowState) -> WorkflowState:
        """Run one speculative node without making its failure terminal."""

        recoverable = getattr(node, "run_recoverable", None)
        if callable(recoverable):
            return recoverable(state)
        return node.run(state)

    @staticmethod
    def _measurement_shell(source: WorkflowState) -> WorkflowState:
        """Clone exactly what an independent candidate measurement mutates.

        A whole-state ``deepcopy`` would duplicate every previously evaluated
        polyline carried by the parent state, only for those lists to be reset
        immediately. The shell shares read-only references (prompt, preferences,
        geocoded context) and gives the clone private copies of the containers
        and nested records the candidate pipeline writes to.
        """
        shell = copy.copy(source)
        shell.history = []
        shell.errors = []
        shell.placement_candidates = []
        shell.pending_direct_guides = None
        shell.pending_direct_guide_budget = None
        shell.preflight_candidates = []
        shell.candidates = []
        shell.intent = (
            copy.deepcopy(source.intent) if source.intent is not None else None
        )
        shell.plan = copy.deepcopy(source.plan) if source.plan is not None else None
        if source.reference_shape is not None:
            shell.reference_shape = copy.deepcopy(source.reference_shape)
        shell.workflow = None
        return shell

    @staticmethod
    def _is_connected(candidate_state: WorkflowState) -> bool:
        validation = candidate_state.validation
        return bool(
            validation
            and validation.on_roads
            and candidate_state.snapped
            and candidate_state.snapped.snapped
        )

    def _recover_unroutable_placement(
        self,
        state: WorkflowState,
        nodes: Mapping[str, WorkflowNode],
        runtime: WorkflowRuntime | None = None,
    ) -> None:
        """Try the remaining road-ranked placements when Directions rejects the first.

        Snap preflight proves proximity to roads, not connectivity between every
        waypoint.  The former pipeline stopped immediately when the top-ranked
        placement could not be routed and exposed its straight-line guide. All
        shortlisted placements are measured concurrently, then the first
        road-connected one in preflight priority order wins — exactly the choice
        the sequential walk made, without paying its summed latency.
        """

        validation = state.validation
        primary_is_connected = bool(
            validation
            and validation.on_roads
            and state.snapped
            and state.snapped.snapped
        )
        if (
            validation is None
            or primary_is_connected
            or not state.placement_candidates
        ):
            return

        primary_draft = copy.deepcopy(state.route_draft)
        primary_snapped = copy.deepcopy(state.snapped)
        primary_validation = copy.deepcopy(validation)
        primary_errors = list(state.errors)

        queued = [copy.deepcopy(draft) for draft in state.placement_candidates]
        jobs: list[tuple[str, WorkflowState, str]] = []
        for draft in queued:
            job_state = self._measurement_shell(state)
            job_state.candidate_count = 0
            job_state.preflight_count = 0
            job_state.errors = list(primary_errors)
            job_state.route_draft = copy.deepcopy(draft)
            jobs.append(("road_recovery", job_state, ""))

        results = self._measure_candidates(jobs, nodes)

        connected_index: int | None = None
        total_candidate_count = 0
        total_preflight_count = 0
        evaluated: list = []
        history_entries: list[dict] = []
        for attempt, (candidate_state, error) in enumerate(results, start=1):
            candidate_draft = candidate_state.route_draft
            entry = {
                "agent": "road_recovery",
                "attempt": attempt,
                "rotation_deg": (
                    candidate_draft.rotation_deg if candidate_draft else None
                ),
                "scale_m": candidate_draft.scale_m if candidate_draft else None,
                "preflight_score": (
                    candidate_draft.preflight_score if candidate_draft else None
                ),
            }
            if error is not None:
                entry.update({"on_roads": False, "error_type": type(error).__name__})
                log.warning(
                    "road recovery candidate %d failed with %s; trying next placement",
                    attempt,
                    type(error).__name__,
                )
                history_entries.append(entry)
                continue
            total_candidate_count += candidate_state.candidate_count
            total_preflight_count += candidate_state.preflight_count
            evaluated.extend(candidate_state.candidates)
            connected = self._is_connected(candidate_state)
            entry["on_roads"] = connected
            history_entries.append(entry)
            if connected and connected_index is None:
                connected_index = attempt - 1

        state.candidate_count += total_candidate_count
        state.preflight_count += total_preflight_count
        state.candidates.extend(evaluated)
        state.history.extend(history_entries)

        if connected_index is None:
            state.route_draft = primary_draft
            state.snapped = primary_snapped
            state.validation = primary_validation
            state.errors = primary_errors
            state.placement_candidates = []
            log.warning(
                "road recovery exhausted %d additional placements; no connected route found",
                len(results),
            )
            return

        winner = results[connected_index][0]
        state.route_draft = winner.route_draft
        state.snapped = winner.snapped
        state.validation = winner.validation
        state.errors = winner.errors
        # Placements ranked behind the winner were never consumed by the
        # sequential walk; keep them available for refinement.
        state.placement_candidates = [
            copy.deepcopy(result_state.route_draft)
            for result_state, error in results[connected_index + 1 :]
            if error is None and result_state.route_draft is not None
        ]
        log.info(
            "road recovery found a connected placement on attempt %d "
            "(preflight=%s)",
            connected_index + 1,
            winner.route_draft.preflight_score if winner.route_draft else None,
        )

    def _evaluate_fallback_candidates(
        self,
        state: WorkflowState,
        nodes: Mapping[str, WorkflowNode],
        runtime: WorkflowRuntime | None = None,
    ) -> None:
        """Handle unavailable-source substitutions without replacing explicit shapes."""
        validation = state.validation
        plan = state.plan
        intent = state.intent
        shape = state.shape
        requested = state.requested_shape
        if (
            validation is None
            or plan is None
            or intent is None
            or shape is None
            or not requested
        ):
            return
        source_substitution = requested.casefold() != shape.name.casefold()
        if self._passes_quality(validation):
            if source_substitution:
                state.fit_decision = FitDecision(
                    requested_shape=requested,
                    selected_shape=shape.name,
                    substituted=True,
                    requested_score=0.0,
                    requested_fidelity=0.0,
                    selected_score=validation.score,
                    selected_fidelity=validation.shape_fidelity,
                    candidates_tested=[shape.name],
                    reasons=[
                        (
                            f"We don’t have a reliable one-line version of {requested.title()} "
                            "yet, so we couldn’t match it to streets."
                        ),
                        (
                            f"{shape.name.title()} worked best on nearby streets, with a "
                            f"{validation.shape_fidelity:.0%} shape match."
                        ),
                    ],
                )
            return

        # Keep an explicitly selected drawing even when one automatic
        # benchmark misses. The automatic report still identifies the weak
        # components, but the user—not a simpler fallback template—decides
        # whether the measured route is recognisable enough to accept.
        if not source_substitution:
            state.fit_decision = FitDecision(
                requested_shape=requested,
                selected_shape=shape.name,
                substituted=False,
                requested_score=validation.score,
                requested_fidelity=validation.shape_fidelity,
                selected_score=validation.score,
                selected_fidelity=validation.shape_fidelity,
                candidates_tested=[shape.name],
                reasons=self._fit_reasons(validation)
                + [
                    "The requested drawing was retained for your review; automatic "
                    "benchmarks inform the decision but do not replace your selected shape."
                ],
            )
            log.warning(
                (
                    "Explicit shape %s retained for user review: overall=%.1f%%, "
                    "likeness=%.1f%%, failed checks=%s."
                ),
                shape.name,
                validation.score * 100,
                validation.shape_fidelity * 100,
                ", ".join(
                    quality_gate_report(
                        validation,
                        closed=shape.closed,
                        candidate_shape=shape.name,
                        selected_shape=shape.name,
                    )["failed_gates"]
                ) or "none",
                extra={
                    "event": "route.explicit_shape.retained",
                    "shape": shape.name,
                    "city": intent.city,
                    "sport": intent.sport,
                    "decision": "review",
                    "verified": False,
                    "score": validation.score,
                    "fidelity": validation.shape_fidelity,
                },
            )
            return

        requested_score = validation.score
        requested_fidelity = validation.shape_fidelity
        requested_shape = shape.name
        primary_state = copy.deepcopy(state)
        attempted: list[str] = []
        passing_alternative: WorkflowState | None = None
        best_below_target: WorkflowState | None = None

        if validation.on_roads:
            alternative_names = [
                candidate_name
                for candidate_name in plan.fallback_candidates
                if candidate_name != shape.name
            ]
            # Near the deadline further replacement routings cannot finish
            # inside the client timeout; keep the requested route instead.
            if runtime is not None and runtime.deadline_exceeded():
                log.warning(
                    "fallback search skipped: workflow deadline already exceeded"
                )
                alternative_names = []
            jobs: list[tuple[str, WorkflowState, str]] = []
            for candidate_name in alternative_names:
                # The fallback branch of ``_measure_candidates`` sources every
                # measurement from ``primary_state`` and passes the candidate
                # name separately, so the job state is a shared placeholder.
                jobs.append(("fallback", primary_state, candidate_name))

            results = self._measure_candidates(
                jobs,
                nodes,
                fallback_sources=[primary_state] * len(jobs),
            )

            for candidate_name, (candidate, _error) in zip(
                [job[2] for job in jobs],
                results,
                strict=True,
            ):
                attempted.append(candidate_name)
                state.candidate_count += candidate.candidate_count
                state.preflight_count += candidate.preflight_count
                state.preflight_candidates.extend(
                    candidate.preflight_candidates
                )
                state.candidates.extend(candidate.candidates)
                candidate_validation = candidate.validation
                if candidate_validation is None:
                    continue
                state.history.append(
                    {
                        "agent": "fallback_search",
                        "iteration": len(attempted),
                        "shape": candidate_name,
                        "score": candidate_validation.score,
                        "fidelity": candidate_validation.shape_fidelity,
                        "distance_fit": candidate_validation.distance_fit,
                        "closure": candidate_validation.closure,
                        "on_roads": candidate_validation.on_roads,
                        "issues": candidate_validation.issues,
                    }
                )
                if self._passes_quality(candidate_validation):
                    passing_alternative = candidate
                    break
                if (
                    best_below_target is None
                    or (
                        best_below_target.validation is not None
                        and self._candidate_is_better(
                            candidate_validation,
                            best_below_target.validation,
                        )
                    )
                ):
                    best_below_target = candidate

        if passing_alternative is not None:
            selected_validation = passing_alternative.validation
            selected_shape = passing_alternative.shape
            if selected_validation is None or selected_shape is None:
                return
            preserved_history = list(state.history)
            preserved_candidate_count = state.candidate_count
            preserved_preflight_count = state.preflight_count
            state.shape = copy.deepcopy(passing_alternative.shape)
            state.route_draft = copy.deepcopy(passing_alternative.route_draft)
            state.placement_candidates = copy.deepcopy(
                passing_alternative.placement_candidates
            )
            state.snapped = copy.deepcopy(passing_alternative.snapped)
            state.validation = copy.deepcopy(selected_validation)
            state.errors = list(passing_alternative.errors)
            state.history = preserved_history
            state.candidate_count = preserved_candidate_count
            state.preflight_count = preserved_preflight_count
            intent.shape = selected_shape.name
            plan.suggested_shape = selected_shape.name
            primary_reasons = self._fit_reasons(primary_state.validation)
            if source_substitution:
                primary_reasons.insert(
                    0,
                    (
                        f"We don’t have a reliable one-line version of {requested.title()} yet, "
                        f"and {requested_shape.title()} didn’t fit these streets either."
                    ),
                )
            state.fit_decision = FitDecision(
                requested_shape=requested,
                selected_shape=selected_shape.name,
                substituted=True,
                requested_score=requested_score,
                requested_fidelity=requested_fidelity,
                selected_score=selected_validation.score,
                selected_fidelity=selected_validation.shape_fidelity,
                candidates_tested=attempted,
                reasons=[
                    *primary_reasons,
                    (
                        f"{selected_shape.name.title()} was the strongest street route: "
                        f"{selected_validation.shape_fidelity:.0%} shape match, "
                        f"{selected_validation.distance_fit:.0%} distance match, and "
                        f"{selected_validation.closure:.0%} return-to-start match."
                    ),
                ],
            )
            log.info(
                "fallback search substituted %s -> %s (fidelity %.3f -> %.3f)",
                requested_shape,
                selected_shape.name,
                requested_fidelity,
                selected_validation.shape_fidelity,
            )
            return

        # Keep the requested route selected when no alternative reaches the
        # recommended targets. Every measured route remains in state.candidates
        # for comparison, editing, and optional export.
        state.shape = primary_state.shape
        state.route_draft = primary_state.route_draft
        state.snapped = primary_state.snapped
        state.validation = primary_state.validation
        state.errors = primary_state.errors
        reasons = self._fit_reasons(primary_state.validation)
        if source_substitution:
            reasons.insert(
                0,
                (
                    f"We don’t have a reliable one-line version of {requested.title()} yet, "
                    f"and {requested_shape.title()} didn’t fit these streets either."
                ),
            )
        if not validation.on_roads:
            reasons.append(
                "We couldn’t match any of the alternatives to connected streets."
            )
        elif attempted:
            best_note = ""
            if (
                best_below_target is not None
                and best_below_target.validation is not None
            ):
                best_note = (
                    f" The closest alternative had a "
                    f"{best_below_target.validation.shape_fidelity:.0%} shape match."
                )
            reasons.append(
                f"We also tried {', '.join(attempted)}, but none was a clear enough match."
                f"{best_note} You can still compare and edit them."
            )
        state.fit_decision = FitDecision(
            requested_shape=requested,
            selected_shape=requested_shape,
            substituted=False,
            requested_score=requested_score,
            requested_fidelity=requested_fidelity,
            selected_score=requested_score,
            selected_fidelity=requested_fidelity,
            candidates_tested=attempted,
            reasons=reasons,
        )

    def _measure_fallback_shape(
        self,
        source: WorkflowState,
        shape_name: str,
        nodes: Mapping[str, WorkflowNode],
    ) -> WorkflowState:
        """Route one simple shape and one targeted second placement."""
        candidate = self._measurement_shell(source)
        if candidate.intent is None:
            return candidate
        candidate.intent.shape = shape_name
        candidate.shape = None
        candidate.route_draft = None
        candidate.snapped = None
        candidate.validation = None
        candidate.export = None
        candidate.best_validation = None
        candidate.best_snapped = None
        candidate.fit_decision = None
        candidate.placement_candidates = []
        candidate.preflight_candidates = []
        candidate.candidates = []
        candidate.history = []
        candidate.errors = [
            error
            for error in candidate.errors
            if not error.startswith(("shape:", "snap:", "export:"))
        ]
        candidate.candidate_count = 0
        candidate.preflight_count = 0
        candidate.iterations = 0

        self._run_candidate_node(nodes["shape"], candidate)
        self._run_candidate_node(nodes["placement"], candidate)
        preflight = nodes.get("preflight")
        if preflight is not None:
            self._run_candidate_node(preflight, candidate)
        Orchestrator._measure_route_variants(candidate, nodes, recoverable=True)
        best = copy.deepcopy(candidate)
        if candidate.validation is None or self._passes_quality(candidate.validation):
            return best
        if not candidate.validation.on_roads or candidate.route_draft is None:
            return best

        trial = copy.deepcopy(candidate)
        trial.candidate_count = 0
        trial.preflight_count = 0
        # Prefer the next city-wide, road-fit-ranked placement. Only fall back
        # to a local measured transform when the snap preflight was unavailable.
        if trial.placement_candidates:
            trial.route_draft = copy.deepcopy(trial.placement_candidates.pop(0))
        else:
            workflow = get_settings().workflow
            if candidate.validation.shape_fidelity < workflow.min_shape_fidelity:
                trial.route_draft.rotation_deg = (
                    trial.route_draft.rotation_deg + 90.0
                ) % 360.0
            elif (
                trial.snapped is not None
                and trial.snapped.total_distance_m > 0
                and trial.route_draft.target_distance_km
            ):
                measured_km = trial.snapped.total_distance_m / 1000.0
                factor = trial.route_draft.target_distance_km / measured_km
                trial.route_draft.scale_m *= min(1.35, max(0.55, factor))
            else:
                return best

        self._run_candidate_node(nodes["placement"], trial)
        Orchestrator._measure_route_variants(trial, nodes, recoverable=True)
        candidate.candidate_count += trial.candidate_count
        candidate.preflight_count += trial.preflight_count
        if (
            trial.validation is not None
            and candidate.validation is not None
            and self._candidate_is_better(trial.validation, candidate.validation)
        ):
            trial.candidate_count = candidate.candidate_count
            trial.preflight_count = candidate.preflight_count
            return trial
        return candidate

    @staticmethod
    def _fit_reasons(validation) -> list[str]:
        if validation is None:
            return ["We couldn’t match this drawing to nearby streets."]
        workflow = get_settings().workflow
        reasons: list[str] = []
        if not validation.on_roads:
            reasons.append(
                "We couldn’t match this drawing to connected streets, so the map is only a "
                "preview."
            )
        if validation.shape_fidelity < workflow.min_shape_fidelity:
            reasons.append(
                f"The closest route had a {validation.shape_fidelity:.0%} shape match. "
                f"We aim for at least {workflow.min_shape_fidelity:.0%}."
            )
        if validation.spatial_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Line order scored {validation.spatial_similarity:.0%}; the street route "
                "drifts too far from the drawing."
            )
        if validation.coverage_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Outline coverage scored {validation.coverage_similarity:.0%}; large sections "
                "move away from the drawing."
            )
        if validation.turning_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Turns and curves scored {validation.turning_similarity:.0%}; some of the "
                "shape’s distinctive features are lost."
            )
        if validation.landmark_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Key points scored {validation.landmark_similarity:.0%}; one or more important "
                "tips, corners, or notches are missing."
            )
        if validation.length_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Street detours made the route {validation.route_length_ratio:.2f}× longer "
                "than the drawing and added confusing extra lines."
            )
        if validation.extent_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Shape proportions scored {validation.extent_similarity:.0%}; the route is too "
                "stretched or squashed."
            )
        if validation.distance_fit < distance_fit_minimum(validation.target_distance_km):
            reasons.append(
                f"Distance match scored {validation.distance_fit:.0%}; the route is too far "
                "from the length you requested."
            )
        if validation.closure < 0.6:
            reasons.append(
                f"Return to start scored {validation.closure:.0%}; the finish is too far from "
                "the starting point."
            )
        if (
            validation.score < workflow.validation_score_threshold
            and not reasons
        ):
            reasons.append(
                f"Overall match scored {validation.score:.0%}. We aim for at least "
                f"{workflow.validation_score_threshold:.0%}."
            )
        return reasons

    @staticmethod
    def _draft_params_eq(a, b) -> bool:
        """True if the tweakable params of two drafts are identical."""
        if a is None or b is None:
            return a is b
        for attr in ("scale_m", "rotation_deg", "lat_offset_m", "lon_offset_m", "simplify_tolerance", "feature_repair", "feature_repair_variant"):
            if getattr(a, attr) != getattr(b, attr):
                return False
        return True

    @staticmethod
    def _candidate_is_better(candidate, incumbent) -> bool:
        """Balance failed-gate progress and usable-route fidelity.

        Complete quality-gate passes outrank every partial result.  Partial
        routes jointly reward their weakest required check and aggregate
        likeness, preventing either one from hiding a severe regression in the
        other.  Scores and gates themselves remain unchanged.
        """
        if candidate.on_roads != incumbent.on_roads:
            return candidate.on_roads
        return Orchestrator._quality_rank(candidate) > Orchestrator._quality_rank(incumbent)

    @staticmethod
    def _shape_repair_is_better(candidate, incumbent) -> bool:
        """Do not create a new distance failure while polishing the silhouette.

        The main search may trade distance for a substantially better drawing.
        Late local repairs are narrower: a measured, on-road route that already
        meets the activity length must remain available as the incumbent.
        Every trial is still recorded for user comparison.
        """
        if (incumbent.on_roads
                and incumbent.distance_fit >= distance_fit_minimum(incumbent.target_distance_km)
                and candidate.distance_fit < distance_fit_minimum(candidate.target_distance_km)):
            return False
        return Orchestrator._candidate_is_better(candidate, incumbent)

    @staticmethod
    def _passes_quality(validation) -> bool:
        # Open routes receive closure=1.0 in ValidationAgent, so treating the
        # closure gate as applicable here is equivalent while keeping this
        # state-free helper useful in candidate comparisons.
        return passes_quality_gates(validation, closed=True)

    @staticmethod
    def _quality_rank(validation) -> tuple[bool, bool, float, float, float]:
        return route_quality_rank(validation)

    def _evaluate_suggestion_candidates(
        self,
        state: WorkflowState,
        nodes: Mapping[str, WorkflowNode],
        runtime: WorkflowRuntime | None = None,
    ) -> None:
        """Measure a few city-specific templates before refining the winner."""
        plan = state.plan
        intent = state.intent
        if (
            plan is None
            or intent is None
            or state.shape is None
            or state.route_draft is None
            or state.snapped is None
            or state.validation is None
            or len(plan.suggestion_candidates) < 2
        ):
            return

        if self._passes_quality(state.validation):
            log.info(
                "suggestion search accepted primary %s (fidelity=%.3f, score=%.3f)",
                state.shape.name,
                state.validation.shape_fidelity,
                state.validation.score,
            )
            return

        best_shape = copy.deepcopy(state.shape)
        best_draft = copy.deepcopy(state.route_draft)
        best_placement_candidates = copy.deepcopy(state.placement_candidates)
        best_snapped = copy.deepcopy(state.snapped)
        best_validation = copy.deepcopy(state.validation)
        best_errors = list(state.errors)
        primary_shape_name = state.shape.name

        alternative_names = [
            candidate_name
            for candidate_name in plan.suggestion_candidates
            if candidate_name != primary_shape_name
        ]
        # Near the deadline further template routings cannot finish inside the
        # client timeout; keep the best measured route instead.
        if runtime is not None and runtime.deadline_exceeded():
            log.warning(
                "suggestion search skipped: workflow deadline already exceeded"
            )
            alternative_names = []

        jobs: list[tuple[str, WorkflowState, str]] = []
        for candidate_name in alternative_names:
            candidate_state = self._measurement_shell(state)
            if candidate_state.intent is None:
                continue
            candidate_state.candidate_count = 0
            candidate_state.preflight_count = 0
            candidate_state.intent.shape = candidate_name
            candidate_state.route_draft = None
            jobs.append(("candidate", candidate_state, candidate_name))

        results = self._measure_candidates(jobs, nodes)

        for candidate_name, (candidate_state, _error) in zip(
            [job[2] for job in jobs],
            results,
            strict=True,
        ):
            state.candidate_count += candidate_state.candidate_count
            state.preflight_count += candidate_state.preflight_count
            state.preflight_candidates.extend(
                candidate_state.preflight_candidates
            )
            state.candidates.extend(candidate_state.candidates)
            candidate_validation = candidate_state.validation
            if (
                candidate_validation is None
                or candidate_state.shape is None
                or candidate_state.route_draft is None
                or candidate_state.snapped is None
            ):
                continue
            state.history.extend(candidate_state.history)
            state.history.append(
                {
                    "agent": "suggestion_search",
                    "iteration": 0,
                    "shape": candidate_name,
                    "score": candidate_validation.score,
                    "fidelity": candidate_validation.shape_fidelity,
                    "distance_fit": candidate_validation.distance_fit,
                    "on_roads": candidate_validation.on_roads,
                }
            )
            if self._candidate_is_better(candidate_validation, best_validation):
                best_shape = copy.deepcopy(candidate_state.shape)
                best_draft = copy.deepcopy(candidate_state.route_draft)
                best_placement_candidates = copy.deepcopy(
                    candidate_state.placement_candidates
                )
                best_snapped = copy.deepcopy(candidate_state.snapped)
                best_validation = copy.deepcopy(candidate_validation)
                best_errors = list(candidate_state.errors)
                if self._passes_quality(best_validation):
                    break

        state.shape = best_shape
        state.route_draft = best_draft
        state.placement_candidates = best_placement_candidates
        state.snapped = best_snapped
        state.validation = best_validation
        state.errors = best_errors
        intent.shape = best_shape.name
        plan.suggested_shape = best_shape.name
        plan.notes = plan.suggestion_reasons.get(best_shape.name, plan.notes)
        log.info(
            "suggestion search selected %s (fidelity=%.3f, score=%.3f)",
            best_shape.name,
            best_validation.shape_fidelity,
            best_validation.score,
        )


def _iter_snapshot(state: WorkflowState, new_v, best_v) -> dict:
    return {
        "agent": "refinement",
        "iteration": state.iterations,
        "score": new_v.score,
        "delta_vs_best": round(new_v.score - best_v.score, 4),
        "fidelity": new_v.shape_fidelity,
        "distance_fit": new_v.distance_fit,
        "closure": new_v.closure,
        "on_roads": new_v.on_roads,
        "issues": new_v.issues,
        "rotation_deg": state.route_draft.rotation_deg if state.route_draft else None,
        "scale_m": state.route_draft.scale_m if state.route_draft else None,
        "lat_offset_m": state.route_draft.lat_offset_m if state.route_draft else None,
        "lon_offset_m": state.route_draft.lon_offset_m if state.route_draft else None,
        "simplify_tolerance": (
            state.route_draft.simplify_tolerance if state.route_draft else None
        ),
    }


_default: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _default
    if _default is None:
        _default = Orchestrator()
    return _default


def generate(
    prompt: str,
    *,
    intent_override: Intent | None = None,
    start_point: LatLon | None = None,
    start_label: str | None = None,
    start_direction_deg: float | None = None,
    route_preferences: RoutePreferences | None = None,
    reference_shape: Shape | None = None,
    reference_image_data_url: str | None = None,
    reference_name: str | None = None,
    reference_kind: str | None = None,
    map_placement: MapPlacement | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    preview_sink: Callable[[dict[str, Any]], None] | None = None,
) -> WorkflowState:
    """Convenience entry point used by the API and the demo script."""
    return get_orchestrator().run(
        prompt,
        intent_override=intent_override,
        start_point=start_point,
        start_label=start_label,
        start_direction_deg=start_direction_deg,
        route_preferences=route_preferences,
        reference_shape=reference_shape,
        reference_image_data_url=reference_image_data_url,
        reference_name=reference_name,
        reference_kind=reference_kind,
        map_placement=map_placement,
        event_sink=event_sink,
        preview_sink=preview_sink,
    )
