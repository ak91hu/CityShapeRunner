"""Contracts for the GPS Art Intelligence product layer."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from gps_art_wizzard.api import niche
from gps_art_wizzard.main import create_app
from gps_art_wizzard.state import RouteReadiness
from gps_art_wizzard.tools import gpx_writer, ors_client, timed_readiness

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


class _ForecastResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_timed_readiness_matches_the_exact_selected_hour(monkeypatch):
    requested_params = []
    hourly = {
        "time": ["2026-08-13T12:00", "2026-08-13T13:00", "2026-08-14T12:00"],
        "temperature_2m": [19.0, 23.0, 31.0],
        "precipitation": [0.0, 1.4, 4.2],
        "weather_code": [1, 61, 80],
        "wind_speed_10m": [5.0, 11.0, 22.0],
    }

    def fake_get(_url, *, params, timeout):
        requested_params.append((params, timeout))
        return _ForecastResponse({"hourly": hourly})

    monkeypatch.setattr(timed_readiness.httpx, "get", fake_get)
    current = datetime(2026, 8, 13, 9, tzinfo=UTC)
    first = timed_readiness.time_readiness(
        47.5, 19.0, datetime(2026, 8, 13, 13, 45, tzinfo=UTC), now=current
    )
    second = timed_readiness.time_readiness(
        47.5, 19.0, datetime(2026, 8, 14, 12, 15, tzinfo=UTC), now=current
    )

    assert first["weather"]["forecast_at"] == "2026-08-13T13:00:00+00:00"
    assert first["weather"]["temperature_c"] == 23.0
    assert second["weather"]["temperature_c"] == 31.0
    assert first["weather"] != second["weather"]
    assert requested_params[0][0]["forecast_days"] == 16


def test_timed_readiness_never_substitutes_a_nearby_hour(monkeypatch):
    hourly = {
        "time": ["2026-08-13T12:00", "2026-08-13T14:00"],
        "temperature_2m": [19.0, 25.0],
    }
    monkeypatch.setattr(
        timed_readiness.httpx,
        "get",
        lambda *_args, **_kwargs: _ForecastResponse({"hourly": hourly}),
    )

    result = timed_readiness.time_readiness(
        47.5,
        19.0,
        datetime(2026, 8, 13, 13, 30, tzinfo=UTC),
        now=datetime(2026, 8, 13, 9, tzinfo=UTC),
    )

    assert result["weather"] is None
    assert result["weather_status"] == "unavailable"
    assert "No hourly forecast" in result["weather_message"]


def test_timed_readiness_explains_dates_outside_the_forecast_window(monkeypatch):
    def unexpected_get(*_args, **_kwargs):
        raise AssertionError("Weather API must not be called outside its supported window")

    monkeypatch.setattr(timed_readiness.httpx, "get", unexpected_get)
    result = timed_readiness.time_readiness(
        47.5,
        19.0,
        datetime(2026, 9, 4, 13, tzinfo=UTC),
        now=datetime(2026, 8, 13, 9, tzinfo=UTC),
    )

    assert result["weather"] is None
    assert result["weather_status"] == "outside_forecast_window"
    assert "16 days ahead" in result["weather_message"]


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
