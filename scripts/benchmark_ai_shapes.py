"""Run the AI drawing stage against a repeatable multilingual prompt suite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gps_art_wizzard.agents.intent_agent import IntentAgent
from gps_art_wizzard.agents.planning_agent import PlanningAgent
from gps_art_wizzard.agents.shape_agent import ShapeAgent
from gps_art_wizzard.ai_shape_benchmark import (
    AI_SHAPE_BENCHMARK_CASES,
    benchmark_shape_record,
)
from gps_art_wizzard.state import WorkflowState


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=len(AI_SHAPE_BENCHMARK_CASES))
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument("--city", default="Budapest")
    parser.add_argument("--distance", type=float, default=8.0)
    args = parser.parse_args()

    records: list[dict[str, object]] = []
    for case in AI_SHAPE_BENCHMARK_CASES[: max(0, args.limit)]:
        prompt = f"{case.prompt} in {args.city}, about {args.distance:g} km running"
        state = WorkflowState(prompt=prompt)
        IntentAgent().run(state)
        PlanningAgent().run(state)
        ShapeAgent().run(state)
        if state.shape is None:
            records.append({"id": case.id, "error": "shape stage returned nothing"})
        else:
            records.append(benchmark_shape_record(case, state.shape))

    scores = [record["semantic_score"] for record in records if isinstance(record.get("semantic_score"), float)]
    report = {
        "case_count": len(records),
        "independently_verified": sum(bool(record.get("independent_verifier")) for record in records),
        "mean_semantic_score": sum(scores) / len(scores) if scores else None,
        "fallback_count": sum(record.get("source") == "fallback" for record in records),
        "records": records,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

