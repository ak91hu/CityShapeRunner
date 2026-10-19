"""Compare current scoring against a Git revision on identical geometry.

Catalog perturbations are synthetic diagnostics, never road-route evidence.
Optional recorded results retain their original provider provenance. This audit
does not claim that changed placement searches return identical routes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import types
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gps_art_wizzard.tools import geo, shape_library, shape_similarity  # noqa: E402


def git_source(ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)


def baseline_scorer(ref: str):
    name = "gps_art_wizzard.tools._accuracy_baseline"
    module = types.ModuleType(name)
    sys.modules[name] = module
    source = git_source(ref, "gps_art_wizzard/tools/shape_similarity.py")
    exec(compile(source, f"{ref}:shape_similarity.py", "exec"), module.__dict__)
    return module


def catalog_pairs():
    for name in shape_library.SHAPES:
        _, paths, _ = shape_library.get_shape(name)
        xy = geo.stitch_paths(paths)
        reference = [geo.unit_to_latlon(x, y, 47.5, 19, 1800) for x, y in xy]
        middle = len(reference) // 2
        yield f"{name}:identity", reference, reference
        yield f"{name}:shift", reference, [(lat + 0.0004, lon - 0.0003) for lat, lon in reference]
        yield f"{name}:stretch", reference, [(lat, 19 + (lon - 19) * 1.3) for lat, lon in reference]
        # Remove an interior part while retaining the route endpoints.
        trimmed = reference[:max(1, middle - len(reference) // 8)] + reference[middle + len(reference) // 8:]
        yield f"{name}:missing-section", reference, trimmed


def recorded_pairs(paths):
    seen = set()
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("records", [data]) if isinstance(data, dict) else data
        for index, row in enumerate(rows):
            points, ideal = row.get("points"), row.get("ideal_points")
            evidence = (row.get("workflow") or {}).get("routing_requests", {}).get("directions", 0)
            if not points or not ideal or not evidence:
                continue
            fingerprint = hashlib.sha256(json.dumps([ideal, points]).encode()).hexdigest()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            yield f"{path.name}:record-{index}", ideal, points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="HEAD")
    parser.add_argument("--recorded", nargs="*", type=Path, default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", args.baseline_ref], cwd=ROOT, text=True).strip()
    original = baseline_scorer(revision)
    invariant_files = (
        "quality.py", "agents/validation_agent.py", "agents/export_agent.py",
        "tools/geo.py", "tools/route_safety.py", "tools/gpx_writer.py",
        "tools/shape_library.py", "tools/extended_shape_catalog.py", "tools/hungarian_shape_catalog.py",
    )
    unchanged = {}
    for relative in invariant_files:
        path = "gps_art_wizzard/" + relative
        old = git_source(revision, path).replace(b"\r\n", b"\n")
        current = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
        unchanged[path] = old == current

    counts = {"catalog_geometry_pairs": 0, "recorded_provider_geometry_pairs": 0, "metric_comparisons": 0}
    differences = []
    maximum = 0.0
    for kind, pairs in (("catalog_geometry_pairs", catalog_pairs()),
                        ("recorded_provider_geometry_pairs", recorded_pairs(args.recorded))):
        for label, reference, candidate in pairs:
            counts[kind] += 1
            for n, floor in ((64, 64), (128, 256)):
                kwargs = {"n": n, "closed_sample_floor": floor}
                before = asdict(original.similarity_diagnostics_between_routes(reference, candidate, **kwargs))
                after = asdict(shape_similarity.similarity_diagnostics_between_routes(reference, candidate, **kwargs))
                counts["metric_comparisons"] += 1
                delta = {key: abs(before[key] - after[key]) for key in before if before[key] != after[key]}
                if delta:
                    differences.append({"case": label, "samples": n, "differences": delta})
                    maximum = max(maximum, max(delta.values()))
            if counts[kind] % 25 == 0:
                print(json.dumps({"progress": kind, "pairs_checked": counts[kind], "differences": len(differences)}), flush=True)
    report = {
        "created_at": datetime.now(UTC).isoformat(), "baseline_commit": revision,
        "catalog_templates": len(shape_library.SHAPES), **counts,
        "bit_identical_metric_results": not differences,
        "maximum_absolute_metric_difference": maximum if math.isfinite(maximum) else str(maximum),
        "unchanged_quality_and_geometry_files": unchanged,
        "differences": differences,
        "recorded_inputs": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                            for path in args.recorded],
        "limits": ["Same-input numerical audit; not a paired live placement-search benchmark.",
                   "Recorded Directions provenance comes from the saved workflow telemetry.",
                   "Human recognizability and future routing-provider changes are not measured."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "baseline_commit", "catalog_templates", *counts, "bit_identical_metric_results",
        "maximum_absolute_metric_difference", "unchanged_quality_and_geometry_files",
    )}), flush=True)
    if differences or not all(unchanged.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
