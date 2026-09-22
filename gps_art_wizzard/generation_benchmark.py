"""Reproducible end-to-end route experiments and paired result comparisons.

Run with ``python -m gps_art_wizzard.generation_benchmark --help``. Network
runs are explicitly selected; importing or listing cases never calls providers.
Human labels are supplied separately and bound to the exact route fingerprint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .state import WorkflowState


@dataclass(frozen=True)
class GenerationCase:
    id: str
    city: str
    shape: str
    sport: str
    distance_km: float

    @property
    def prompt(self) -> str:
        return f"draw a {self.shape} in {self.city}, {self.distance_km:g} km, {self.sport}"


def benchmark_cases() -> list[GenerationCase]:
    """200 fixed cases spanning grid, river, hills and coastal constraints."""
    cities = ("Budapest", "Szeged", "Pécs", "Siófok", "Tatabánya")
    shapes = ("heart", "star", "triangle", "square", "circle", "cat", "dog", "fish", "butterfly", "house")
    return [GenerationCase(f"c{ci}-{shape}-{sport}-{distance}", city, shape, sport, distance)
            for ci, city in enumerate(cities)
            for shape in shapes
            for sport, distances in (("run", (5, 10)), ("bike", (15, 30)))
            for distance in distances]


def route_fingerprint(points) -> str:
    return hashlib.sha256(json.dumps(points, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def failure_stage(state: WorkflowState) -> str | None:
    if state.shape is None or state.shape.source == "fallback":
        return "shape_generation"
    review = state.shape.semantic_verification
    if review and review.score is not None and review.score < 0.68:
        return "shape_semantics"
    if not state.snapped or not state.snapped.snapped:
        return "street_connectivity"
    if state.validation:
        from .quality import passes_quality_gates
        if not passes_quality_gates(state.validation, closed=state.shape.closed):
            return "street_fit"
    else:
        return "validation_missing"
    return None


def result_record(case: GenerationCase, state: WorkflowState, elapsed: float) -> dict[str, Any]:
    points = state.snapped.points if state.snapped and state.snapped.snapped else []
    validation = state.validation
    incomplete_reasons = (sorted(state.workflow.routing_failures) if state.workflow
                          else ["missing_routing_telemetry"])
    if state.workflow and not points and not state.workflow.routing_requests.get("directions"):
        incomplete_reasons.append("routing_not_measured")
    record: dict[str, Any] = {
        "schema_version": 1, "case": asdict(case),
        "route_hash": route_fingerprint(points) if points else None,
        "points": points,
        "ideal_points": state.route_draft.waypoints if state.route_draft else [],
        "placement": {key: getattr(state.route_draft, key) for key in (
            "center_lat", "center_lon", "scale_m", "rotation_deg", "lat_offset_m", "lon_offset_m",
        )} if state.route_draft else None,
        "elapsed_seconds": elapsed, "failure_stage": failure_stage(state),
        "search_complete": not incomplete_reasons,
        "search_incomplete_reasons": incomplete_reasons,
        "selected_shape": state.shape.name if state.shape else None,
        "shape_source": state.shape.source if state.shape else None,
        "validation": asdict(validation) if validation else None,
        "distance_error_ratio": (
            abs(state.snapped.total_distance_m / 1000 - case.distance_km) / case.distance_km
            if points and state.snapped else None
        ),
        "preflight_placements": state.preflight_count,
        "routing_candidates": state.candidate_count,
        "candidate_metrics": [
            {"shape": candidate.shape_name, "validation": asdict(candidate.validation),
             "rotation_deg": candidate.rotation_deg, "scale_m": candidate.scale_m,
             "lat_offset_m": candidate.lat_offset_m, "lon_offset_m": candidate.lon_offset_m}
            for candidate in state.candidates
        ],
        "search_diagnostics": {
            "reversal_repairs": [row for row in state.history if row.get("agent") == "reversal_repair"],
            "detour_repairs": [row for row in state.history if row.get("agent") == "detour_repair"],
            "contour_reconnections": [row for row in state.history if row.get("agent") == "contour_reconnect"],
            "reference_reconnections": [row for row in state.history if row.get("agent") == "contour_reference"],
            "graph_reconnections": [row for row in state.history if row.get("agent") == "contour_graph"],
            "shape_polish": [row for row in state.history if row.get("agent") == "shape_polish"],
            "component_polish": [row for row in state.history if row.get("agent") == "component_polish"],
            "graph_proposals": [
                {key: row.get(key) for key in ("graph_proposal", "graph_revision", "graph_expansions")}
                for row in state.history if "graph_proposal" in row
            ],
            "adaptive_rounds": [
                {key: row.get(key) for key in ("adaptive_round", "placements", "best_score")}
                for row in state.history if "adaptive_round" in row
            ],
            "feature_repairs": [
                {key: row.get(key) for key in ("feature_id", "variant")}
                for row in state.history if row.get("feature_repair_attempt")
            ],
        },
        "workflow": state.workflow.public_summary() if state.workflow else None,
        # Geometric similarity or model approval cannot fill human labels.
        "human_recognized": None, "manual_edit_count": None,
    }
    if state.shape and state.shape.source != "fallback" and state.shape.name != case.shape and points:
        record["failure_stage"] = "shape_substitution"
    return record


def attach_human_labels(records: list[dict], labels: list[dict]) -> list[dict]:
    keyed = {(row["case_id"], row["route_hash"]): row for row in labels}
    result = []
    for record in records:
        row = dict(record)
        label = keyed.get((row["case"]["id"], row["route_hash"]))
        if label and row["route_hash"]:
            recognized = label.get("recognized")
            edits = label.get("manual_edit_count")
            if not isinstance(recognized, bool):
                raise ValueError("recognized must be a human-provided boolean")
            if edits is not None and (type(edits) is not int or edits < 0):
                raise ValueError("manual_edit_count must be a nonnegative integer or null")
            row.update(human_recognized=recognized, manual_edit_count=edits)
        result.append(row)
    return result


def summary(records: list[dict]) -> dict:
    def mean(values):
        finite = [v for v in values if v is not None and math.isfinite(v)]
        return statistics.mean(finite) if finite else None

    recognized = [row["human_recognized"] for row in records if row.get("human_recognized") is not None]
    return {
        "cases": len(records),
        "incomplete_searches": sum(row.get("search_complete") is False for row in records),
        "unknown_search_completeness": sum("search_complete" not in row for row in records),
        "connected_routes": sum(bool(row.get("points")) for row in records),
        "automatic_passes": sum(row.get("failure_stage") is None for row in records),
        "mean_elapsed_seconds": mean(row.get("elapsed_seconds") for row in records),
        "mean_distance_error_ratio": mean(row.get("distance_error_ratio") for row in records),
        "mean_shape_fidelity": mean((row.get("validation") or {}).get("shape_fidelity") for row in records),
        "human_labeled_cases": len(recognized),
        "human_recognition_rate": mean(recognized),
        "mean_manual_edits": mean(row.get("manual_edit_count") for row in records),
        "mean_feature_preservation": mean((row.get("validation") or {}).get("feature_preservation") for row in records),
        "mean_reversal_similarity": mean((row.get("validation") or {}).get("reversal_similarity") for row in records),
        "mean_api_attempts": mean(sum(row["workflow"].get("routing_requests", {}).values())
                                  if row.get("workflow") else None for row in records),
        "mean_ai_attempts": mean((row.get("workflow") or {}).get("ai", {}).get("attempts") for row in records),
        "failures": {stage: sum(row.get("failure_stage") == stage for row in records)
                     for stage in sorted({row["failure_stage"] for row in records if row.get("failure_stage")})},
    }


def compare(baseline: dict, experiment: dict) -> dict:
    if baseline.get("shape_metric_revision") != experiment.get("shape_metric_revision"):
        raise ValueError("shape metric revisions differ; rerun both variants with the same scoring")
    if baseline.get("network_revision") != experiment.get("network_revision"):
        raise ValueError("network revisions differ; rerun with the same snapshot")
    before = {row["case"]["id"]: row for row in baseline["records"]}
    after = {row["case"]["id"]: row for row in experiment["records"]}
    if before.keys() != after.keys():
        raise ValueError("comparison requires the same case set")
    for key in before:
        if before[key]["case"] != after[key]["case"]:
            raise ValueError("comparison case parameters differ")
        if before[key].get("search_complete") is not True or after[key].get("search_complete") is not True:
            raise ValueError("comparison requires complete searches with routing telemetry; rerun affected cases")
    a, b = summary(list(before.values())), summary(list(after.values()))
    return {
        "baseline": a, "experiment": b,
        "network_revision": baseline.get("network_revision"),
        "shape_metric_revision": baseline.get("shape_metric_revision"),
        "network_revision_supplied": bool(baseline.get("network_revision")),
        "automatic_pass_delta": b["automatic_passes"] - a["automatic_passes"],
        "paired_cases": len(before),
    }


def run_cases(cases, *, variant: str, network_revision: str | None = None, checkpoint=None, runner=None):
    from .config import get_settings
    from .orchestrator import Orchestrator
    from .state import Intent
    from .tools import ors_client, shape_similarity

    run = runner or Orchestrator().run
    settings = get_settings()
    previous = settings.workflow.preflight_adaptive
    previous_graph = settings.routing.shape_graph_enabled
    previous_review = settings.workflow.ai_route_verifier_enabled
    settings.workflow.preflight_adaptive = variant != "baseline"
    settings.routing.shape_graph_enabled = variant in {"graph", "full"}
    settings.workflow.ai_route_verifier_enabled = variant == "full"
    # Only non-secret, relevant configuration is serialized.
    result: dict[str, Any] = {"schema_version": 1, "variant": variant, "network_revision": network_revision,
              "shape_metric_revision": shape_similarity.METRIC_REVISION,
              "configuration": {"adaptive": settings.workflow.preflight_adaptive,
                                "placement_limit": settings.workflow.preflight_max_placements,
                                "guide_points": settings.workflow.preflight_guide_points,
                                "graph_enabled": settings.routing.shape_graph_enabled,
                                "shape_polish_candidates": settings.workflow.shape_polish_candidates
                                if settings.workflow.preflight_adaptive else 0,
                                "route_review_enabled": settings.workflow.ai_route_verifier_enabled,
                                "cache_policy": "directions cold per case; graph and AI process cache shared"},
              "records": []}
    try:
        for case in cases:
            ors_client.clear_directions_cache()
            started = time.perf_counter()
            try:
                state = run(case.prompt, intent_override=Intent(case.shape, None, case.city, case.sport, case.distance_km, None))
                record = result_record(case, state, time.perf_counter() - started)
            except Exception as error:
                # Store only the class; provider exceptions may contain request data.
                record = {"case": asdict(case), "route_hash": None, "points": [],
                          "search_complete": False, "search_incomplete_reasons": ["execution_error"],
                          "elapsed_seconds": time.perf_counter() - started,
                          "failure_stage": "execution_error", "error_type": type(error).__name__,
                          "human_recognized": None, "manual_edit_count": None}
            result["records"].append(record)
            if checkpoint:
                checkpoint(result)
    finally:
        settings.workflow.preflight_adaptive = previous
        settings.routing.shape_graph_enabled = previous_graph
        settings.workflow.ai_route_verifier_enabled = previous_review
    result["summary"] = summary(result["records"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list the 200 cases without network calls")
    parser.add_argument("--run", choices=("baseline", "adaptive", "graph", "full"), help="execute real pipeline (uses configured APIs)")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--case-id", action="append", help="run only selected stable case ids")
    parser.add_argument("--network-revision", help="operator-supplied frozen map/graph revision; absent means live/unverified")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("BASELINE", "EXPERIMENT"))
    parser.add_argument("--labels", type=Path, help="human label JSON array for both comparison files")
    args = parser.parse_args()

    def save(value):
        payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.output.with_suffix(args.output.suffix + ".tmp")
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(args.output)
        else:
            print(payload)

    if args.compare:
        baseline, experiment = [json.loads(path.read_text(encoding="utf-8")) for path in args.compare]
        if args.labels:
            labels = json.loads(args.labels.read_text(encoding="utf-8"))
            for report in (baseline, experiment):
                report["records"] = attach_human_labels(report["records"], labels)
        save(compare(baseline, experiment))
    elif args.list:
        save([asdict(case) for case in benchmark_cases()])
    elif args.run:
        if not 1 <= args.limit <= 200:
            parser.error("--limit must be between 1 and 200")
        cases = benchmark_cases()
        if args.case_id:
            unknown = set(args.case_id) - {case.id for case in cases}
            if unknown:
                parser.error("unknown case ids: " + ", ".join(sorted(unknown)))
            cases = [case for case in cases if case.id in args.case_id]
        save(run_cases(cases[:args.limit], variant=args.run, network_revision=args.network_revision,
                       checkpoint=save if args.output else None))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
