"""Live route progress contract without provider or paid map calls."""

import json

from fastapi import HTTPException
from fastapi.testclient import TestClient

import gps_art_wizzard.api.routes as routes
from gps_art_wizzard.main import create_app


def test_stream_reports_real_progress_and_preview_before_final_result(monkeypatch):
    def generate_stub(_request, *, event_sink=None, preview_sink=None):
        event_sink({
            "sequence": 1, "stage": "preflight", "attempt": 1,
            "status": "completed", "elapsed_ms": 120,
            "preflight_count": 12, "routing_requests": {"snap": 1},
        })
        preview_sink({
            "points": [[47.5, 19.0], [47.501, 19.001]],
            "distance_km": 0.14, "shape_name": "heart", "status": "checking",
        })
        return {
            "prompt": "heart", "intent": None, "shape": None, "validation": None,
            "distance_km": 0.14, "snapped": True, "iterations": 0,
            "below_threshold": True, "errors": [], "history": [],
            "gpx": None, "tcx": None, "file_paths": {},
            "points_preview": [[47.5, 19.0], [47.501, 19.001]],
        }

    monkeypatch.setattr(routes, "_generate_route_sync", generate_stub)
    with TestClient(create_app()) as client:
        response = client.post(
            "/generate", json={"prompt": "heart"},
            headers={"Accept": "application/x-ndjson"},
        )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    messages = [json.loads(line) for line in response.text.splitlines()]
    assert [message["type"] for message in messages] == ["progress", "preview", "result"]
    assert messages[0]["preflight_count"] == 12
    assert messages[1]["status"] == "checking"
    assert "gpx" not in messages[1]
    assert messages[2]["data"]["gpx"] is None


def test_stream_failure_is_an_explicit_error_event_not_a_fake_success(monkeypatch):
    def fail(_request, *, event_sink=None, preview_sink=None):
        event_sink({"stage": "snap", "status": "running"})
        raise HTTPException(status_code=503, detail="No connected street route could be created.")

    monkeypatch.setattr(routes, "_generate_route_sync", fail)
    with TestClient(create_app()) as client:
        response = client.post(
            "/generate", json={"prompt": "heart"},
            headers={"Accept": "application/x-ndjson"},
        )

    assert response.status_code == 200  # headers were sent before routing failed
    messages = [json.loads(line) for line in response.text.splitlines()]
    assert [message["type"] for message in messages] == ["progress", "error"]
    assert messages[-1]["status"] == 503
    assert "result" not in response.text
