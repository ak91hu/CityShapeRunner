"""Exact graph-search ablation on recorded real-road drawing references.

No provider calls. This measures graph CPU work, not generation wall time.
The baseline graph module is loaded directly from the named Git revision.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import types
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gps_art_wizzard.tools import ors_client, street_graph  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recorded", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-ref", default="HEAD")
    args = parser.parse_args()
    name = "gps_art_wizzard.tools._graph_baseline"
    baseline = types.ModuleType(name)
    sys.modules[name] = baseline
    source = subprocess.check_output(["git", "show", f"{args.baseline_ref}:gps_art_wizzard/tools/street_graph.py"], cwd=ROOT)
    exec(compile(source, name, "exec"), baseline.__dict__)
    raw = json.loads(args.snapshot.read_text(encoding="utf-8"))
    elements = raw["elements"]
    records = json.loads(args.recorded.read_text(encoding="utf-8"))["records"]
    graphs = {(sport, version): module.build_graph(elements, sport) for sport in ("run", "bike")
              for version, module in (("original", baseline), ("current", street_graph))}
    output = []
    for row in records:
        if row["variant"] != "original":
            continue
        guides = ors_client._subsample(row["ideal_points"], closed=True, max_points=18)
        timings, proposals = {}, {}
        for version, module in (("original", baseline), ("current", street_graph)):
            timings[version] = []
            for _ in range(3):
                started = time.perf_counter()
                result = module.shape_route(graphs[row["case"]["sport"], version], guides,
                                            target_m=row["case"]["distance_km"] * 1000,
                                            closed=True, seconds=60, max_expansions=30000)
                timings[version].append(time.perf_counter() - started)
                proposals[version] = asdict(result) if result else None
        identical = proposals["original"] == proposals["current"]
        output.append({"case": row["case"]["id"], "identical_proposal": identical,
                       "timings_seconds": timings,
                       "median_speedup": statistics.median(timings["original"]) / statistics.median(timings["current"]),
                       "expansions": (proposals["current"] or {}).get("expanded"),
                       "proposal_found": proposals["current"] is not None})
        print(json.dumps(output[-1]), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"method": "Three calls per reference; 60s nonbinding wall budget, same 30000 expansion cap; includes first cold cache call.",
                                      "cases": output}, indent=2) + "\n", encoding="utf-8")
    if not all(row["identical_proposal"] for row in output):
        raise SystemExit("Graph search changed a proposal")


if __name__ == "__main__":
    main()
