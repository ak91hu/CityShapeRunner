"""Run the AI drawing stage against a repeatable multilingual prompt suite."""

from __future__ import annotations

import argparse
import json
import logging
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
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=len(AI_SHAPE_BENCHMARK_CASES))
    parser.add_argument("--case-id", action="append", default=[], help="Run only this stable case id; repeatable")
    parser.add_argument("--language", action="append", default=[], help="Run only this language; repeatable")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument("--city", default="Budapest")
    parser.add_argument("--distance", type=float, default=8.0)
    args = parser.parse_args()

    known_ids = {case.id for case in AI_SHAPE_BENCHMARK_CASES}
    unknown_ids = sorted(set(args.case_id) - known_ids)
    if unknown_ids:
        parser.error("unknown --case-id: " + ", ".join(unknown_ids))
    cases = [
        case
        for case in AI_SHAPE_BENCHMARK_CASES
        if (not args.case_id or case.id in args.case_id)
        and (not args.language or case.language in args.language)
    ][: max(0, args.limit)]

    records: list[dict[str, object]] = []
    for case in cases:
        prompt = f"{case.prompt} in {args.city}, about {args.distance:g} km running"
        state = WorkflowState(prompt=prompt)
        IntentAgent().run(state)
        PlanningAgent().run(state)
        ShapeAgent().run(state)
        if state.shape is None:
            records.append({"id": case.id, "error": "shape stage returned nothing"})
        else:
            record = benchmark_shape_record(case, state.shape)
            record["errors"] = list(state.errors)
            records.append(record)

    scores: list[float] = []
    for record in records:
        score = record.get("semantic_score")
        if isinstance(score, float):
            scores.append(score)
    report = {
        "case_count": len(records),
        "semantic_passes": sum(1 for record in records if record.get("semantic_pass") is True),
        "visually_reviewed": sum(1 for record in records if record.get("visually_reviewed") is True),
        "independently_verified": sum(
            1 for record in records if record.get("independent_verifier") is True
        ),
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
