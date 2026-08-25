"""Wheelchair and step accessibility evidence for a routed polyline.

The layer mirrors the night-readiness contract: sample the route, assign every
sample to its nearest OSM-tagged highway segment, and report honest shares of
explicitly accessible, restricted, and barrier (steps) ground plus an unpaved
share. Flagged barrier stretches reuse the readiness-concern shape so the map
can highlight exactly where a wheelchair user would be blocked.

OpenStreetMap accessibility tags are sparse and volunteer-maintained: an
untagged street is not an accessible street, only an unknown one.
"""

from __future__ import annotations

import numpy as np

from . import geo, osm_data
from .route_sampling import local_xy, nearest_segment_attributes, sample_route

MAX_WAY_SEGMENTS = 24_000
MIN_BARRIER_RUN_M = 30.0
MAX_BARRIER_CONCERNS = 6
MAX_SPAN_KM = 12.0

_CLASS_ORDER = {
    "steps": 0,
    "wheelchair_no": 1,
    "wheelchair_limited": 2,
    "unpaved": 3,
    "wheelchair_yes": 4,
    "paved": 5,
    "untagged": 6,
}


def _class_label(class_value: str) -> str:
    return {
        "steps": "Steps",
        "wheelchair_no": "Wheelchair: no",
        "wheelchair_limited": "Wheelchair: limited",
        "unpaved": "Unpaved surface",
        "wheelchair_yes": "Wheelchair: yes",
        "paved": "Paved surface",
        "untagged": "Untagged",
    }.get(class_value, class_value)


def analyse(points: list[tuple[float, float]]) -> dict:
    """Return accessibility evidence for one routed polyline."""

    unavailable: dict = {
        "available": False,
        "status": "unavailable",
        "wheelchair_yes_share": None,
        "wheelchair_no_share": None,
        "steps_share": None,
        "unpaved_share": None,
        "untagged_share": None,
        "concerns": [],
        "message": "Accessibility data is temporarily unavailable.",
        "note": "Accessibility tags come from OpenStreetMap volunteers; untagged does not mean accessible.",
    }
    if len(points) < 2 or geo.path_distance_m(points) <= 0:
        return {
            **unavailable,
            "message": "A routed street polyline is needed for the accessibility check.",
        }

    bbox = osm_data.route_bbox(points)
    if osm_data.bbox_span_km(bbox) > MAX_SPAN_KM:
        return {
            **unavailable,
            "message": "This route covers too large an area for a reliable accessibility lookup.",
        }

    try:
        ways = osm_data.fetch_accessibility_ways(bbox)
    except osm_data.OsmUnavailable as error:
        return {**unavailable, "message": str(error)}

    if not ways:
        return {
            **unavailable,
            "status": "unavailable",
            "message": "No accessibility-tagged streets were found around this route.",
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
    classes: list[str] = []
    total_segments = 0
    for way in ways:
        total_segments += len(way["points"]) - 1
    stride = max(1, int(np.ceil(total_segments / MAX_WAY_SEGMENTS)))
    kept_segments = 0
    for way_index, way in enumerate(ways):
        way_lat = np.array([point[0] for point in way["points"]])
        way_lon = np.array([point[1] for point in way["points"]])
        coordinates = local_xy(way_lat, way_lon, center_lat, center_lon)
        class_value = way["class"]
        for index in range(len(coordinates) - 1):
            if (way_index + index) % stride != 0:
                continue
            if kept_segments >= MAX_WAY_SEGMENTS:
                break
            starts.append(coordinates[index])
            ends.append(coordinates[index + 1])
            classes.append(class_value)
            kept_segments += 1

    if not kept_segments:
        return {**unavailable, "message": "No usable accessibility segments were returned."}

    best_distance, (nearest_class,) = nearest_segment_attributes(
        sample_xy,
        np.array(starts),
        np.array(ends),
        [np.array(classes, dtype=object)],
    )

    far_mask = best_distance > 60.0
    resolved_class = np.where(far_mask, "untagged", nearest_class)

    def share(class_value: str) -> float:
        return float((resolved_class == class_value).sum()) / float(sample_count)

    wheelchair_yes = share("wheelchair_yes")
    wheelchair_no = share("wheelchair_no") + share("wheelchair_limited")
    steps = share("steps")
    unpaved = share("unpaved")
    paved = share("paved")
    untagged = share("untagged")

    step_m = geo.path_distance_m(points) / max(sample_count - 1, 1)
    barrier_classes = {"steps", "wheelchair_no"}
    concerns: list[dict] = []
    run_start: int | None = None
    run_class = ""
    runs: list[tuple[int, int, str]] = []
    for index in range(sample_count):
        current = str(resolved_class[index])
        is_barrier = current in barrier_classes
        if is_barrier and (run_start is None or current != run_class):
            if run_start is not None:
                runs.append((run_start, index - 1, run_class))
            run_start, run_class = index, current
        if not is_barrier and run_start is not None:
            runs.append((run_start, index - 1, run_class))
            run_start, run_class = None, ""
    if run_start is not None:
        runs.append((run_start, sample_count - 1, run_class))

    for order, (start_index, end_index, class_value) in enumerate(runs, start=1):
        length_m = (end_index - start_index + 1) * step_m
        if length_m < MIN_BARRIER_RUN_M:
            continue
        if len(concerns) >= MAX_BARRIER_CONCERNS:
            break
        section = samples[max(0, start_index - 1) : min(sample_count, end_index + 1)]
        thin = max(1, len(section) // 24)
        is_steps = class_value == "steps"
        concerns.append(
            {
                "code": f"barrier_{order}",
                "label": f"{_class_label(class_value)} stretch {order}",
                "detail": (
                    "Steps make this section impassable for wheels."
                    if is_steps
                    else "OpenStreetMap marks this section as not wheelchair accessible."
                ),
                "severity": "warning",
                "distance_m": round(length_m),
                "segments_preview": [[lat, lon] for lat, lon in section[::thin]],
            }
        )

    status = "ready"
    if concerns or wheelchair_no > 0.15 or steps > 0.01:
        status = "review"

    return {
        "available": True,
        "status": status,
        "wheelchair_yes_share": round(wheelchair_yes, 3),
        "wheelchair_no_share": round(wheelchair_no, 3),
        "steps_share": round(steps, 3),
        "unpaved_share": round(unpaved, 3),
        "paved_share": round(paved, 3),
        "untagged_share": round(untagged, 3),
        "concerns": concerns,
        "message": (
            "No tagged barriers on this route."
            if status == "ready"
            else "Check the flagged sections before planning a wheelchair or stroller ride."
        ),
        "note": "Untagged streets are unknown, not accessible. Survey critical sections in person.",
    }
