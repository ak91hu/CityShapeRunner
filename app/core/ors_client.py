from __future__ import annotations

import logging
import time
from typing import Sequence
import httpx

from app.core.units import GeoPoint, haversine_m
from app.core.mapbox_client import _adaptive_reduce, compute_route_distance_km

logger = logging.getLogger(__name__)

_ORS_PROFILES = {
    "running": "foot-walking",
    "walking": "foot-walking",
    "cycling": "cycling-regular",
    "driving": "driving-car",
}

# Reuse a single client to avoid the cost of recreating SSL contexts on every call.
_ORS_CLIENT: httpx.Client | None = None


def _get_ors_client(timeout: float = 45.0) -> httpx.Client:
    global _ORS_CLIENT
    if _ORS_CLIENT is None:
        _ORS_CLIENT = httpx.Client(timeout=timeout)
    return _ORS_CLIENT


def snap_route_to_roads(
    keypoints: Sequence[GeoPoint],
    activity: str,
    api_key: str,
    base_url: str = "https://api.openrouteservice.org/v2/directions",
) -> list[GeoPoint] | None:
    if not api_key:
        return None
    if len(keypoints) < 2:
        return None

    profile = _ORS_PROFILES.get(activity, "foot-walking")

    deduped: list[GeoPoint] = []
    for kp in keypoints:
        if not deduped or haversine_m(deduped[-1], kp) > 5.0:
            deduped.append(kp)
    if len(deduped) < 2:
        return None

    # ORS limit is often 50 for free, but let's stick to 25 or 50
    reduced = _adaptive_reduce(deduped, 40)

    # ORS uses [lon, lat] for coordinates
    coords = [[c[1], c[0]] for c in reduced]
    url = f"{base_url}/{profile}/geojson"

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8"
    }

    payload = {
        "coordinates": coords,
        "geometry": "true",
        "instructions": "false"
    }

    try:
        client = _get_ors_client()
        resp = client.post(url, headers=headers, json=payload)
        if resp.status_code == 429:
            time.sleep(1.5)
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.warning("ORS API returned %d: %s", resp.status_code, resp.text[:200])
            return None

        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None

        geom = features[0].get("geometry", {})
        coords_out = geom.get("coordinates", [])

        if not coords_out or len(coords_out) < 2:
            return None

        return [(lat, lon) for lon, lat in coords_out]

    except Exception as exc:
        logger.warning("ORS snap failed: %s", exc)
        return None
