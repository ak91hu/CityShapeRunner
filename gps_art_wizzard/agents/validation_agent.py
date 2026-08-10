"""ValidationAgent: score the snapped route (closure, distance fit, shape fidelity)."""

from __future__ import annotations

import math

from ..config import get_settings
from ..quality import quality_gate_report
from ..state import EvaluatedCandidate, Validation, WorkflowState
from ..tools import geo, shape_similarity
from .base import BaseAgent


class ValidationAgent(BaseAgent):
    name = "validation"

    def run(self, state: WorkflowState) -> WorkflowState:
        if (
            state.snapped is None
            or state.shape is None
            or state.intent is None
            or state.route_draft is None
        ):
            raise RuntimeError("validation requires snapped route, shape, intent, and route draft")
        snapped = state.snapped
        shape = state.shape
        intent = state.intent

        # --- closure (closed shapes only) --------------------------------- #
        if shape.closed and len(snapped.points) >= 2:
            gap_m = geo.haversine(*snapped.points[0], *snapped.points[-1])
            closure_score = math.exp(-gap_m / 200.0)  # 200 m gap -> ~0.37
            closure_applicable = True
        else:
            gap_m = 0.0
            closure_score = 1.0
            closure_applicable = False

        # --- distance fit -------------------------------------------------- #
        actual_km = snapped.total_distance_m / 1000.0
        bounds = get_settings().workflow.distance_bounds.get(intent.sport, [3, 60])
        target = state.route_draft.target_distance_km or intent.distance_km
        if target:
            err = abs(actual_km - target) / max(target, 1.0)
            distance_fit = math.exp(-err * 3.0)
        elif bounds[0] <= actual_km <= bounds[1]:
            distance_fit = 1.0
        else:
            over = actual_km - bounds[1] if actual_km > bounds[1] else bounds[0] - actual_km
            distance_fit = math.exp(-over / max(bounds[1] - bounds[0], 1.0))

        # --- shape fidelity ------------------------------------------------ #
        # Compare the placed drawing (waypoints) to the road-snapped result,
        # so the score is rotation-robust (both share the placed orientation).
        diagnostics = shape_similarity.similarity_diagnostics_between_routes(
            state.route_draft.waypoints, snapped.points
        )
        fidelity = diagnostics.fidelity

        # --- road-following guard ------------------------------------------ #
        # A straight-line fallback (snapped=False) cuts through buildings,
        # rivers, and parks — it is NOT a runnable route. Shape fidelity is
        # meaningless in that mode (~1.0, the drawing compared to itself), so
        # cap the overall score below the threshold and flag it prominently.
        on_roads = snapped.snapped
        if not on_roads:
            fidelity = min(fidelity, 0.3)

        # --- overall ------------------------------------------------------- #
        if closure_applicable:
            score = 0.5 * fidelity + 0.3 * distance_fit + 0.2 * closure_score
        else:
            score = 0.6 * fidelity + 0.4 * distance_fit
        if not on_roads:
            score = min(score, 0.4)
        minimum_fidelity = get_settings().workflow.min_shape_fidelity
        if fidelity < minimum_fidelity:
            # A good distance cannot compensate for an unrecognisable drawing.
            # Keep the cap monotonic so 0.69 fidelity always outranks 0.35;
            # the previous flat 0.71 cap created ties that selected malformed
            # routes merely because their kilometre total happened to match.
            fidelity_shortfall = minimum_fidelity - fidelity
            recognition_cap = (
                get_settings().workflow.validation_score_threshold
                - 0.01
                - 0.5 * fidelity_shortfall
            )
            score = min(
                score,
                max(0.0, recognition_cap),
            )

        issues: list[str] = []
        if not on_roads:
            issues.append("route is NOT on roads (straight-line fallback) — cuts through buildings/obstacles")
        if closure_applicable and closure_score < 0.6:
            issues.append(f"loop not closed (gap {gap_m:.0f} m)")
        if distance_fit < 0.6:
            issues.append(f"distance {actual_km:.1f} km off target/bounds")
        if fidelity < minimum_fidelity:
            issues.append(f"low shape fidelity ({fidelity:.2f})")
        if on_roads and diagnostics.spatial_similarity < minimum_fidelity:
            issues.append(
                "the ordered street curve departs too far from the selected shape "
                f"({diagnostics.spatial_similarity:.2f})"
            )
        if on_roads and diagnostics.coverage_similarity < minimum_fidelity:
            issues.append(
                "the street route leaves too much of the intended outline uncovered "
                f"({diagnostics.coverage_similarity:.2f})"
            )
        if on_roads and diagnostics.turning_similarity < minimum_fidelity:
            issues.append(
                "characteristic direction changes were not preserved "
                f"({diagnostics.turning_similarity:.2f})"
            )
        if on_roads and diagnostics.landmark_similarity < minimum_fidelity:
            issues.append(
                "salient corners, notches, or tips were not preserved "
                f"({diagnostics.landmark_similarity:.2f})"
            )
        if on_roads and diagnostics.reversal_similarity < minimum_fidelity:
            issues.append(
                "the street route adds unintended U-turns or backtracking strokes "
                f"({diagnostics.reversal_similarity:.2f})"
            )
        if on_roads and diagnostics.length_similarity < minimum_fidelity:
            issues.append(
                "street detours distort the drawing length "
                f"({diagnostics.route_length_ratio:.2f}× the guide length)"
            )
        if on_roads and diagnostics.extent_similarity < minimum_fidelity:
            issues.append(
                "the routed width/height no longer matches the intended silhouette "
                f"({diagnostics.extent_similarity:.2f})"
            )

        state.validation = Validation(
            score=score,
            closure=closure_score,
            distance_fit=distance_fit,
            shape_fidelity=fidelity,
            issues=issues,
            on_roads=on_roads,
            spatial_similarity=diagnostics.spatial_similarity,
            coverage_similarity=diagnostics.coverage_similarity,
            turning_similarity=diagnostics.turning_similarity,
            length_similarity=diagnostics.length_similarity,
            extent_similarity=diagnostics.extent_similarity,
            route_length_ratio=diagnostics.route_length_ratio,
            mean_deviation_ratio=diagnostics.mean_deviation_ratio,
            landmark_similarity=diagnostics.landmark_similarity,
            reversal_similarity=diagnostics.reversal_similarity,
            closure_gap_m=gap_m,
            actual_distance_km=actual_km,
            target_distance_km=target,
            route_point_count=len(snapped.points),
            guide_point_count=len(state.route_draft.waypoints),
        )
        state.candidates.append(
            EvaluatedCandidate(
                shape_name=shape.name,
                shape_source=shape.source,
                points=list(snapped.points),
                ideal_points=list(state.route_draft.waypoints),
                total_distance_m=snapped.total_distance_m,
                snapped=snapped.snapped,
                closed=shape.closed,
                target_distance_km=target,
                validation=state.validation,
                rotation_deg=state.route_draft.rotation_deg,
                scale_m=state.route_draft.scale_m,
                lat_offset_m=state.route_draft.lat_offset_m,
                lon_offset_m=state.route_draft.lon_offset_m,
                preflight_score=state.route_draft.preflight_score,
            )
        )
        report = quality_gate_report(
            state.validation,
            closed=shape.closed,
            candidate_shape=shape.name,
            selected_shape=shape.name,
        )
        failed = report["failed_gates"]
        decision = "passed every automatic check" if report["passed"] else "available for user review"
        target_text = f"{target:.2f} km" if target is not None else "activity range"
        failed_text = ", ".join(failed) if failed else "none"
        self._record(
            state,
            (
                f"Route validation: {shape.name} is {decision}; "
                f"street matched={'yes' if on_roads else 'no'}, "
                f"overall={score:.1%}, likeness={fidelity:.1%}, "
                f"distance={actual_km:.2f} km against {target_text}, "
                f"failed checks={failed_text}."
            ),
            event="route.validation.completed",
            shape=shape.name,
            city=intent.city,
            sport=intent.sport,
            decision="verified" if report["passed"] else "review",
            verified=report["passed"],
            failed_gates=failed,
            score=score,
            fidelity=fidelity,
            snapped=on_roads,
            distance_km=actual_km,
            target_distance_km=target,
            distance_delta_km=(actual_km - target) if target is not None else None,
            distance_fit=distance_fit,
            closure=closure_score,
            closure_gap_m=gap_m,
            spatial_similarity=diagnostics.spatial_similarity,
            coverage_similarity=diagnostics.coverage_similarity,
            turning_similarity=diagnostics.turning_similarity,
            landmark_similarity=diagnostics.landmark_similarity,
            reversal_similarity=diagnostics.reversal_similarity,
            length_similarity=diagnostics.length_similarity,
            extent_similarity=diagnostics.extent_similarity,
            route_length_ratio=diagnostics.route_length_ratio,
            mean_deviation_ratio=diagnostics.mean_deviation_ratio,
            route_point_count=len(snapped.points),
            guide_point_count=len(state.route_draft.waypoints),
            rotation_deg=state.route_draft.rotation_deg,
            scale_m=state.route_draft.scale_m,
            lat_offset_m=state.route_draft.lat_offset_m,
            lon_offset_m=state.route_draft.lon_offset_m,
            preflight_score=state.route_draft.preflight_score,
        )
        return state
