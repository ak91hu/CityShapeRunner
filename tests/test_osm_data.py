"""Overpass transport and fallback behaviour for the optional OSM layers."""

from __future__ import annotations

import httpx
import pytest

from gps_art_wizzard.tools import osm_data


def test_overpass_get_falls_back_and_caches_success(monkeypatch) -> None:
    osm_data.clear_osm_cache()
    monkeypatch.delenv("GEOCODE_OFFLINE", raising=False)
    monkeypatch.setattr(osm_data, "_OVERPASS_URL", "https://primary.example/api/interpreter")
    monkeypatch.setattr(
        osm_data, "_OVERPASS_FALLBACK_URL", "https://backup.example/api/interpreter"
    )
    calls: list[tuple[str, str]] = []

    def get(url: str, *, params: dict, headers: dict, timeout: httpx.Timeout):
        assert headers["User-Agent"]
        assert timeout is osm_data._TIMEOUT  # noqa: SLF001
        calls.append((url, params["data"]))
        request = httpx.Request("GET", url, params=params)
        if "primary" in url:
            return httpx.Response(504, request=request)
        return httpx.Response(200, json={"elements": [{"id": 42}]}, request=request)

    monkeypatch.setattr(osm_data.httpx, "get", get)

    assert osm_data.overpass_query("out;", cache_key="fallback-test") == [{"id": 42}]
    assert osm_data.overpass_query("out;", cache_key="fallback-test") == [{"id": 42}]
    assert calls == [
        ("https://primary.example/api/interpreter", "out;"),
        ("https://backup.example/api/interpreter", "out;"),
    ]


def test_overpass_all_failures_remain_unavailable_and_uncached(monkeypatch) -> None:
    osm_data.clear_osm_cache()
    monkeypatch.delenv("GEOCODE_OFFLINE", raising=False)
    monkeypatch.setattr(osm_data, "_OVERPASS_URL", "https://primary.example/api/interpreter")
    monkeypatch.setattr(
        osm_data, "_OVERPASS_FALLBACK_URL", "https://backup.example/api/interpreter"
    )
    calls: list[str] = []

    def get(url: str, **_kwargs):
        calls.append(url)
        return httpx.Response(504, request=httpx.Request("GET", url))

    monkeypatch.setattr(osm_data.httpx, "get", get)

    for _ in range(2):
        with pytest.raises(osm_data.OsmUnavailable, match="temporarily unavailable"):
            osm_data.overpass_query("out;", cache_key="failure-test")
    assert len(calls) == 4


def test_accessibility_uses_bbox_highways_and_filters_locally(monkeypatch) -> None:
    queries: list[str] = []
    geometry = [{"lat": 47.5, "lon": 19.04}, {"lat": 47.501, "lon": 19.041}]

    def query(statement: str, *, cache_key: str) -> list[dict]:
        assert cache_key.startswith("accessibility:")
        queries.append(statement)
        return [
            {"id": 1, "tags": {"highway": "residential"}, "geometry": geometry},
            {
                "id": 2,
                "tags": {"highway": "footway", "surface": "asphalt"},
                "geometry": geometry,
            },
            {"id": 3, "tags": {"highway": "steps"}, "geometry": geometry},
        ]

    monkeypatch.setattr(osm_data, "overpass_query", query)
    ways = osm_data.fetch_accessibility_ways((47.49, 19.03, 47.51, 19.05))

    assert len(queries) == 1
    assert 'way["highway"](' in queries[0]
    assert '["wheelchair"]' not in queries[0]
    assert [way["class"] for way in ways] == ["paved", "steps"]
