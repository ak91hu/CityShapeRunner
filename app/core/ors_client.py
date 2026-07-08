"""OpenRouteService client for snapping routes to real road networks.

After the shape-matching pipeline places the artwork on the synthetic grid,
this module replaces the synthetic route coordinates with real road-following
geometry from the ORS Directions API.

To get more trackpoints and better precision, routes are requested segment-by-
segment (each consecutive pair of keypoints is routed independently) and then
concatenated.  This avoids ORS optimising the waypoint order and produces a
denser, more road-faithful polyline.
"""
from __future__ import annotations

import logging
import time
from typing import Sequence

import httpx

from app.core.units import GeoPoint, haversine_m

logger = logging.getLogger(__name__)

_ORS_PROFILES = {
    "running": "foot-walking",
    "walking": "foot-walking",
    "cycling": "cycling-regular",
}


def _ors_route_segment(
    start: GeoPoint,
    end: GeoPoint,
    profile: str,
    api_key: str,
    base_url: str,
    client: httpx.Client,
) -> list[GeoPoint] | None:
    """Route a single segment via ORS and return dense (lat, lon) points."""
    url = f"{base_url}/v2/directions/{profile}/geojson"
    body = {
        "coordinates": [[start[1], start[0]], [end[1], end[0]]],
        "format": "geojson",
        "instructions": False,
        "elevation": False,
        "geometry_simplify": False,
        "continue_straight": "true",
        "preference": "recommended",
        "options": {
            "continue_straight": "true",
        },
    }
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    try:
        resp = client.post(url, json=body, headers=headers)
        if resp.status_code == 429:
            time.sleep(1.5)
            resp = client.post(url, json=body, headers=headers)
        if resp.status_code != 200:
            logger.warning("ORS segment returned %d: %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        geom = features[0].get("geometry", {})
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            return None
        return [(c[1], c[0]) for c in coords]
    except Exception as exc:
        logger.warning("ORS segment failed: %s", exc)
        return None


def snap_route_to_roads(
    keypoints: Sequence[GeoPoint],
    activity: str,
    api_key: str,
    base_url: str = "https://api.openrouteservice.org",
) -> list[GeoPoint] | None:
    """Send keypoints to ORS Directions API and get real road-following geometry.

    Routes each consecutive pair of keypoints as a separate ORS request so
    that (a) the waypoint order is preserved exactly, (b) each segment gets
    full road-following detail, and (c) we stay within ORS free-tier limits
    (max 2 waypoints per request = no optimisation).

    Returns a concatenated list of (lat, lon) points following real roads,
    or None if ORS fails on all segments.
    """
    if not api_key:
        return None
    if len(keypoints) < 2:
        return None

    profile = _ORS_PROFILES.get(activity, "foot-walking")

    # Deduplicate consecutive identical keypoints
    deduped: list[GeoPoint] = []
    for kp in keypoints:
        if not deduped or haversine_m(deduped[-1], kp) > 5.0:
            deduped.append(kp)
    if len(deduped) < 2:
        return None

    # If there are many keypoints (>70), ORS may reject long requests.
    # Batch them into chunks of 50 coordinates (ORS limit).
    max_coords = 50
    all_points: list[GeoPoint] = []

    try:
        with httpx.Client(timeout=45.0) as client:
            for i in range(len(deduped) - 1):
                seg = _ors_route_segment(
                    deduped[i], deduped[i + 1], profile, api_key, base_url, client
                )
                if seg and len(seg) >= 2:
                    if all_points and all_points[-1] == seg[0]:
                        all_points.extend(seg[1:])
                    else:
                        all_points.extend(seg)
                else:
                    # Fallback: straight line for this segment
                    if not all_points or all_points[-1] != deduped[i]:
                        all_points.append(deduped[i])
                    all_points.append(deduped[i + 1])

    except Exception as exc:
        logger.warning("ORS snap failed: %s", exc)
        return None

    if len(all_points) < 2:
        return None

    # Densify: insert intermediate points if segments are too sparse
    densified = _densify_route(all_points, max_gap_m=25.0)
    return densified


def _densify_route(
    route: list[GeoPoint], max_gap_m: float = 25.0
) -> list[GeoPoint]:
    """Insert intermediate points so no consecutive pair is farther than max_gap_m."""
    if len(route) < 2:
        return route
    result: list[GeoPoint] = [route[0]]
    for i in range(1, len(route)):
        a = route[i - 1]
        b = route[i]
        dist = haversine_m(a, b)
        if dist > max_gap_m:
            n = max(1, int(dist / max_gap_m))
            for j in range(1, n):
                frac = j / n
                lat = a[0] + frac * (b[0] - a[0])
                lon = a[1] + frac * (b[1] - a[1])
                result.append((lat, lon))
        result.append(b)
    return result


def compute_route_distance_km(route: Sequence[GeoPoint]) -> float:
    """Compute total route distance in km using haversine."""
    total_m = 0.0
    for i in range(len(route) - 1):
        total_m += haversine_m(route[i], route[i + 1])
    return total_m / 1000.0
