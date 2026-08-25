"""Named sights close to the planned route, for a sightseeing GPS-art layer.

Attractions come from OpenStreetMap tourism/historic tags. Each hit is matched
to its position along the route so the result reads like a programme: what you
pass and after how many kilometres. Lookups are best effort; when Overpass is
unavailable the endpoint says so instead of failing.
"""

from __future__ import annotations

import numpy as np

from . import geo, osm_data
from .route_sampling import local_xy, sample_route

CORRIDOR_M = 90.0
MAX_LANDMARKS = 14
SAMPLE_STEP_M = 15.0
MAX_SPAN_KM = 12.0


def find_landmarks(points: list[tuple[float, float]]) -> dict:
    """Return named sights within ``CORRIDOR_M`` of the routed polyline."""

    unavailable = {
        "available": False,
        "landmarks": [],
        "message": "Sightseeing data is temporarily unavailable.",
    }
    if not points or geo.path_distance_m(points) <= 0:
        return {**unavailable, "message": "A routed street polyline is needed."}
    bbox = osm_data.route_bbox(points)
    if osm_data.bbox_span_km(bbox) > MAX_SPAN_KM:
        return {
            **unavailable,
            "message": "This route covers too large an area for a reliable sightseeing lookup.",
        }
    try:
        places = osm_data.fetch_attractions(bbox)
    except osm_data.OsmUnavailable as error:
        return {**unavailable, "message": str(error)}
    if not places:
        return {
            "available": True,
            "landmarks": [],
            "message": "No tagged sights were found within a short walk of this route.",
            "corridor_m": CORRIDOR_M,
        }

    samples = sample_route(points, step_m=SAMPLE_STEP_M)
    step_m = geo.path_distance_m(points) / max(len(samples) - 1, 1)
    center_lat = sum(point[0] for point in samples) / len(samples)
    center_lon = sum(point[1] for point in samples) / len(samples)
    sample_xy = local_xy(
        np.array([point[0] for point in samples]),
        np.array([point[1] for point in samples]),
        center_lat,
        center_lon,
    )
    place_xy = local_xy(
        np.array([place["lat"] for place in places]),
        np.array([place["lon"] for place in places]),
        center_lat,
        center_lon,
    )
    distances = np.sqrt(((sample_xy[:, None, :] - place_xy[None, :, :]) ** 2).sum(axis=2))

    matches: list[dict] = []
    seen_names: set[str] = set()
    for place_index, place in enumerate(places):
        if place["name"] in seen_names:
            continue
        nearest_index = int(np.argmin(distances[:, place_index]))
        distance_m = float(distances[nearest_index, place_index])
        if distance_m > CORRIDOR_M:
            continue
        seen_names.add(place["name"])
        matches.append(
            {
                "name": place["name"],
                "kind": place["kind"],
                "latitude": place["lat"],
                "longitude": place["lon"],
                "offset_km": round(nearest_index * step_m / 1000.0, 2),
            }
        )

    matches.sort(key=lambda item: item["offset_km"])
    trimmed = matches[:MAX_LANDMARKS]
    message = (
        f"{len(trimmed)} sight(s) sit right on this route."
        if trimmed
        else "No tagged sights were found within a short walk of this route."
    )
    return {
        "available": True,
        "landmarks": trimmed,
        "count": len(trimmed),
        "corridor_m": CORRIDOR_M,
        "message": message,
    }
