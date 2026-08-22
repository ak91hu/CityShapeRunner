"""Request-correlation logging regression tests."""

from __future__ import annotations

import json
import logging

import uvicorn
from fastapi.testclient import TestClient

import gps_art_wizzard.main as main_module
from gps_art_wizzard.api.routes import (
    RouteAcceptanceRequest,
    record_route_acceptance,
)
from gps_art_wizzard.logging_config import (
    _JsonFormatter,
    bind_request_id,
    reset_request_id,
)
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


def test_browser_clients_can_read_request_correlation_headers():
    with TestClient(create_app()) as client:
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )

    exposed = response.headers["Access-Control-Expose-Headers"].casefold()
    assert "x-request-id" in exposed
    assert "retry-after" in exposed


def test_json_log_contains_searchable_host_independent_fields(monkeypatch):
    request_token = bind_request_id("debug-session-123")
    monkeypatch.setenv("SERVICE_NAME", "gps-art-wizard")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_REVISION", "abc123")
    try:
        record = logging.LogRecord(
            name="gps_art_wizzard.test",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="candidate needs review",
            args=(),
            exc_info=None,
        )
        record.event = "candidate.review.required"
        record.score = 0.61
        record.decision = "review"
        record.verified = False
        record.failed_gates = ["landmark_similarity", "distance_fit"]
        # Handlers normally apply this context filter before formatting.
        record.request_id = "debug-session-123"

        payload = json.loads(_JsonFormatter().format(record))
    finally:
        reset_request_id(request_token)

    assert payload["severity"] == "WARNING"
    assert payload["service"] == "gps-art-wizard"
    assert payload["environment"] == "test"
    assert payload["revision"] == "abc123"
    assert payload["request_id"] == "debug-session-123"
    assert payload["event"] == "candidate.review.required"
    assert payload["score"] == 0.61
    assert payload["decision"] == "review"
    assert payload["verified"] is False
    assert payload["failed_gates"] == ["landmark_similarity", "distance_fit"]


def test_json_log_preserves_allowlisted_workflow_dimensions() -> None:
    record = logging.LogRecord(
        name="gps_art_wizzard.workflow_runtime",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Workflow finished",
        args=(),
        exc_info=None,
    )
    record.request_id = "workflow-request-7"
    record.event = "workflow.finished"
    record.workflow_run_id = "workflow-request-7"
    record.workflow_status = "completed"
    record.workflow_mode = "hybrid"
    record.workflow_duration_ms = 1250
    record.workflow_step_failures = 1
    record.workflow_llm_attempts = 3
    record.workflow_llm_fallbacks = 1

    payload = json.loads(_JsonFormatter().format(record))

    assert payload["workflow_run_id"] == "workflow-request-7"
    assert payload["workflow_status"] == "completed"
    assert payload["workflow_mode"] == "hybrid"
    assert payload["workflow_duration_ms"] == 1250
    assert payload["workflow_step_failures"] == 1
    assert payload["workflow_llm_attempts"] == 3
    assert payload["workflow_llm_fallbacks"] == 1


def test_explicit_route_acceptance_writes_a_readable_debug_event(caplog):
    with caplog.at_level(logging.WARNING, logger="gps_art_wizzard.api.routes"):
        response = record_route_acceptance(
            RouteAcceptanceRequest(
                generation_request_id="original-request-42",
                route_id="candidate-3",
                shape_name="heart",
                scientifically_verified=False,
                snapped=True,
                failed_gates=["landmark_similarity"],
                score=0.74,
                shape_fidelity=0.76,
                distance_km=8.2,
            )
        )

    assert response == {"recorded": True}
    record = caplog.records[-1]
    assert "User accepted route for GPX" in record.getMessage()
    assert record.event == "route.user.accepted"
    assert record.generation_request_id == "original-request-42"
    assert record.failed_gates == ["landmark_similarity"]


def test_server_prefers_platform_port_and_keeps_structured_logging(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(app: str, **kwargs) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setattr(uvicorn, "run", fake_run)

    main_module.run()

    assert captured["app"] == "gps_art_wizzard.main:app"
    assert captured["port"] == 8080
    assert captured["log_config"] is None
    assert captured["access_log"] is False


def test_edit_route_endpoint_blocks_unsafe_gpx_without_ors():
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
    assert response.status_code == 503
    assert response.headers["X-Request-ID"] == "manual-edit-test"
    assert payload == {
        "detail": (
            "The edited route could not be matched to connected streets, so no "
            "GPS file was created. Adjust the control points or retry when the "
            "routing service is available."
        )
    }
