"""Focused unit tests for the public FastAPI request and error contracts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gps_art_wizzard.api import routes
from gps_art_wizzard.api.routes import (
    EditedRouteRequest,
    GenerateRequest,
    RouteAcceptanceRequest,
)
from gps_art_wizzard.main import create_app


def test_generate_request_normalises_unicode_and_collapses_whitespace() -> None:
    request = GenerateRequest(prompt="  ａ heart\n\trun in   Budapest  ")

    assert request.prompt == "a heart run in Budapest"


@pytest.mark.parametrize(
    ("prompt", "message"),
    [
        ("", "enter a route idea"),
        ("   \n\t  ", "enter a route idea"),
        ("x" * 321, "320 characters or fewer"),
        ("!? ♥", "include a shape, word, letter, or number"),
        ("heart\x00run", "remove unsupported control characters"),
    ],
)
def test_generate_request_rejects_malformed_prompts(prompt: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        GenerateRequest(prompt=prompt)


def test_edited_route_request_normalises_labels_and_coordinates() -> None:
    request = EditedRouteRequest(
        control_points=[[47, 19], [47.1, 19.1]],
        reference_points=[[47.0, 19.0], [47.2, 19.2]],
        name="  Morning   route ",
        shape_name="  letter   A ",
    )

    assert request.control_points == [[47.0, 19.0], [47.1, 19.1]]
    assert request.reference_points == [[47.0, 19.0], [47.2, 19.2]]
    assert request.name == "Morning route"
    assert request.shape_name == "letter A"


@pytest.mark.parametrize(
    "point",
    [
        [91.0, 19.0],
        [-91.0, 19.0],
        [47.0, 181.0],
        [47.0, -181.0],
        [float("nan"), 19.0],
        [47.0],
    ],
)
def test_edited_route_request_rejects_invalid_coordinates(point: list[float]) -> None:
    with pytest.raises(ValidationError, match="latitude|point"):
        EditedRouteRequest(control_points=[[47.0, 19.0], point])


def test_route_acceptance_normalises_identifiers_and_legacy_flag() -> None:
    request = RouteAcceptanceRequest(
        route_id="  candidate-3  ",
        shape_name="  letter   A ",
        scientifically_verified=True,
        failed_gates=[" road_network ", "  ", "x" * 100],
    )

    assert request.route_id == "candidate-3"
    assert request.shape_name == "letter A"
    assert request.failed_gates == ["road_network", "x" * 80]
    assert request.checks_passed is True


def test_generate_endpoint_passes_a_normalised_prompt_to_the_domain(monkeypatch) -> None:
    seen: list[str] = []

    def reject_after_recording(prompt: str):
        seen.append(prompt)
        raise ValueError("unsupported test route")

    monkeypatch.setattr(routes, "generate", reject_after_recording)
    with TestClient(create_app()) as client:
        response = client.post(
            "/generate",
            headers={"X-Request-ID": "api-contract-test"},
            json={"prompt": "  a star   run  "},
        )

    assert seen == ["a star run"]
    assert response.status_code == 422
    assert response.json() == {"detail": "unsupported test route"}
    assert response.headers["X-Request-ID"] == "api-contract-test"


def test_generate_endpoint_does_not_expose_unexpected_exception_details(monkeypatch) -> None:
    def fail_generation(_prompt: str):
        raise RuntimeError("provider-secret-value")

    monkeypatch.setattr(routes, "generate", fail_generation)
    with TestClient(create_app()) as client:
        response = client.post("/generate", json={"prompt": "a circle run"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": (
            "Route generation failed. Verify the routing and model-provider configuration."
        )
    }
    assert "provider-secret-value" not in response.text


def test_edit_endpoint_rejects_a_guide_over_one_thousand_kilometres(
    monkeypatch,
) -> None:
    def should_not_route(*_args, **_kwargs):
        pytest.fail("an invalid guide must be rejected before calling the router")

    monkeypatch.setattr(routes.ors_client, "snap_route", should_not_route)
    with TestClient(create_app()) as client:
        response = client.post(
            "/edit-route",
            json={
                "control_points": [[0.0, 0.0], [0.0, 10.0]],
                "sport": "run",
                "name": "Oversized route",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Edited route guides must stay within a 1,000 km total span."
    )


@pytest.mark.parametrize("configured", [True, False])
def test_health_reports_gallery_configuration(monkeypatch, configured: bool) -> None:
    monkeypatch.setattr(routes.cloudinary_gallery, "is_configured", lambda: configured)

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "GPS Art Wizard",
        "version": "0.1.0",
        "gallery": {"configured": configured},
    }
