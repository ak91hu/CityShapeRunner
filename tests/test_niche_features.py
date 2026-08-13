"""Contracts for the GPS Art Intelligence product layer."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from gps_art_wizzard.api import niche
from gps_art_wizzard.main import create_app
from gps_art_wizzard.state import RouteReadiness
from gps_art_wizzard.tools import gpx_writer, ors_client

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


def test_inkproof_forecast_reports_drift_resilience_and_mappable_details():
    with TestClient(create_app()) as client:
        response = client.post(
            "/inkproof-analysis",
            json={"points": POINTS, "accuracy_m": 10},
        )
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["resilience_score"] <= 1
    assert 0 <= body["expected_recognition"] <= 1
    assert body["rating"] in {"durable", "watch", "fragile"}
    assert isinstance(body["fragile_segments"], list)
    assert "deterministic" in body["method"]


def test_art_rescue_preserves_pen_up_gaps_and_exports_only_missing_ink():
    first = [(47.0, 19.0), (47.001, 19.0), (47.001, 19.001)]
    second = [(47.0, 19.001), (47.0, 19.0)]
    recordings = [
        {"name": "day-one.gpx", "gpx": gpx_writer.to_gpx(first)},
        {"name": "day-two.gpx", "gpx": gpx_writer.to_gpx(second)},
    ]
    with TestClient(create_app()) as client:
        response = client.post(
            "/art-rescue",
            json={
                "planned_points": POINTS,
                "recordings": recordings,
                "tolerance_m": 15,
                "name": "Two-day square",
                "sport": "run",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["recording_count"] == 2
    assert body["track_segment_count"] == 2
    assert 0.6 < body["coverage"] < 1
    assert body["missing_segments"]
    assert body["missing_ink_gpx"].count("<trkseg>") == 1
    assert body["merged_recording_gpx"].count("<trkseg>") == 2
    assert "recorded points only" in body["authenticity"]
    assert "not stored" in body["privacy"]
