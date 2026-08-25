"""Night-run readiness from OpenStreetMap street lighting and road class.

The analysis samples the routed polyline at a fixed metric step, assigns every
sample to its nearest tagged highway segment, and aggregates three honest
numbers: how much of the route is lit, how much is explicitly unlit, and how
much sits on roads that carry meaningful car traffic. Contiguous unlit stretches
become map-ready concerns in the same shape as the route-readiness concerns so
the result page can highlight them on the map.

Everything here is planning evidence from a community map, not a safety
guarantee: lighting can change, tags go stale, and temporary closures are
invisible to Overpass.
"""

from __future__ import annotations

import numpy as np

from . import geo, osm_data
from .route_sampling import local_xy, nearest_segment_attributes, sample_route

MAX_WAY_SEGMENTS = 24_000
MIN_DARK_RUN_M = 200.0
MAX_DARK_CONCERNS = 6
MAX_SPAN_KM = 12.0

_MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link"}
_SECONDARY = {"secondary", "secondary_link"}
_TERTIARY = {"tertiary", "tertiary_link", "unclassified", "road"}
_RESIDENTIAL = {"residential", "service", "living_street"}
_LOW_TRAFFIC = {"pedestrian", "cycleway", "path", "footway", "steps", "track", "bridleway"}


def traffic_weight(highway: str) -> float:
    """Relative car-traffic exposure of one OSM highway class (0..1)."""

    if highway in _MAJOR:
        return 0.95
    if highway in _SECONDARY:
        return 0.65
    if highway in _TERTIARY:
        return 0.45
    if highway in _RESIDENTIAL:
        return 0.3
    if highway in _LOW_TRAFFIC:
        return 0.08
    return 0.45


def traffic_label(score: float) -> str:
    if score < 25.0:
        return "low"
    if score < 55.0:
        return "moderate"
    return "high"


def analyse(points: list[tuple[float, float]]) -> dict:
    """Return lighting and traffic exposure evidence for one routed polyline."""

    unavailable: dict = {
        "available": False,
        "status": "unavailable",
        "lit_share": None,
        "unlit_share": None,
        "unknown_share": None,
        "traffic_exposure": None,
        "traffic_label": None,
        "concerns": [],
        "message": "Street-lighting data is temporarily unavailable.",
        "note": "Lighting comes from OpenStreetMap tags that volunteers maintain; verify locally.",
    }
    if len(points) < 2 or geo.path_distance_m(points) <= 0:
        return {**unavailable, "message": "A routed street polyline is needed for the night check."}

    bbox = osm_data.route_bbox(points)
    if osm_data.bbox_span_km(bbox) > MAX_SPAN_KM:
        return {
            **unavailable,
            "message": "This route covers too large an area for a reliable lighting lookup.",
        }

    try:
        ways = osm_data.fetch_lit_highways(bbox)
    except osm_data.OsmUnavailable as error:
        return {**unavailable, "message": str(error)}

    if not ways:
        return {
            **unavailable,
            "status": "review",
            "message": "No tagged street lighting was found around this route.",
        }

    samples = sample_route(points)
    sample_count = len(samples)
    center_lat = sum(point[0] for point in points) / len(points)
    center_lon = sum(point[1] for point in points) / len(points)
    sample_xy = local_xy(
        np.array([point[0] for point in samples]),
        np.array([point[1] for point in samples]),
        center_lat,
        center_lon,
    )

    starts: list[np.ndarray] = []
    ends: list[np.ndarray] = []
    weights: list[float] = []
    lit_values: list[str] = []
    total_segments = 0
    for way in ways:
        total_segments += len(way["points"]) - 1
    stride = max(1, int(np.ceil(total_segments / MAX_WAY_SEGMENTS)))
    kept_segments = 0
    for way_index, way in enumerate(ways):
        way_lat = np.array([point[0] for point in way["points"]])
        way_lon = np.array([point[1] for point in way["points"]])
        coordinates = local_xy(way_lat, way_lon, center_lat, center_lon)
        weight = traffic_weight(way["highway"])
        lit_value = way["lit"]
        for index in range(len(coordinates) - 1):
            if (way_index + index) % stride != 0:
                continue
            if kept_segments >= MAX_WAY_SEGMENTS:
                break
            starts.append(coordinates[index])
            ends.append(coordinates[index + 1])
            weights.append(weight)
            lit_values.append(lit_value)
            kept_segments += 1

    if not kept_segments:
        return {**unavailable, "message": "No usable lighting segments were returned."}

    best_distance, (nearest_weight, nearest_lit) = nearest_segment_attributes(
        sample_xy,
        np.array(starts),
        np.array(ends),
        [np.array(weights), np.array(lit_values, dtype=object)],
    )

    # Samples whose nearest tagged segment is far away carry no real evidence;
    # they count as unknown instead of pretending a neighbouring tag applies.
    far_mask = best_distance > 60.0
    lit_mask = (nearest_lit == "yes") & ~far_mask
    unlit_mask = (nearest_lit == "no") & ~far_mask
    sample_count_f = float(sample_count)
    lit_share = float(lit_mask.sum()) / sample_count_f
    unlit_share = float(unlit_mask.sum()) / sample_count_f
    unknown_share = max(0.0, 1.0 - lit_share - unlit_share)
    evidence = ~far_mask
    exposure = float(nearest_weight[evidence].mean()) * 100.0 if evidence.any() else 100.0
    exposure_label = traffic_label(exposure)

    concerns: list[dict] = []
    run_start: int | None = None
    runs: list[tuple[int, int]] = []
    for index in range(sample_count):
        dark_now = bool(unlit_mask[index])
        if dark_now and run_start is None:
            run_start = index
        if (not dark_now or index == sample_count - 1) and run_start is not None:
            run_end = index - 1 if not dark_now else index
            runs.append((run_start, run_end))
            run_start = None
    step_m = geo.path_distance_m(points) / max(sample_count - 1, 1)
    for order, (start_index, end_index) in enumerate(runs, start=1):
        length_m = (end_index - start_index + 1) * step_m
        if length_m < MIN_DARK_RUN_M:
            continue
        if len(concerns) >= MAX_DARK_CONCERNS:
            break
        section = samples[max(0, start_index - 1) : min(sample_count, end_index + 1)]
        thin = max(1, len(section) // 24)
        concerns.append(
            {
                "code": f"dark_section_{order}",
                "label": f"Unlit stretch {order}",
                "detail": "OpenStreetMap marks this part as not lit; check it before going after dark.",
                "severity": "warning",
                "distance_m": round(length_m),
                "segments_preview": [[lat, lon] for lat, lon in section[::thin]],
            }
        )
    if unknown_share > 0.35:
        concerns.append(
            {
                "code": "lighting_unknown",
                "label": "Lighting data gap",
                "detail": "A large part of the route has no explicit lighting tag in OpenStreetMap.",
                "severity": "info",
                "distance_m": round(unknown_share * geo.path_distance_m(points)),
                "segments_preview": [],
            }
        )

    status = "ready"
    if unlit_share > 0.2 or exposure_label == "high" or unknown_share > 0.4 or concerns:
        status = "review"

    return {
        "available": True,
        "status": status,
        "lit_share": round(lit_share, 3),
        "unlit_share": round(unlit_share, 3),
        "unknown_share": round(unknown_share, 3),
        "traffic_exposure": round(exposure, 1),
        "traffic_label": exposure_label,
        "concerns": concerns,
        "message": (
            "Mostly lit with light traffic."
            if status == "ready"
            else "Check the flagged stretches before heading out after dark."
        ),
        "note": "Lighting and traffic classes come from OpenStreetMap tags; they can be incomplete or stale.",
    }
