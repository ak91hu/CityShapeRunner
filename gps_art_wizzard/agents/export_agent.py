"""ExportAgent: serialise the final (best) snapped route to GPX / TCX."""

from __future__ import annotations

import os

from ..config import get_settings
from ..state import WorkflowState
from ..tools import gpx_writer
from .base import BaseAgent


class ExportAgent(BaseAgent):
    name = "export"

    def run(self, state: WorkflowState) -> WorkflowState:
        # Clear stale export errors from a previous run.
        state.errors = [
            e
            for e in state.errors
            if not e.startswith(("export:", "export-warning:"))
        ]
        snapped = state.best_snapped or state.snapped
        if not snapped or len(snapped.points) < 2:
            state.errors.append("export: no snapped route available")
            return state
        if not snapped.snapped:
            state.errors.append(
                "export-warning: GPX is a manually reviewable guide, not a verified street route"
            )
        if (
            state.validation is None
            or state.validation.shape_fidelity < get_settings().workflow.min_shape_fidelity
        ):
            state.errors.append(
                "export-warning: shape fidelity is below the recommended minimum"
            )
        if (
            state.validation is None
            or state.validation.score
            < get_settings().workflow.validation_score_threshold
            or state.validation.distance_fit < 0.6
        ):
            state.errors.append(
                "export-warning: route quality or target-distance fit is below the recommended minimum"
            )
        intent = state.intent
        if intent is None:
            state.errors.append("export: no route intent available")
            state.export = None
            return state
        shape_label = (intent.text if intent.text else (intent.shape or "route")) or "route"
        city = intent.city or "route"
        name = f"{shape_label} in {city}"

        gpx = gpx_writer.to_gpx(
            snapped.points, name=name, sport=intent.sport, total_distance_m=snapped.total_distance_m
        )
        tcx = None
        try:
            tcx = gpx_writer.to_tcx(
                snapped.points, name=name, sport=intent.sport, total_distance_m=snapped.total_distance_m
            )
        except Exception:  # noqa: BLE001
            pass

        # Stateless hosting is the default. Operators can opt into persistent
        # server-side copies by configuring an explicit export directory.
        file_paths: dict[str, str] = {}
        out_dir = os.getenv("EXPORT_DIR", "").strip()
        if out_dir:
            file_paths = gpx_writer.write_files(
                snapped.points,
                name=name,
                sport=intent.sport,
                total_distance_m=snapped.total_distance_m,
                out_dir=out_dir,
            )
        from ..state import Export
        state.export = Export(gpx=gpx, tcx=tcx, file_paths=file_paths, name=name)
        self._record(
            state,
            f"exported candidate gpx "
            f"({len(snapped.points)} pts, {snapped.total_distance_m/1000:.2f}km, "
            f"street_matched={snapped.snapped})",
        )
        return state
