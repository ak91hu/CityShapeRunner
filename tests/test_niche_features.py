"""Contracts for the GPS Art Intelligence product layer."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from gps_art_wizzard.api import niche
from gps_art_wizzard.main import create_app
from gps_art_wizzard.state import RouteReadiness
from gps_art_wizzard.tools import ors_client

POINTS = [[47.0, 19.0], [47.001, 19.0], [47.001, 19.001], [47.0, 19.001], [47.0, 19.0]]


def test_mural_plan_splits_one_route_into_balanced_gpx_sections():
    with TestClient(create_app()) as client:
        response = client.post("/mural-plan", json={"points": POINTS, "participants": 2, "name": "Team heart"})
    assert response.status_code == 200
    sections = response.json()["sections"]
    assert len(sections) == 2
    assert all("<gpx" in section["gpx"] for section in sections)
    assert abs(sections[0]["distance_km"] - sections[1]["distance_km"]) < 0.02


def test_timed_readiness_exposes_daylight_and_resilient_weather(monkeypatch):
    monkeypatch.setattr(niche, "time_readiness", lambda *_: {"daylight": "daylight", "weather": None})
    with TestClient(create_app()) as client:
        response = client.post("/timed-readiness", json={"latitude": 47.5, "longitude": 19.0, "departure_at": datetime.now(UTC).isoformat()})
    assert response.status_code == 200
    assert response.json()["daylight"] == "daylight"


def test_recognition_repair_keeps_salient_anchor_route_exportable(monkeypatch):
    def fake_snap(points, **_):
        return points, 500.0, True, RouteReadiness(status="ready", data_quality="good")
    monkeypatch.setattr(ors_client, "snap_route_detailed", fake_snap)
    with TestClient(create_app()) as client:
        response = client.post("/recognition-repair", json={"reference_points": POINTS, "sport": "run", "closed": True})
    assert response.status_code == 200
    body = response.json()
    assert body["snapped"] is True
    assert body["recognition_score"] >= 0
    assert "<gpx" in body["gpx"]
