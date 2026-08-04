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

import copy
import logging
from collections.abc import Mapping
from typing import Protocol

from .config import get_settings
from .graph import build_nodes
from .logging_config import current_request_id
from .quality import passes_quality_gates, quality_bottleneck, quality_gate_report
from .state import FitDecision, WorkflowState

log = logging.getLogger(__name__)


class WorkflowNode(Protocol):
    def run(self, state: WorkflowState) -> WorkflowState: ...


class Orchestrator:
    def __init__(self, nodes: Mapping[str, WorkflowNode] | None = None):
        self.nodes = build_nodes() if nodes is None else nodes

    def run(self, prompt: str) -> WorkflowState:
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
        )
        n = self.nodes

        # --- linear pass --------------------------------------------------- #
        n["intent"].run(state)
        if state.intent is not None:
            state.requested_shape = (
                f"text:{state.intent.text}"
                if state.intent.text
                else state.intent.shape
            )
        n["planning"].run(state)
        n["shape"].run(state)
        n["placement"].run(state)
        n["preflight"].run(state)
        n["snap"].run(state)
        n["validation"].run(state)
        self._evaluate_suggestion_candidates(state, n)

        cfg = get_settings().workflow
        threshold = cfg.validation_score_threshold
        max_iter = cfg.max_refinement_iterations

        best_v = state.validation
        best_snapped = copy.deepcopy(state.snapped)
        best_draft = copy.deepcopy(state.route_draft)
        best_errors = list(state.errors)
        if best_v is None:
            state.errors.append("validation produced no score")
            return state

        # --- refinement loop ----------------------------------------------- #
        # Geometry tweaks cannot turn the explicit no-road-data preview into a
        # feasible route. Skipping those no-op iterations keeps offline/local
        # use fast and avoids implying that refinement solved road access.
        while (
            best_v.on_roads
            and not self._passes_quality(best_v)
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
        self._evaluate_fallback_candidates(state, n)
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
        return state

    def _evaluate_fallback_candidates(
        self,
        state: WorkflowState,
        nodes: Mapping[str, WorkflowNode],
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
                            f"{requested.title()} is not available as a validated continuous "
                            "route template, so it could not be tested without inventing an "
                            "unreliable drawing."
                        ),
                        (
                            f"{shape.name.title()} was used only because its real-street route "
                            f"passed every quality gate at "
                            f"{validation.shape_fidelity:.0%} recognisability."
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
            for candidate_name in plan.fallback_candidates:
                if candidate_name == shape.name:
                    continue
                attempted.append(candidate_name)
                candidate = self._measure_fallback_shape(
                    state,
                    candidate_name,
                    nodes,
                )
                state.candidate_count += candidate.candidate_count
                state.preflight_count += candidate.preflight_count
                state.preflight_candidates.extend(
                    copy.deepcopy(candidate.preflight_candidates)
                )
                state.candidates.extend(copy.deepcopy(candidate.candidates))
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
                        f"{requested.title()} is not available as a validated continuous route "
                        f"template; the initial {requested_shape.title()} fallback also failed."
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
                        f"{selected_shape.name.title()} was selected only after a real-street "
                        f"candidate passed every quality gate: "
                        f"{selected_validation.shape_fidelity:.0%} recognisability, "
                        f"{selected_validation.distance_fit:.0%} distance accuracy, and "
                        f"{selected_validation.closure:.0%} closure."
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
                    f"{requested.title()} is not available as a validated continuous route "
                    f"template; the initial {requested_shape.title()} fallback also failed."
                ),
            )
        if not validation.on_roads:
            reasons.append(
                "Street routing was unavailable, so no alternative could be verified safely."
            )
        elif attempted:
            best_note = ""
            if (
                best_below_target is not None
                and best_below_target.validation is not None
            ):
                best_note = (
                    f" The strongest alternative reached only "
                    f"{best_below_target.validation.shape_fidelity:.0%} recognisability."
                )
            reasons.append(
                f"Measured {', '.join(attempted)} on the same street network, but none "
                f"met every recommended quality target.{best_note} All remain available "
                f"for comparison and manual editing."
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
        candidate = copy.deepcopy(source)
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

        nodes["shape"].run(candidate)
        nodes["placement"].run(candidate)
        preflight = nodes.get("preflight")
        if preflight is not None:
            preflight.run(candidate)
        nodes["snap"].run(candidate)
        nodes["validation"].run(candidate)
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

        nodes["placement"].run(trial)
        nodes["snap"].run(trial)
        nodes["validation"].run(trial)
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
            return ["No valid street-route candidate was produced for the requested drawing."]
        workflow = get_settings().workflow
        reasons: list[str] = []
        if not validation.on_roads:
            reasons.append(
                "The routing provider did not return a real-street route, so recognisability "
                "could not be verified."
            )
        if validation.shape_fidelity < workflow.min_shape_fidelity:
            reasons.append(
                f"The best requested-shape candidate preserved "
                f"{validation.shape_fidelity:.0%} of the recognisable silhouette; "
                f"the required minimum is {workflow.min_shape_fidelity:.0%}."
            )
        if validation.spatial_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Ordered curve similarity was {validation.spatial_similarity:.0%}: the "
                "street traversal departed too far from the selected drawing."
            )
        if validation.coverage_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Outline coverage was {validation.coverage_similarity:.0%}: streets pulled "
                "substantial sections away from the guide contour."
            )
        if validation.turning_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Characteristic-turn preservation was {validation.turning_similarity:.0%}, "
                "so the corners/curves that identify the shape were lost."
            )
        if validation.landmark_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Salient-landmark preservation was {validation.landmark_similarity:.0%}, "
                "so one or more dominant tips, corners, or notches were lost."
            )
        if validation.length_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Street detours stretched the route to {validation.route_length_ratio:.2f}× "
                "the guide length, creating visually misleading extra strokes."
            )
        if validation.extent_similarity < workflow.min_shape_fidelity:
            reasons.append(
                f"Width/height preservation was {validation.extent_similarity:.0%}, "
                "which changed the overall silhouette proportions."
            )
        if validation.distance_fit < 0.6:
            reasons.append(
                f"Distance accuracy was {validation.distance_fit:.0%}; the route could not "
                "stay close enough to the requested length."
            )
        if validation.closure < 0.6:
            reasons.append(
                f"Loop closure was {validation.closure:.0%}; the street network left an "
                "unacceptable start-to-finish gap."
            )
        if (
            validation.score < workflow.validation_score_threshold
            and not reasons
        ):
            reasons.append(
                f"The combined route score was {validation.score:.0%}, below the required "
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

        for candidate_name in plan.suggestion_candidates:
            if candidate_name == primary_shape_name:
                continue
            candidate_state = copy.deepcopy(state)
            if candidate_state.intent is None:
                continue
            candidate_state.candidate_count = 0
            candidate_state.preflight_count = 0
            candidate_state.placement_candidates = []
            candidate_state.preflight_candidates = []
            candidate_state.candidates = []
            candidate_state.intent.shape = candidate_name
            candidate_state.route_draft = None
            candidate_state.history = []
            nodes["shape"].run(candidate_state)
            nodes["placement"].run(candidate_state)
            preflight = nodes.get("preflight")
            if preflight is not None:
                preflight.run(candidate_state)
            nodes["snap"].run(candidate_state)
            nodes["validation"].run(candidate_state)
            state.candidate_count += candidate_state.candidate_count
            state.preflight_count += candidate_state.preflight_count
            state.preflight_candidates.extend(
                copy.deepcopy(candidate_state.preflight_candidates)
            )
            state.candidates.extend(copy.deepcopy(candidate_state.candidates))
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


def generate(prompt: str) -> WorkflowState:
    """Convenience entry point used by the API and the demo script."""
    return get_orchestrator().run(prompt)
