"""Run the original and current generators against live ORS on paired inputs.

Source trees are frozen before the experiment. Every workflow runs in a fresh
process, uses the same supplied OSM snapshot, and makes its own provider calls.
HTTP evidence excludes credentials. Failed/incomplete runs are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    {"id": "heart-run-5", "city": "Szeged", "shape": "heart", "sport": "run", "distance_km": 5},
    {"id": "star-run-5", "city": "Szeged", "shape": "star", "sport": "run", "distance_km": 5},
    {"id": "triangle-run-5", "city": "Szeged", "shape": "triangle", "sport": "run", "distance_km": 5},
    {"id": "circle-run-5", "city": "Szeged", "shape": "circle", "sport": "run", "distance_km": 5},
    {"id": "star-run-10", "city": "Szeged", "shape": "star", "sport": "run", "distance_km": 10},
    {"id": "heart-bike-15", "city": "Szeged", "shape": "heart", "sport": "bike", "distance_km": 15},
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def source_hash(folder: Path) -> str:
    files = sorted(path for path in folder.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    return hashlib.sha256("\n".join(f"{path.relative_to(folder).as_posix()}:{digest(path)}" for path in files).encode()).hexdigest()


def prepare_sources(output: Path, ref: str, snapshot: Path, rate_limit: int):
    revision = subprocess.check_output(["git", "rev-parse", ref], cwd=ROOT, text=True).strip()
    baseline, current = output / "original-src", output / "current-src"
    if baseline.exists() or current.exists():
        raise ValueError("Use a new output directory; source snapshots must not be overwritten")
    baseline.mkdir()
    archive = subprocess.check_output(["git", "archive", "--format=zip", revision, "gps_art_wizzard", "config/settings.yaml"], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        if any(not (baseline / item.filename).resolve().is_relative_to(baseline.resolve()) for item in zipped.infolist()):
            raise ValueError("Unsafe archive path")
        zipped.extractall(baseline)
    shutil.copytree(ROOT / "gps_art_wizzard", current / "gps_art_wizzard", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (current / "config").mkdir()
    shutil.copy2(ROOT / "config/settings.yaml", current / "config/settings.yaml")
    shared_snapshot = output / "osm-snapshot.json"
    shutil.copy2(snapshot, shared_snapshot)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(), "original_commit": revision,
        "source_hashes": {"original": source_hash(baseline), "current": source_hash(current)},
        "osm_snapshot_sha256": digest(shared_snapshot), "osm_snapshot_source": str(snapshot),
        "benchmark_driver_sha256": digest(Path(__file__)),
        "request_limit_per_60_seconds": rate_limit,
        "cases": CASES, "seed_policy": "SHA256(case id), first 32 bits; original search is deterministic",
        "method": "Fresh process and fresh live routing evidence for every run; alternating AB/BA order.",
        "limits": ["One city; these cases do not establish quality in every city.",
                   "OSM search snapshot is fixed; live ORS engine/network revisions are recorded.",
                   "One timing observation per paired input; no population-level latency claim.",
                   "Geometric checks are not human recognizability labels.",
                   "Generation wall time includes benchmark quota waits; quota waits are reported separately."],
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def worker(args):
    output = args.output_dir.resolve()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    case = manifest["cases"][args.case_index]
    sys.path.insert(0, str(output / f"{args.variant}-src"))
    # Same deterministic catalog/planning mode, profile, distance and city in
    # both variants. Only the new search has a seed and initial parallel stage.
    os.environ.update(GEOCODE_OFFLINE="1", LLM_USAGE_MODE="essential",
                      AI_ROUTE_VERIFIER_ENABLED="false", AI_SHAPE_VERIFIER_ENABLED="false",
                      SHAPE_GRAPH_SNAPSHOT=str(output / "osm-snapshot.json"))
    import gpxpy
    import httpx

    from gps_art_wizzard.config import get_settings
    from gps_art_wizzard.orchestrator import Orchestrator
    from gps_art_wizzard.quality import quality_gate_report
    from gps_art_wizzard.state import Intent
    from gps_art_wizzard.tools import geo, ors_client

    cfg = get_settings()
    if not cfg.routing.ors_api_key:
        raise ValueError("ORS credential missing")
    started = time.perf_counter()
    latest = {}
    records, received = [], []
    lock, stopped = threading.Lock(), threading.Event()
    quota_lock = threading.Lock()
    quota_file = output / "request-start-times.json"
    quota_starts = json.loads(quota_file.read_text()) if quota_file.exists() else []
    quota_aborted = False
    original_post = httpx.Client.post

    def capture(client, url, *positional, **kwargs):
        nonlocal quota_aborted
        waiting_since = time.perf_counter()
        with quota_lock:
            if quota_aborted:
                raise RuntimeError("Benchmark stopped provider calls after a quota rejection")
            while True:
                now = time.time()
                quota_starts[:] = [stamp for stamp in quota_starts if now - stamp < 60.5]
                if len(quota_starts) < manifest["request_limit_per_60_seconds"]:
                    break
                time.sleep(max(0.01, min(60, quota_starts[0] + 60.5 - now)))
            quota_starts.append(time.time())
            write_json(quota_file, quota_starts)
        begin = time.perf_counter()
        request = {"endpoint": str(url), "body": kwargs.get("json"), "started_seconds": begin - started,
                   "quota_wait_start_seconds": waiting_since - started,
                   "quota_wait_seconds": begin - waiting_since}
        try:
            response = original_post(client, url, *positional, **kwargs)
            request["http_status"] = response.status_code
            request["quota_headers"] = {key: value for key, value in response.headers.items()
                                        if "ratelimit" in key.lower() or key.lower() == "retry-after"}
            if response.status_code == 429:
                quota_aborted = True
            try:
                body = response.json()
                request["engine"] = body.get("metadata", {}).get("engine")
                if response.status_code == 200:
                    request["response"] = body
                else:
                    request["error_code"] = (body.get("error") or {}).get("code") if isinstance(body.get("error"), dict) else None
            except (ValueError, AttributeError):
                request["invalid_json"] = True
            return response
        except httpx.HTTPError as exc:
            request["transport_error"] = type(exc).__name__
            raise
        finally:
            request["duration_seconds"] = time.perf_counter() - begin
            with lock:
                records.append(request)

    httpx.Client.post = capture
    original_snap = ors_client.snap_route_detailed

    def snap(*positional, **kwargs):
        result = original_snap(*positional, **kwargs)
        if result[2]:
            with lock:
                received.append(list(result[0]))
        return result

    ors_client.snap_route_detailed = snap

    def progress(data):
        with lock:
            latest.update(stage=data.get("stage"), elapsed_ms=data.get("elapsed_ms"),
                          routing_requests=data.get("routing_requests"))

    def heartbeat():
        while not stopped.wait(15):
            with lock:
                data = dict(latest)
            print(json.dumps({"heartbeat": True, "variant": args.variant, "case": case["id"],
                              "wall_seconds": round(time.perf_counter() - started, 1), **data}), flush=True)

    threading.Thread(target=heartbeat, daemon=True).start()
    seed = int.from_bytes(hashlib.sha256(case["id"].encode()).digest()[:4], "big")
    options = {"intent_override": Intent(case["shape"], None, case["city"], case["sport"], case["distance_km"], None),
               "event_sink": progress}
    if args.variant == "current":
        options["search_seed"] = seed
    row = {"case": case, "variant": args.variant, "search_seed": seed if args.variant == "current" else None,
           "source_sha256": manifest["source_hashes"][args.variant],
           "osm_snapshot_sha256": manifest["osm_snapshot_sha256"], "started_at": datetime.now(UTC).isoformat()}
    try:
        prompt = f"draw a {case['shape']} in {case['city']}, {case['distance_km']} km, {case['sport']}"
        state = Orchestrator().run(prompt, **options)
        points = state.snapped.points if state.snapped and state.snapped.snapped else []
        row.update(points=points, ideal_points=state.route_draft.waypoints if state.route_draft else [],
                   validation=asdict(state.validation) if state.validation else None,
                   road_connected=bool(points), provider_geometry_preserved=bool(points and points in received),
                   selected_shape=state.shape.name if state.shape else None,
                   quality=quality_gate_report(state.validation, closed=bool(state.shape and state.shape.closed)),
                   workflow=state.workflow.public_summary(), candidate_count=state.candidate_count,
                   preflight_count=state.preflight_count, errors=state.errors,
                   history=state.history, iterations=state.iterations,
                   candidate_metrics=[{"shape": c.shape_name, "validation": asdict(c.validation),
                                       "points": c.points,
                                       "provider_geometry_preserved": c.points in received,
                                       "rotation_deg": c.rotation_deg, "scale_m": c.scale_m,
                                       "lat_offset_m": c.lat_offset_m, "lon_offset_m": c.lon_offset_m}
                                      for c in state.candidates])
        if points and state.export:
            gpx = gpxpy.parse(state.export.gpx)
            exported = [(p.latitude, p.longitude) for t in gpx.tracks for s in t.segments for p in s.points]
            row["gpx_vertex_count_preserved"] = len(exported) == len(points)
            row["gpx_max_error_m"] = max(geo.haversine(*a, *b) for a, b in zip(points, exported, strict=True))
        row["configuration"] = {
            "max_duration_seconds": cfg.workflow.max_duration_seconds,
            "optimization_budget_seconds": getattr(cfg.workflow, "optimization_budget_seconds", None),
            "max_refinement_iterations": cfg.workflow.max_refinement_iterations,
            "preflight_max_placements": cfg.workflow.preflight_max_placements,
            "preflight_guide_points": cfg.workflow.preflight_guide_points,
            "measurement_workers": cfg.workflow.measurement_workers,
            "initial_placement_candidates": getattr(cfg.workflow, "initial_placement_candidates", 1),
            "shape_graph_seconds": cfg.routing.shape_graph_seconds,
            "llm_usage_mode": cfg.llm.usage_mode, "ors_preference": cfg.routing.preference,
        }
    except Exception as exc:
        row.update(execution_error=type(exc).__name__, points=[], road_connected=False)
    finally:
        stopped.set()
        row["elapsed_seconds"] = time.perf_counter() - started
        engines = {json.dumps(r["engine"], sort_keys=True) for r in records if r.get("engine")}
        row["ors_engines"] = [json.loads(engine) for engine in sorted(engines)]
        row["http_requests"] = len(records)
        intervals = sorted((r["quota_wait_start_seconds"], r["started_seconds"]) for r in records
                           if r["quota_wait_seconds"] >= 0.01)
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        row["quota_wait_union_seconds"] = sum(end - start for start, end in merged)
        row["quota_wait_intervals"] = merged
        row["quota_aborted"] = quota_aborted
        stem = output / f"{case['id']}-{args.variant}"
        write_json(stem.with_suffix(".http.json"), records)
        write_json(stem.with_suffix(".json"), row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline-ref", default="1dee20f")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--case-index", type=int)
    parser.add_argument("--variant", choices=("original", "current"))
    parser.add_argument("--request-limit", type=int, default=35)
    parser.add_argument("--original-results", type=Path,
                        help="Reuse a disclosed previous original run with identical source, cases and OSM snapshot")
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    if args.snapshot is None:
        parser.error("--snapshot is required")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not 1 <= args.request_limit <= 35:
        parser.error("--request-limit must be between 1 and 35")
    manifest = prepare_sources(output, args.baseline_ref, args.snapshot.resolve(), args.request_limit)
    previous = {}
    if args.original_results:
        supplied = json.loads(args.original_results.read_text(encoding="utf-8"))
        prior_manifest = supplied["manifest"]
        if (prior_manifest["source_hashes"]["original"] != manifest["source_hashes"]["original"]
                or prior_manifest["osm_snapshot_sha256"] != manifest["osm_snapshot_sha256"]
                or prior_manifest["cases"] != manifest["cases"]):
            raise ValueError("Original evidence has different source, OSM snapshot or test cases")
        previous = {row["case"]["id"]: row for row in supplied["records"] if row["variant"] == "original"}
        if len(previous) != len(manifest["cases"]):
            raise ValueError("Original evidence does not cover every case")
        manifest["original_evidence_reused_from"] = str(args.original_results.resolve())
        manifest["method"] = "Fresh current runs; disclosed previously recorded original runs with identical source/cases/OSM. Live engine identity checked per pair."
        manifest["limits"].append("Original timing observations were recorded earlier, not interleaved with these current runs.")
        write_json(output / "manifest.json", manifest)
    all_results = []
    for index, case in enumerate(manifest["cases"]):
        # Balance order effects without running competing workflows at once.
        order = ("original", "current") if index % 2 == 0 else ("current", "original")
        for variant in order:
            if variant == "original" and previous:
                row = previous[case["id"]]
                for suffix in (".json", ".http.json"):
                    shutil.copy2(args.original_results.parent / f"{case['id']}-original{suffix}",
                                 output / f"{case['id']}-original{suffix}")
                all_results.append(row)
                write_json(output / "results.json", {"manifest": manifest, "records": all_results})
                print(json.dumps({"reused_original_evidence": case["id"]}), flush=True)
                continue
            print(json.dumps({"started": case, "variant": variant}), flush=True)
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--output-dir", str(output),
                       "--case-index", str(index), "--variant", variant]
            with (output / f"{case['id']}-{variant}.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True, encoding="utf-8", errors="replace")
                for line in process.stdout:
                    log.write(line)
                    if line.startswith('{"heartbeat":'):
                        print(line.rstrip(), flush=True)
                process.wait()
            path = output / f"{case['id']}-{variant}.json"
            if not path.exists():
                raise RuntimeError(f"Worker failed with exit code {process.returncode}: {case['id']} {variant}")
            row = json.loads(path.read_text(encoding="utf-8"))
            all_results.append(row)
            write_json(output / "results.json", {"manifest": manifest, "records": all_results})
            print(json.dumps({"finished": case["id"], "variant": variant,
                              "seconds": round(row["elapsed_seconds"], 2),
                              "fidelity": (row.get("validation") or {}).get("shape_fidelity"),
                              "connected": row["road_connected"],
                              "failed_gates": row.get("quality", {}).get("failed_gates"),
                              "routing_failures": row.get("workflow", {}).get("routing_failures")}), flush=True)
            if row.get("quota_aborted"):
                raise RuntimeError("Provider quota rejection: experiment stopped; failed run retained")


if __name__ == "__main__":
    main()
