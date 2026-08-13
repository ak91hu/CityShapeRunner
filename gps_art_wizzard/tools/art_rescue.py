"""GPS-art-specific recording resilience and multi-session rescue tools.

These calculations intentionally run locally and deterministically.  They do
not need a routing API, an account, or a paid navigation service.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import gpxpy
import numpy as np

from . import geo, gpx_writer, shape_similarity

LatLon = tuple[float, float]


@dataclass(frozen=True)
class Recording:
    name: str
    segments: list[list[LatLon]]


def _densify(points: list[LatLon], *, preferred_step_m: float, max_points: int = 5_000) -> list[LatLon]:
    if len(points) < 2:
        return list(points)
    total_distance = geo.path_distance_m(points)
    step_m = max(preferred_step_m, total_distance / max(max_points - 1, 1), 1.0)
    result = [points[0]]
    for start, end in zip(points, points[1:], strict=False):
        distance = geo.haversine(*start, *end)
        count = max(1, int(math.ceil(distance / step_m)))
        for index in range(1, count + 1):
            fraction = index / count
            result.append(
                (
                    start[0] + (end[0] - start[0]) * fraction,
                    start[1] + (end[1] - start[1]) * fraction,
                )
            )
    return result


def _project(points: list[LatLon], center: LatLon) -> np.ndarray:
    return np.asarray(
        [geo.latlon_to_unit(lat, lon, center[0], center[1], 1.0) for lat, lon in points],
        dtype=float,
    )


def _minimum_distances(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    if len(target) == 0:
        return np.full(len(source), np.inf, dtype=float)
    result = np.full(len(source), np.inf, dtype=float)
    for start in range(0, len(source), 256):
        chunk = source[start : start + 256]
        distances = np.hypot(
            chunk[:, np.newaxis, 0] - target[np.newaxis, :, 0],
            chunk[:, np.newaxis, 1] - target[np.newaxis, :, 1],
        )
        result[start : start + len(chunk)] = distances.min(axis=1)
    return result


def _distance_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, enabled in enumerate(mask):
        if enabled and start is None:
            start = index
        if not enabled and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def _downsample(points: list[LatLon], limit: int = 180) -> list[list[float]]:
    if len(points) <= limit:
        selected = points
    else:
        indices = np.linspace(0, len(points) - 1, num=limit, dtype=int)
        selected = [points[int(index)] for index in indices]
    return [[lat, lon] for lat, lon in selected]


def _nonlocal_clearance(points_xy: np.ndarray, exclusion: int, *, closed: bool) -> np.ndarray:
    """Nearest visually separate stroke, excluding neighbours along the route."""

    count = len(points_xy)
    result = np.full(count, np.inf, dtype=float)
    all_indices = np.arange(count)
    for start in range(0, count, 192):
        chunk = points_xy[start : start + 192]
        distances = np.hypot(
            chunk[:, np.newaxis, 0] - points_xy[np.newaxis, :, 0],
            chunk[:, np.newaxis, 1] - points_xy[np.newaxis, :, 1],
        )
        chunk_indices = np.arange(start, start + len(chunk))[:, np.newaxis]
        index_distance = np.abs(chunk_indices - all_indices[np.newaxis, :])
        if closed:
            index_distance = np.minimum(index_distance, count - index_distance)
        distances[index_distance <= exclusion] = np.inf
        result[start : start + len(chunk)] = distances.min(axis=1)
    return result


def inkproof_analysis(points: list[LatLon], accuracy_m: float) -> dict:
    """Estimate whether normal GPS drift can blur recognition-critical details."""

    sampled = _densify(
        points,
        preferred_step_m=max(5.0, min(accuracy_m, 14.0)),
        max_points=2_400,
    )
    center = sampled[len(sampled) // 2]
    points_xy = _project(sampled, center)
    segment_lengths = np.hypot(
        np.diff(points_xy[:, 0]),
        np.diff(points_xy[:, 1]),
    )
    mean_step = max(float(segment_lengths.mean()), 1.0)
    closed = geo.haversine(*sampled[0], *sampled[-1]) <= max(accuracy_m * 2, 30.0)
    exclusion = max(3, int(round(max(accuracy_m * 5, 45.0) / mean_step)))
    clearance = _nonlocal_clearance(points_xy, exclusion, closed=closed)
    proximity_risk = np.clip(1.0 - clearance / max(accuracy_m * 5.0, 25.0), 0.0, 1.0)

    arm = max(2, int(round(max(accuracy_m * 4, 35.0) / mean_step)))
    turn_degrees = np.zeros(len(points_xy), dtype=float)
    for index in range(arm, len(points_xy) - arm):
        incoming = points_xy[index] - points_xy[index - arm]
        outgoing = points_xy[index + arm] - points_xy[index]
        denominator = np.linalg.norm(incoming) * np.linalg.norm(outgoing)
        if denominator <= 1e-9:
            continue
        cosine = float(np.dot(incoming, outgoing) / denominator)
        turn_degrees[index] = math.degrees(math.acos(min(1.0, max(-1.0, cosine))))
    corner_risk = np.clip((turn_degrees - 35.0) / 105.0, 0.0, 1.0) * 0.9
    risk = np.maximum(proximity_risk, corner_risk)
    fragile_mask = risk >= 0.48

    seed_bytes = hashlib.sha256(
        f"{sampled[0]}:{sampled[-1]}:{len(sampled)}:{accuracy_m:.1f}".encode()
    ).digest()[:8]
    rng = np.random.default_rng(int.from_bytes(seed_bytes, "big"))
    simulated_fidelity: list[float] = []
    kernel_size = max(3, min(15, int(round(30.0 / mean_step))))
    kernel = np.ones(kernel_size, dtype=float) / kernel_size
    for _ in range(24):
        raw = rng.normal(0.0, 1.0, size=(len(points_xy), 2))
        drift = np.column_stack(
            [np.convolve(raw[:, axis], kernel, mode="same") for axis in range(2)]
        )
        deviation = np.hypot(drift[:, 0], drift[:, 1])
        scale = accuracy_m / max(float(np.quantile(deviation, 0.95)), 1e-6)
        noisy_xy = points_xy + drift * scale
        noisy = [
            geo.unit_to_latlon(float(x), float(y), center[0], center[1], 1.0)
            for x, y in noisy_xy
        ]
        simulated_fidelity.append(
            shape_similarity.fidelity_between_routes(sampled, noisy, n=96)
        )

    fragile_distance = sum(
        length
        for index, length in enumerate(segment_lengths)
        if fragile_mask[index] or fragile_mask[index + 1]
    )
    total_distance = max(float(segment_lengths.sum()), 1.0)
    fragile_share = fragile_distance / total_distance
    expected_fidelity = float(np.mean(simulated_fidelity))
    resilience_score = min(
        1.0,
        max(0.0, 0.72 * expected_fidelity + 0.28 * (1.0 - fragile_share)),
    )
    rating = "durable" if resilience_score >= 0.84 else "watch" if resilience_score >= 0.68 else "fragile"

    fragile_segments = []
    ranked_runs = sorted(
        _distance_runs(fragile_mask),
        key=lambda run: float(risk[run[0] : run[1] + 1].max()),
        reverse=True,
    )[:8]
    for rank, (start, end) in enumerate(ranked_runs, start=1):
        preview_start = max(0, start - 1)
        preview_end = min(len(sampled) - 1, end + 1)
        segment = sampled[preview_start : preview_end + 1]
        close_strokes = float(np.nanmin(clearance[start : end + 1])) < accuracy_m * 5
        fragile_segments.append(
            {
                "id": f"inkproof-{rank}",
                "label": f"Fragile ink area {rank}",
                "reason": (
                    "Nearby strokes may visually merge when the recorded position drifts."
                    if close_strokes
                    else "A tight turn may be rounded off by sparse or drifting GPS samples."
                ),
                "risk_score": float(risk[start : end + 1].max()),
                "distance_m": geo.path_distance_m(segment),
                "points_preview": _downsample(segment),
            }
        )

    tips = ["Wait for a stable GPS lock before starting the activity."]
    if fragile_segments:
        tips.append("Slow down at the highlighted details so the recorder captures more points.")
        tips.append("If possible, enlarge the drawing or choose a Street Canvas area with wider separation.")
    if accuracy_m >= 15:
        tips.append("Buildings and dense tree cover can exceed this accuracy profile; dual-band GPS can help.")
    return {
        "accuracy_m": accuracy_m,
        "resilience_score": resilience_score,
        "expected_recognition": expected_fidelity,
        "fragile_share": fragile_share,
        "rating": rating,
        "fragile_segments": fragile_segments,
        "tips": tips,
        "method": "24 deterministic correlated-drift simulations plus detail-clearance analysis",
    }


def parse_recording(name: str, xml: str) -> Recording:
    """Read GPX tracks and routes while rejecting XML entity payloads."""

    folded = xml.casefold()
    if "<!doctype" in folded or "<!entity" in folded:
        raise ValueError(f"{name}: unsupported XML declaration")
    try:
        document = gpxpy.parse(xml)
    except Exception as error:  # noqa: BLE001
        raise ValueError(f"{name}: this is not a readable GPX file") from error
    segments: list[list[LatLon]] = []
    for track in document.tracks:
        for segment in track.segments:
            points = [(float(point.latitude), float(point.longitude)) for point in segment.points]
            if len(points) >= 2:
                segments.append(points)
    for route in document.routes:
        points = [(float(point.latitude), float(point.longitude)) for point in route.points]
        if len(points) >= 2:
            segments.append(points)
    if not segments:
        raise ValueError(f"{name}: no track or route with at least two points was found")
    return Recording(name=name, segments=segments)


def rescue_analysis(
    planned_points: list[LatLon],
    recordings: list[Recording],
    *,
    tolerance_m: float,
    name: str,
    sport: str,
) -> dict:
    """Compare completed recordings with the plan and export only missing ink."""

    planned = _densify(
        planned_points,
        preferred_step_m=max(5.0, min(tolerance_m / 2.0, 12.0)),
        max_points=5_000,
    )
    original_segments = [segment for recording in recordings for segment in recording.segments]
    if sum(len(segment) for segment in original_segments) > 80_000:
        raise ValueError("The recordings contain more than 80,000 points; simplify them first.")
    recorded = [
        _densify(
            segment,
            preferred_step_m=max(5.0, min(tolerance_m / 2.0, 12.0)),
            max_points=max(250, 8_000 // max(len(original_segments), 1)),
        )
        for segment in original_segments
    ]
    center = planned[len(planned) // 2]
    planned_xy = _project(planned, center)
    recorded_xy = np.concatenate([_project(segment, center) for segment in recorded])
    plan_distance = _minimum_distances(planned_xy, recorded_xy)
    recorded_distance = _minimum_distances(recorded_xy, planned_xy)
    covered = plan_distance <= tolerance_m
    on_art = recorded_distance <= tolerance_m
    coverage = float(covered.mean())
    precision = float(on_art.mean())
    art_match = 2 * coverage * precision / max(coverage + precision, 1e-9)

    missing_segments = []
    missing_distances_m: list[float] = []
    repair_paths: list[list[LatLon]] = []
    for index, (start, end) in enumerate(_distance_runs(~covered), start=1):
        anchor_start = max(0, start - 1)
        anchor_end = min(len(planned) - 1, end + 1)
        repair = planned[anchor_start : anchor_end + 1]
        distance_m = geo.path_distance_m(repair)
        if distance_m < max(12.0, tolerance_m * 0.6):
            continue
        repair_paths.append(repair)
        missing_distances_m.append(distance_m)
        missing_segments.append(
            {
                "id": f"missing-ink-{index}",
                "label": f"Missing ink {index}",
                "distance_m": distance_m,
                "points_preview": _downsample(repair),
                "gpx": gpx_writer.to_gpx(
                    repair,
                    name=f"{name} - missing ink {index}",
                    sport=sport,
                    total_distance_m=distance_m,
                ),
            }
        )

    recorded_distance_m = sum(geo.path_distance_m(segment) for segment in original_segments)
    missing_distance_m = sum(missing_distances_m)
    return {
        "recording_count": len(recordings),
        "track_segment_count": len(original_segments),
        "coverage": coverage,
        "precision": precision,
        "art_match": art_match,
        "tolerance_m": tolerance_m,
        "recorded_distance_km": recorded_distance_m / 1000,
        "missing_distance_km": missing_distance_m / 1000,
        "missing_segments": missing_segments,
        "recorded_segments_preview": [_downsample(segment, 260) for segment in original_segments],
        "merged_recording_gpx": gpx_writer.to_segmented_gpx(
            original_segments,
            name=f"{name} - combined recordings",
            sport=sport,
        ),
        "missing_ink_gpx": (
            gpx_writer.to_segmented_gpx(
                repair_paths,
                name=f"{name} - missing ink mission",
                sport=sport,
            )
            if repair_paths
            else None
        ),
        "message": (
            "The planned drawing is fully covered at this tolerance."
            if not missing_segments
            else f"{len(missing_segments)} separate repair mission(s) can complete the drawing."
        ),
        "authenticity": "The combined GPX contains recorded points only; repair routes are separate and untimed.",
        "privacy": "Files were analysed in memory and were not stored.",
    }
