"""Run the full GPS-art pipeline against a sample prompt and print a summary.

Works offline (no API keys): LLM calls use rule-based fallbacks, the snap step
uses a straight-line connector, and geocoding uses a built-in default. Set
OPENAI/ANTHROPIC/ORS keys in .env for real LLM + street snapping.
"""

from __future__ import annotations

import os
import sys

# Allow running as `python scripts/run_demo.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gps_art_wizzard.orchestrator import generate  # noqa: E402


def main() -> None:
    prompt = " ".join(sys.argv[1:]) or "a heart run in Budapest, about 8 km"
    print(f"\n  prompt: {prompt}\n  {'-' * 60}")

    state = generate(prompt)

    v = state.validation
    s = state.snapped
    print(f"  intent     : {state.intent}")
    print(f"  plan       : strategy={state.plan.shape_strategy} "
          f"difficulty={state.plan.difficulty}" if state.plan else "  plan       : (none)")
    print(f"  shape      : {state.shape.name} (source={state.shape.source}, "
          f"closed={state.shape.closed}, paths={len(state.shape.paths)})")
    print(f"  snapped    : {s.snapped}  pts={len(s.points)}  dist={s.total_distance_m/1000:.2f} km")
    print(f"  validation : score={v.score:.3f}  fidelity={v.shape_fidelity:.3f}  "
          f"dist_fit={v.distance_fit:.3f}  closure={v.closure:.3f}")
    if v.issues:
        print(f"  issues     : {v.issues}")
    print(f"  iterations : {state.iterations}  below_threshold={state.below_threshold}")

    out = os.path.join(os.getcwd(), "demo_route.gpx")
    if state.export and state.export.gpx:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(state.export.gpx)
        print(f"\n  GPX written to: {out}")
        print(f"  (also cached at: {state.export.file_paths.get('gpx')})")
    if state.errors:
        print(f"  errors     : {state.errors}")
    print()


if __name__ == "__main__":
    main()
