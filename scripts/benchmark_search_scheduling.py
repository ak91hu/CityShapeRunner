"""Measure initial-placement scheduling with a synthetic delayed router.

No network requests, model calls or real-world route-quality claims. This
isolates scheduling latency with identical candidates and validation in both
variants, rather than predicting a complete production request's duration.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, replace
from pathlib import Path

from gps_art_wizzard.config import get_settings
from gps_art_wizzard.orchestrator import Orchestrator
from gps_art_wizzard.state import RouteDraft, SnappedRoute, Validation, WorkflowState
from gps_art_wizzard.workflow_runtime import WorkflowRuntime


def measure(workers: int, delay: float) -> dict:
    state = WorkflowState("synthetic scheduling benchmark", search_seed=123)
    state.route_draft = RouteDraft(47.5, 19, 600, 0, 0, 0, 0.8,
                                   [(47.5, 19), (47.501, 19.001)], False)
    state.placement_candidates = [replace(state.route_draft, lon_offset_m=value) for value in (1000, 2000)]

    class Router:
        def run(self, trial):
            time.sleep(delay)
            trial.candidate_count += 1
            trial.snapped = SnappedRoute(trial.route_draft.waypoints, 150, True)

    class Validator:
        def run(self, trial):
            score = 0.80 + trial.route_draft.lon_offset_m / 20_000
            trial.validation = Validation(score, 1, 1, score)

    config = get_settings().workflow
    previous = config.measurement_workers, config.initial_placement_candidates
    try:
        config.measurement_workers, config.initial_placement_candidates = workers, 3
        runtime = WorkflowRuntime(state, max_duration_seconds=175, max_llm_calls=0)
        started = time.perf_counter()
        Orchestrator({})._measure_initial_placements(state, {"snap": Router(), "validation": Validator()}, runtime)
        elapsed = time.perf_counter() - started
    finally:
        config.measurement_workers, config.initial_placement_candidates = previous
    return {"seconds": elapsed, "measurements": state.candidate_count,
            "selected_offset_m": state.route_draft.lon_offset_m,
            "validation": asdict(state.validation)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 0 <= args.delay <= 2 or not 1 <= args.repeats <= 20:
        parser.error("delay must be 0–2 seconds and repeats 1–20")
    serial, parallel = [], []
    for _ in range(args.repeats):
        serial.append(measure(1, args.delay))
        parallel.append(measure(3, args.delay))
    before = statistics.median(row["seconds"] for row in serial)
    after = statistics.median(row["seconds"] for row in parallel)
    unchanged = all((a["selected_offset_m"], a["validation"], a["measurements"]) ==
                    (b["selected_offset_m"], b["validation"], b["measurements"])
                    for a, b in zip(serial, parallel, strict=True))
    report = {"kind": "synthetic scheduling microbenchmark", "network_calls": 0,
              "delay_seconds": args.delay, "repeats": args.repeats,
              "serial_median_seconds": before, "parallel_median_seconds": after,
              "speedup": before / max(after, 1e-9), "same_candidates_and_validation": unchanged}
    output = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    if not unchanged:
        raise SystemExit("Scheduling changed the selected candidate or validation")


if __name__ == "__main__":
    main()
