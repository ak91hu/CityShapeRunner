"""Request-correlation logging regression tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gps_art_wizzard.main import create_app


def test_http_requests_echo_a_safe_request_id():
    with TestClient(create_app()) as client:
        response = client.get(
            "/health",
            headers={"X-Request-ID": "debug-session-123"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "debug-session-123"


def test_unsafe_request_id_is_replaced():
    with TestClient(create_app()) as client:
        response = client.get(
            "/health",
            headers={"X-Request-ID": "not safe / header"},
        )

    request_id = response.headers["X-Request-ID"]
    assert request_id != "not safe / header"
    assert len(request_id) == 32


def test_edit_route_endpoint_returns_correlated_manual_gpx_without_ors():
    with TestClient(create_app()) as client:
        response = client.post(
            "/edit-route",
            headers={"X-Request-ID": "manual-edit-test"},
            json={
                "control_points": [
                    [47.5, 19.0],
                    [47.501, 19.001],
                ],
                "reference_points": [
                    [47.5, 19.0],
                    [47.501, 19.001],
                ],
                "sport": "run",
                "closed": False,
                "target_distance_km": 1.0,
                "name": "Manual edit",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "manual-edit-test"
    assert payload["request_id"] == "manual-edit-test"
    assert payload["snapped"] is False
    assert payload["below_recommended"] is True
    assert "<gpx" in payload["gpx"]
