"""ExportAgent: serialise the final (best) snapped route to GPX / TCX."""

from __future__ import annotations

import os

from ..quality import quality_gate_report
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
            state.export = None
            return state
        if state.validation is None:
            state.errors.append("export: route validation is unavailable")
            state.export = None
            return state
        report = quality_gate_report(
            state.validation,
            closed=bool(state.shape and state.shape.closed),
            candidate_shape=state.shape.name if state.shape else None,
            selected_shape=state.shape.name if state.shape else None,
        )
        intent = state.intent
        if intent is None:
            state.errors.append("export: no route intent available")
            state.export = None
            return state
        # A source fallback may replace an unavailable requested drawing.
        # GPX/TCX metadata must describe the shape that is actually shown,
        # not the unavailable name that remains in the original intent.
        shape_label = state.shape.name if state.shape else (intent.shape or "route")
        city = intent.city or "route"
        name = f"{shape_label} in {city}"
        failed_labels = [
            gate["label"]
            for gate in report["gates"]
            if gate["applies"] and not gate["passed"]
        ]
        if failed_labels:
            state.errors.append(
                "export-warning: automatic verification did not pass ("
                + ", ".join(failed_labels)
                + "); the route remains available after explicit user acceptance"
            )

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
        if out_dir and report["passed"]:
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
            (
                f"GPX prepared for {shape_label} in {city}: "
                f"{len(snapped.points)} points, {snapped.total_distance_m/1000:.2f} km, "
                f"street matched={'yes' if snapped.snapped else 'no'}, "
                f"mode={'verified download' if report['passed'] else 'user acceptance required'}, "
                f"failed checks={', '.join(report['failed_gates']) or 'none'}."
            ),
            event="route.export.prepared",
            shape=shape_label,
            city=city,
            sport=intent.sport,
            decision="verified" if report["passed"] else "review",
            verified=report["passed"],
            failed_gates=report["failed_gates"],
            snapped=snapped.snapped,
            distance_km=snapped.total_distance_m / 1000.0,
            route_point_count=len(snapped.points),
            export_mode="verified" if report["passed"] else "user_acceptance",
        )
        return state
