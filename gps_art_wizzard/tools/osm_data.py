"""Best-effort OpenStreetMap street context through a public Overpass mirror.

The module powers the night-readiness and route-landmark layers. Every lookup
is cached in-process by rounded bounding box and degrades to ``OsmUnavailable``
instead of failing a request: these layers are planning evidence, never a hard
dependency. The offline flag used by the geocoder also short-circuits network
access here so tests and air-gapped runs stay deterministic.
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from collections import OrderedDict

import httpx

from .geo import haversine

logger = logging.getLogger(__name__)

_OVERPASS_URL = os.getenv("OVERPASS_BASE_URL", "https://overpass-api.de/api/interpreter")
# The public mirror's Apache rejects default library user agents with 406.
_USER_AGENT = os.getenv("OVERPASS_USER_AGENT", "GPSArtWizard/1.0")
_HEADERS = {"User-Agent": _USER_AGENT}
_TIMEOUT = httpx.Timeout(connect=4.0, read=12.0, write=4.0, pool=4.0)
_CACHE_MAX = 32
_CACHE_TTL_S = 600.0

_cache: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()
_cache_lock = threading.Lock()


class OsmUnavailable(RuntimeError):
    """Raised when OpenStreetMap context cannot be retrieved right now."""


def offline_mode() -> bool:
    """Share the geocoder's offline switch so tests never touch the network."""

    return bool(os.getenv("GEOCODE_OFFLINE"))


def route_bbox(
    points: list[tuple[float, float]],
    *,
    pad_m: float = 120.0,
) -> tuple[float, float, float, float]:
    """Return ``(south, west, north, east)`` padded around the route."""

    latitudes = [point[0] for point in points]
    longitudes = [point[1] for point in points]
    middle_lat = sum(latitudes) / len(latitudes)
    lat_pad = pad_m / 111_320.0
    lon_pad = pad_m / max(1.0, 111_320.0 * math.cos(math.radians(middle_lat)))
    south = min(latitudes) - lat_pad
    west = min(longitudes) - lon_pad
    north = max(latitudes) + lat_pad
    east = max(longitudes) + lon_pad
    return (south, west, north, east)


def bbox_span_km(bbox: tuple[float, float, float, float]) -> float:
    """Diagonal length of a ``(south, west, north, east)`` box in kilometres."""

    south, west, north, east = bbox
    return haversine(south, west, north, east) / 1000.0


def _cache_get(key: str) -> list[dict] | None:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        stored_at, elements = entry
        if now - stored_at > _CACHE_TTL_S:
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        return elements


def _cache_put(key: str, elements: list[dict]) -> None:
    now = time.monotonic()
    with _cache_lock:
        _cache[key] = (now, elements)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


def clear_osm_cache() -> None:
    with _cache_lock:
        _cache.clear()


def overpass_query(query: str, *, cache_key: str | None = None) -> list[dict]:
    """Run one Overpass QL query and return its raw elements."""

    if cache_key:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
    if offline_mode():
        raise OsmUnavailable("OpenStreetMap context is disabled in offline mode.")
    try:
        response = httpx.post(
            _OVERPASS_URL,
            data={"data": query},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.info("Overpass lookup failed: %s", error)
        raise OsmUnavailable(
            "The OpenStreetMap context service is temporarily unavailable."
        ) from error
    elements = payload.get("elements") if isinstance(payload, dict) else None
    if not isinstance(elements, list):
        raise OsmUnavailable("The OpenStreetMap context service returned an unexpected answer.")
    if cache_key:
        _cache_put(cache_key, elements)
    return elements


def _bbox_clause(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    return f"({south:.5f},{west:.5f},{north:.5f},{east:.5f})"


def fetch_lit_highways(bbox: tuple[float, float, float, float]) -> list[dict]:
    """Highways with an explicit ``lit`` tag inside the box.

    Each entry keeps ``highway``, normalised ``lit`` and a ``points`` polyline
    taken from the Overpass ``geom`` output so no node resolution is needed.
    """

    clause = _bbox_clause(bbox)
    query = f'[out:json][timeout:25];way["highway"]["lit"]{clause};out tags geom;'
    cache_key = "lit:" + ":".join(f"{value:.4f}" for value in bbox)
    elements = overpass_query(query, cache_key=cache_key)
    ways: list[dict] = []
    for element in elements[:4_000]:
        tags = element.get("tags") or {}
        highway = tags.get("highway")
        geometry = element.get("geometry") or []
        points = [
            (float(node["lat"]), float(node["lon"]))
            for node in geometry
            if isinstance(node, dict)
            and isinstance(node.get("lat"), (int, float))
            and isinstance(node.get("lon"), (int, float))
        ]
        if not highway or len(points) < 2:
            continue
        ways.append(
            {
                "highway": str(highway),
                "lit": str(tags.get("lit", "")).strip().lower(),
                "points": points,
            }
        )
    return ways


def fetch_attractions(bbox: tuple[float, float, float, float]) -> list[dict]:
    """Named tourist, historic, and green attractions inside the box."""

    clause = _bbox_clause(bbox)
    query = (
        "[out:json][timeout:25];"
        "("
        f'node["tourism"~"^(attraction|artwork|museum|viewpoint|gallery)$"]{clause};'
        f'way["tourism"~"^(attraction|artwork|museum|viewpoint|gallery)$"]{clause};'
        f'node["historic"~"^(monument|memorial|castle|ruins|tower|city_gate)$"]{clause};'
        f'way["historic"~"^(monument|memorial|castle|ruins|tower|city_gate)$"]{clause};'
        ");"
        "out tags center;"
    )
    cache_key = "attractions:" + ":".join(f"{value:.4f}" for value in bbox)
    elements = overpass_query(query, cache_key=cache_key)
    places: list[dict] = []
    for element in elements[:2_000]:
        tags = element.get("tags") or {}
        name = str(tags.get("name", "")).strip()
        kind_tag = tags.get("tourism") or tags.get("historic")
        if not name or not kind_tag:
            continue
        position = element.get("center") or element
        lat = position.get("lat")
        lon = position.get("lon") or position.get("lng")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        places.append(
            {
                "name": name,
                "kind": str(kind_tag),
                "lat": float(lat),
                "lon": float(lon),
            }
        )
    return places


_UNPAVED_SURFACES = {
    "unpaved",
    "compacted",
    "gravel",
    "fine_gravel",
    "ground",
    "dirt",
    "earth",
    "grass",
    "sand",
    "mud",
    "woodchips",
}


def _accessibility_class(tags: dict) -> str:
    """Coarse wheelchair-relevant classification of one highway way."""

    if tags.get("highway") == "steps":
        return "steps"
    wheelchair = str(tags.get("wheelchair", "")).strip().lower()
    if wheelchair in {"no", "limited", "yes"}:
        return f"wheelchair_{wheelchair}"
    surface = str(tags.get("surface", "")).strip().lower()
    if surface in _UNPAVED_SURFACES:
        return "unpaved"
    if surface:
        return "paved"
    return "untagged"


def fetch_accessibility_ways(bbox: tuple[float, float, float, float]) -> list[dict]:
    """Highways with wheelchair, surface, or steps evidence inside the box."""

    clause = _bbox_clause(bbox)
    query = (
        "[out:json][timeout:25];"
        "("
        f'way["highway"]["wheelchair"]{clause};'
        f'way["highway"]["surface"]{clause};'
        f'way["highway"="steps"]{clause};'
        ");"
        "out tags geom;"
    )
    cache_key = "accessibility:" + ":".join(f"{value:.4f}" for value in bbox)
    elements = overpass_query(query, cache_key=cache_key)
    ways: list[dict] = []
    seen_ids: set[str] = set()
    for element in elements[:4_000]:
        element_id = str(element.get("type", "way")) + str(element.get("id", ""))
        if element_id in seen_ids:
            continue
        tags = element.get("tags") or {}
        if not tags.get("highway"):
            continue
        geometry = element.get("geometry") or []
        points = [
            (float(node["lat"]), float(node["lon"]))
            for node in geometry
            if isinstance(node, dict)
            and isinstance(node.get("lat"), (int, float))
            and isinstance(node.get("lon"), (int, float))
        ]
        if len(points) < 2:
            continue
        seen_ids.add(element_id)
        ways.append(
            {
                "highway": str(tags["highway"]),
                "class": _accessibility_class(tags),
                "points": points,
            }
        )
    return ways
