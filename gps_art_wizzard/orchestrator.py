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
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from .config import get_settings
from .graph import build_nodes
from .logging_config import current_request_id
from .quality import passes_quality_gates, quality_bottleneck, quality_gate_report
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
        n["snap"].run(state)
        n["validation"].run(state)
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
            n["snap"].run(state)
            n["validation"].run(state)

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

        # If an explicitly requested drawing still fails the recognition
        # gates, route a small city-aware set of simpler shapes.  A replacement
        # is accepted only after it passes the same street, silhouette,
        # distance, and closure checks as the original.
        self._evaluate_fallback_candidates(state, n, runtime=runtime)
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
                        self._run_candidate_node(nodes["snap"], job_state)
                        self._run_candidate_node(nodes["validation"], job_state)
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
        Orchestrator._run_candidate_node(nodes["snap"], state)
        Orchestrator._run_candidate_node(nodes["validation"], state)
        return state

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
        self._run_candidate_node(nodes["snap"], candidate)
        self._run_candidate_node(nodes["validation"], candidate)
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
        self._run_candidate_node(nodes["snap"], trial)
        self._run_candidate_node(nodes["validation"], trial)
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
        if validation.distance_fit < 0.6:
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
        for attr in ("scale_m", "rotation_deg", "lat_offset_m", "lon_offset_m", "simplify_tolerance"):
            if getattr(a, attr) != getattr(b, attr):
                return False
        return True

    @staticmethod
    def _candidate_is_better(candidate, incumbent) -> bool:
        """Prefer the candidate that best balances every export quality gate.

        A fidelity-only ordering can get stuck on a recognisable route that is
        almost twice the requested distance; score-only ordering does the
        reverse. Ranking by the weakest normalised gate moves the search toward
        a route that is simultaneously recognisable and usable.
        """
        if candidate.on_roads != incumbent.on_roads:
            return candidate.on_roads
        return Orchestrator._quality_rank(candidate) > Orchestrator._quality_rank(incumbent)

    @staticmethod
    def _passes_quality(validation) -> bool:
        # Open routes receive closure=1.0 in ValidationAgent, so treating the
        # closure gate as applicable here is equivalent while keeping this
        # state-free helper useful in candidate comparisons.
        return passes_quality_gates(validation, closed=True)

    @staticmethod
    def _quality_rank(validation) -> tuple[bool, float, float, float]:
        bottleneck = quality_bottleneck(validation, closed=True)
        return (
            Orchestrator._passes_quality(validation),
            bottleneck,
            validation.score,
            validation.shape_fidelity,
        )

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
    )
