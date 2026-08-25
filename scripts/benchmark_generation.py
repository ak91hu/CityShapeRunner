"""Benchmark the generation pipeline: wall-clock time plus per-phase durations.

Runs the orchestrator N times on fixed prompts and reports total latency,
phase timings from the workflow trace, candidate counts, and final quality
scores, so optimisation work can be compared against a recorded baseline.

Usage (from the repo root)::

    python scripts/benchmark_generation.py                 # default prompts
    python scripts/benchmark_generation.py --reps 3 "heart in Budapest"
    python scripts/benchmark_generation.py --json          # machine-readable

Works offline (deterministic fallbacks); set ORS/LLM keys in .env to measure
the real generation path.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

# Allow running as `python scripts/benchmark_generation.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gps_art_wizzard.orchestrator import generate  # noqa: E402
from gps_art_wizzard.tools import ors_client  # noqa: E402
from gps_art_wizzard.tools import shape_similarity as ss  # noqa: E402

DEFAULT_PROMPTS = [
    "a heart run in Budapest, about 8 km",
    "draw an arrow bike ride in Vienna",
    "suggest a 12 km run in Debrecen",
]


def run_once(prompt: str) -> dict:
    ors_client.clear_directions_cache()  # cold-cache measurement
    ss._similarity_diagnostics_cached.cache_clear()
    started = time.perf_counter()
    state = generate(prompt)
    elapsed = time.perf_counter() - started

    trace = state.workflow
    phases: dict[str, int] = {}
    if trace is not None:
        completed: dict[tuple[str, int], int] = {}
        for event in trace.events:
            if event.status.value == "completed" and event.duration_ms:
                key = (event.stage, event.attempt)
                prior = completed.get(key)
                completed[key] = min(prior, event.duration_ms) if prior else event.duration_ms
        for stage, duration in completed.items():
            phases[stage[0]] = phases.get(stage[0], 0) + duration

    validation = state.validation
    return {
        "prompt": prompt,
        "total_s": round(elapsed, 2),
        "phases_ms": phases,
        "score": round(validation.score, 4) if validation else None,
        "fidelity": (
            round(validation.shape_fidelity, 4) if validation else None
        ),
        "shape": state.shape.name if state.shape else None,
        "iterations": state.iterations,
        "candidates": state.candidate_count,
        "preflight": state.preflight_count,
        "below_threshold": state.below_threshold,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompts", nargs="*", help="Prompts to benchmark")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    prompts = args.prompts or DEFAULT_PROMPTS
    runs: list[dict] = []
    for prompt in prompts:
        for rep in range(args.reps):
            result = run_once(prompt)
            result["rep"] = rep + 1
            runs.append(result)
            if not args.as_json:
                print(
                    f"[{rep + 1}/{args.reps}] {result['total_s']:>6.2f}s  "
                    f"shape={result['shape']:<12} score={result['score']}  "
                    f"fidelity={result['fidelity']}  "
                    f"iters={result['iterations']}  "
                    f"full-routes={result['candidates']}  "
                    f"preflight={result['preflight']}  "
                    f":: {prompt}"
                )

    if args.as_json:
        print(json.dumps(runs, indent=2))
        return

    totals = [run["total_s"] for run in runs]
    scores = [run["score"] for run in runs if run["score"] is not None]
    print(
        f"\ntotal: n={len(totals)}, mean={statistics.mean(totals):.2f}s"
        + (
            f", median={statistics.median(totals):.2f}s"
            f", stdev={statistics.stdev(totals):.2f}s"
            if len(totals) > 1
            else ""
        )
    )
    if scores:
        print(f"quality: mean score={statistics.mean(scores):.4f}")


if __name__ == "__main__":
    main()
