"""RefinementAgent: deterministically improve measured route geometry.

Road-network optimisation must be driven by the actual ORS distance and shape
score, not by an LLM guessing whether a route is too long or too short. Each
bounded iteration proposes a scale correction and, when needed, a different
rotation/placement candidate for the orchestrator to measure.
"""

from __future__ import annotations

import copy
import math

from ..config import get_settings
from ..state import WorkflowState
from .base import BaseAgent


class RefinementAgent(BaseAgent):
    name = "refinement"

    def run(self, state: WorkflowState) -> WorkflowState:
        if (
            state.validation is None
            or state.route_draft is None
            or state.intent is None
            or state.shape is None
        ):
            raise RuntimeError("refinement requires validation, route draft, intent, and shape")
        if state.placement_candidates:
            state.route_draft = copy.deepcopy(state.placement_candidates.pop(0))
            score = state.route_draft.preflight_score
            self._record(
                state,
                "refine: testing next road-fit shortlist placement"
                + (f" (preflight={score:.3f})" if score is not None else ""),
            )
            return state
        draft = state.route_draft
        tweaks = self._heuristic(state)
        self._apply(draft, tweaks)
        self._record(state, f"refine: {tweaks.get('rationale', 'applied')}")
        return state

    def _apply(self, draft, t: dict) -> None:
        scale_factor = _finite_number(t.get("scale_factor"))
        if scale_factor is not None:
            draft.scale_m *= min(1.5, max(0.35, scale_factor))
            draft.scale_m = min(200_000.0, max(25.0, draft.scale_m))

        rotation_delta = _finite_number(t.get("rotation_delta_deg"))
        if rotation_delta is not None:
            draft.rotation_deg = (draft.rotation_deg + min(90.0, max(-90.0, rotation_delta))) % 360.0

        lat_offset = _finite_number(t.get("lat_offset_m"))
        if lat_offset is not None:
            draft.lat_offset_m = min(20_000.0, max(-20_000.0, draft.lat_offset_m + lat_offset))

        lon_offset = _finite_number(t.get("lon_offset_m"))
        if lon_offset is not None:
            draft.lon_offset_m = min(20_000.0, max(-20_000.0, draft.lon_offset_m + lon_offset))

        simplify_tolerance = _finite_number(t.get("simplify_tolerance"))
        if simplify_tolerance is not None:
            draft.simplify_tolerance = min(25.0, max(0.0, simplify_tolerance))

    # -- deterministic candidate proposal ---------------------------------- #
    def _heuristic(self, state: WorkflowState) -> dict[str, float | str | None]:
        if (
            state.validation is None
            or state.route_draft is None
            or state.intent is None
            or state.shape is None
        ):
            raise RuntimeError("refinement heuristic received incomplete workflow state")
        v = state.validation
        draft = state.route_draft
        cfg = get_settings().workflow
        target = (
            draft.target_distance_km
            or state.intent.distance_km
            or cfg.distance_defaults.get(state.intent.sport, 8.0)
        )
        actual_km = (state.snapped.total_distance_m / 1000.0) if state.snapped else 0.0

        distance_error = (
            abs(actual_km - target) / target
            if target > 0 and actual_km > 0
            else 1.0
        )
        candidates: list[dict[str, float | str | None]] = []
        tighter_tolerance = (
            max(0.1, draft.simplify_tolerance * 0.65)
            if v.shape_fidelity < cfg.min_shape_fidelity
            else None
        )

        if distance_error > 0.08:
            measured_factor = (
                min(1.5, max(0.35, target / actual_km))
                if actual_km > 0
                else 1.2
            )
            direction = "shrink" if measured_factor < 1.0 else "grow"
            candidates.append(
                {
                    "scale_factor": measured_factor,
                    "rotation_delta_deg": None,
                    "lat_offset_m": None,
                    "lon_offset_m": None,
                    "simplify_tolerance": tighter_tolerance,
                    "rationale": (
                        f"measured distance {actual_km:.2f}km vs {target:.2f}km: "
                        f"{direction} x{measured_factor:.3f}"
                    ),
                }
            )

            # Road distance is discontinuous: moving a guide across a bridge,
            # motorway, or disconnected block can make the full ratio jump
            # from too short to far too long. A square-root correction brackets
            # that transition instead of resubmitting the lower-scoring endpoint.
            damped_factor = math.sqrt(measured_factor)
            if abs(damped_factor - measured_factor) > 0.025:
                candidates.append(
                    {
                        "scale_factor": damped_factor,
                        "rotation_delta_deg": None,
                        "lat_offset_m": None,
                        "lon_offset_m": None,
                        "simplify_tolerance": tighter_tolerance,
                        "rationale": (
                            f"distance response is non-linear: test damped "
                            f"{direction} x{damped_factor:.3f}"
                        ),
                    }
                )

        if v.shape_fidelity < cfg.min_shape_fidelity:
            step = min(1_600.0, max(600.0, draft.scale_m * 0.70))
            variants = (
                (0.0, 0.0, -step, "west grid"),
                (30.0, 0.0, -step, "rotated west grid"),
                (-30.0, -step, 0.0, "rotated south grid"),
                (60.0, step, step, "north-east grid"),
                (-60.0, -step, -step, "south-west grid"),
                (0.0, 0.0, step, "east grid"),
            )
            for rotation, lat_offset, lon_offset, label in variants:
                candidates.append(
                    {
                        "scale_factor": None,
                        "rotation_delta_deg": rotation,
                        "lat_offset_m": lat_offset,
                        "lon_offset_m": lon_offset,
                        "simplify_tolerance": tighter_tolerance,
                        "rationale": (
                            f"fidelity {v.shape_fidelity:.3f}: test {label} "
                            f"(rotation {rotation:+.0f}°)"
                        ),
                    }
                )

        if state.shape.closed and v.closure < 0.7:
            candidates.insert(
                0,
                {
                    "scale_factor": 0.93,
                    "rotation_delta_deg": None,
                    "lat_offset_m": None,
                    "lon_offset_m": None,
                    "simplify_tolerance": tighter_tolerance,
                    "rationale": f"closure {v.closure:.3f}: shrink x0.930",
                },
            )

        if not candidates:
            candidates.extend(
                {
                    "scale_factor": None,
                    "rotation_delta_deg": rotation,
                    "lat_offset_m": None,
                    "lon_offset_m": None,
                    "simplify_tolerance": tighter_tolerance,
                    "rationale": f"test alternate street-grid rotation {rotation:+.0f}°",
                }
                for rotation in (10.0, -20.0, 30.0, -45.0, 60.0, -75.0)
            )

        tried = self._tested_candidate_signatures(state)
        current = self._draft_signature(draft)
        for candidate in candidates:
            signature = self._candidate_signature(draft, candidate)
            if signature != current and signature not in tried:
                return candidate

        # Exhausted candidates are rare with the bounded six-pass loop. Keep a
        # deterministic final escape hatch that still cannot repeat a draft.
        for degrees in range(5, 91, 5):
            candidate = {
                "scale_factor": None,
                "rotation_delta_deg": float(degrees),
                "lat_offset_m": None,
                "lon_offset_m": None,
                "simplify_tolerance": tighter_tolerance,
                "rationale": f"test untried street-grid rotation +{degrees}°",
            }
            if self._candidate_signature(draft, candidate) not in tried:
                return candidate
        return {}

    def _candidate_signature(self, draft, tweaks: dict) -> tuple[float, ...]:
        trial = copy.deepcopy(draft)
        self._apply(trial, tweaks)
        return self._draft_signature(trial)

    @staticmethod
    def _draft_signature(draft) -> tuple[float, ...]:
        return (
            round(float(draft.scale_m), 1),
            round(float(draft.rotation_deg) % 360.0, 1),
            round(float(draft.lat_offset_m), 1),
            round(float(draft.lon_offset_m), 1),
            round(float(draft.simplify_tolerance), 2),
        )

    def _tested_candidate_signatures(self, state: WorkflowState) -> set[tuple[float, ...]]:
        signatures: set[tuple[float, ...]] = set()
        for entry in state.history:
            if entry.get("agent") != "refinement":
                continue
            values = (
                entry.get("scale_m"),
                entry.get("rotation_deg"),
                entry.get("lat_offset_m"),
                entry.get("lon_offset_m"),
                entry.get("simplify_tolerance"),
            )
            if any(value is None for value in values):
                continue
            numeric_values = tuple(float(value) for value in values if value is not None)
            signatures.add(
                (
                    round(numeric_values[0], 1),
                    round(numeric_values[1] % 360.0, 1),
                    round(numeric_values[2], 1),
                    round(numeric_values[3], 1),
                    round(numeric_values[4], 2),
                )
            )
        return signatures


def _finite_number(value: object) -> float | None:
    """Parse untrusted model output without allowing NaN or infinity."""
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
