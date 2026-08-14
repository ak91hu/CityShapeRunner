"""Focused unit tests for the public FastAPI request and error contracts."""

from __future__ import annotations

from types import SimpleNamespace

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


def test_generate_request_accepts_a_public_image_reference_url() -> None:
    request = GenerateRequest(
        prompt="a custom image in Budapest",
        reference_image_url="  https://example.com/drawing.svg  ",
    )

    assert request.reference_image_url == "https://example.com/drawing.svg"


def test_generate_request_rejects_a_non_http_image_reference() -> None:
    with pytest.raises(ValidationError, match="public HTTP or HTTPS"):
        GenerateRequest(
            prompt="a custom image in Budapest",
            reference_image_url="file:///etc/example.svg",
        )


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


def test_interpret_endpoint_exposes_the_bug_as_an_insect_template() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/interpret",
            json={"prompt": "a bug run in Tatabánya, about 8 km"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["drawing_label"] == "bug"
    assert payload["drawing_kind"] == "template"
    assert payload["defaults_applied"] == []
    assert payload["confidence"] == {
        "drawing": 0.98,
        "city": 0.98,
        "sport": 0.98,
        "distance": 0.99,
    }
    assert payload["needs_clarification"] is False
    assert payload["clarifications"] == []
    assert payload["intent"] == {
        "shape": "bug",
        "text": None,
        "city": "Tatabánya",
        "sport": "run",
        "distance_km": 8.0,
        "style": None,
        "suggest": False,
    }


def test_interpret_endpoint_makes_route_defaults_visible() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/interpret", json={"prompt": "draw a bug"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"]["city"] == "Budapest"
    assert payload["intent"]["distance_km"] == 8.0
    assert payload["defaults_applied"] == ["city", "distance"]
    assert payload["confidence"]["city"] == 0.38
    assert payload["confidence"]["distance"] == 0.55


def test_generate_endpoint_forwards_confirmed_intent_start_and_preferences(
    monkeypatch,
) -> None:
    captured = {}

    def reject_after_recording(prompt: str, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        raise ValueError("captured advanced request")

    monkeypatch.setattr(routes, "generate", reject_after_recording)
    with TestClient(create_app()) as client:
        response = client.post(
            "/generate",
            json={
                "prompt": "a bug run in Tatabánya, about 8 km",
                "intent_override": {
                    "shape": "bug",
                    "city": "Tatabánya",
                    "sport": "run",
                    "distance_km": 8,
                },
                "start_point": {
                    "latitude": 47.5853,
                    "longitude": 18.4041,
                    "label": "Station",
                },
                "start_direction_deg": 90,
                "route_preferences": {
                    "avoid_steps": True,
                    "prefer_quiet": True,
                },
            },
        )

    assert response.status_code == 422
    assert captured["prompt"] == "a bug run in Tatabánya, about 8 km"
    assert captured["intent_override"].shape == "bug"
    assert captured["start_point"] == (47.5853, 18.4041)
    assert captured["start_label"] == "Station"
    assert captured["start_direction_deg"] == 90
    assert captured["route_preferences"].avoid_steps is True
    assert captured["route_preferences"].prefer_quiet is True


def test_generate_endpoint_imports_and_forwards_svg_geometry(monkeypatch) -> None:
    captured = {}
    reference = routes.image_reference.ImportedImageReference(
        name="mug",
        kind="svg",
        shape=routes.Shape(
            name="mug",
            paths=[[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.0)]],
            closed=True,
            source="reference_svg",
        ),
        image_data_url="data:image/png;base64,iVBORw0KGgo=",
    )

    monkeypatch.setattr(
        routes.image_reference,
        "import_image_reference",
        lambda url: reference if url.endswith("mug.svg") else None,
    )

    def reject_after_recording(prompt: str, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        raise ValueError("captured image reference")

    monkeypatch.setattr(routes, "generate", reject_after_recording)
    with TestClient(create_app()) as client:
        response = client.post(
            "/generate",
            json={
                "prompt": "a custom image in Budapest, running, about 10 km",
                "reference_image_url": "https://example.com/mug.svg",
            },
        )

    assert response.status_code == 422
    assert captured["reference_shape"].name == "mug"
    assert captured["reference_image_data_url"].startswith("data:image/png;base64,")
    assert captured["reference_name"] == "mug"
    assert captured["reference_kind"] == "svg"


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


def test_generate_endpoint_blocks_an_unrouted_straight_line(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "generate",
        lambda _prompt: SimpleNamespace(
            snapped=SimpleNamespace(snapped=False),
            shape=SimpleNamespace(name="heart"),
            intent=SimpleNamespace(city="Budapest"),
            candidate_count=1,
            preflight_count=0,
        ),
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/generate",
            json={"prompt": "a heart run in Budapest, about 8 km"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "No connected street route could be created, so the planner did not "
            "return an unsafe straight-line GPS track. Try another city, shape, "
            "or distance, or retry when the routing service is available."
        )
    }


@pytest.mark.parametrize(
    "snapped_route",
    [
        SimpleNamespace(snapped=True, points=[], total_distance_m=8_000.0),
        SimpleNamespace(
            snapped=True,
            points=[(47.5, 19.0)],
            total_distance_m=8_000.0,
        ),
        SimpleNamespace(
            snapped=True,
            points=[(47.5, 19.0), (47.501, 19.001)],
            total_distance_m=0.0,
        ),
        SimpleNamespace(
            snapped=True,
            points=[(95.0, 19.0), (47.501, 19.001)],
            total_distance_m=8_000.0,
        ),
    ],
)
def test_generate_endpoint_rejects_a_malformed_claimed_street_route(
    monkeypatch,
    snapped_route,
) -> None:
    monkeypatch.setattr(
        routes,
        "generate",
        lambda _prompt: SimpleNamespace(
            snapped=snapped_route,
            shape=SimpleNamespace(name="heart"),
            intent=SimpleNamespace(city="Budapest"),
            candidate_count=1,
            preflight_count=1,
        ),
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/generate",
            json={"prompt": "a heart run in Budapest, about 8 km"},
        )

    assert response.status_code == 503
    assert "unsafe straight-line GPS track" in response.json()["detail"]


def test_generate_endpoint_hides_response_serialisation_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "generate",
        lambda _prompt: SimpleNamespace(
            snapped=SimpleNamespace(
                snapped=True,
                points=[(47.5, 19.0), (47.501, 19.001)],
                total_distance_m=8_000.0,
            ),
        ),
    )

    def fail_response(_state):
        raise RuntimeError("response-secret-value")

    monkeypatch.setattr(routes, "_state_to_response", fail_response)
    with TestClient(create_app()) as client:
        response = client.post(
            "/generate",
            json={"prompt": "a heart run in Budapest, about 8 km"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "The street route was created, but its response could not be prepared."
    }
    assert "response-secret-value" not in response.text


def test_route_acceptance_rejects_a_non_street_route(caplog) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/route-acceptance",
            json={
                "generation_request_id": "request-unsafe",
                "route_id": "candidate-unsafe",
                "shape_name": "heart",
                "snapped": False,
                "failed_gates": ["road_network"],
            },
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Only a route matched to connected streets can be approved for "
            "GPS export. Generate or edit the route again first."
        )
    }
    rejection = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "route.user.acceptance.rejected"
    )
    assert rejection.candidate_id == "candidate-unsafe"
    assert rejection.reason == "not_street_routed"
    assert not any(
        getattr(record, "event", None) == "route.user.accepted"
        for record in caplog.records
    )


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


@pytest.mark.parametrize(
    ("points", "distance_m", "snapped"),
    [
        ([], 100.0, True),
        ([(47.5, 19.0)], 100.0, True),
        ([(47.5, 19.0), (47.501, 19.001)], 0.0, True),
        ([(47.5, 19.0), (47.501, 19.001)], float("nan"), True),
        ([(47.5, 19.0), (47.501, 181.0)], 100.0, True),
        ([(47.5, 19.0), (47.501, 19.001)], 100.0, False),
    ],
)
def test_edit_endpoint_blocks_malformed_or_unrouted_router_output_before_export(
    monkeypatch,
    points,
    distance_m,
    snapped,
) -> None:
    monkeypatch.setattr(
        routes.ors_client,
        "snap_route_detailed",
        lambda *_args, **_kwargs: (
            points,
            distance_m,
            snapped,
            SimpleNamespace(),
        ),
    )

    def must_not_continue(*_args, **_kwargs):
        pytest.fail("invalid router output must be blocked before validation/export")

    monkeypatch.setattr(routes.ValidationAgent, "run", must_not_continue)
    monkeypatch.setattr(routes.gpx_writer, "to_gpx", must_not_continue)
    with TestClient(create_app()) as client:
        response = client.post(
            "/edit-route",
            json={
                "control_points": [[47.5, 19.0], [47.501, 19.001]],
                "sport": "run",
                "name": "Edited route",
            },
        )

    assert response.status_code == 503
    assert "no GPS file was created" in response.json()["detail"]


def test_edit_endpoint_maps_an_unexpected_router_error_to_a_safe_503(
    monkeypatch,
) -> None:
    def fail_router(*_args, **_kwargs):
        raise RuntimeError("router-secret-value")

    monkeypatch.setattr(routes.ors_client, "snap_route_detailed", fail_router)
    with TestClient(create_app()) as client:
        response = client.post(
            "/edit-route",
            json={
                "control_points": [[47.5, 19.0], [47.501, 19.001]],
                "sport": "run",
                "name": "Edited route",
            },
        )

    assert response.status_code == 503
    assert "no GPS file was created" in response.json()["detail"]
    assert "router-secret-value" not in response.text


def test_edit_endpoint_hides_unexpected_validation_errors(monkeypatch) -> None:
    routed = [(47.5, 19.0), (47.5005, 19.0005), (47.501, 19.001)]
    monkeypatch.setattr(
        routes.ors_client,
        "snap_route_detailed",
        lambda *_args, **_kwargs: (routed, 200.0, True, SimpleNamespace()),
    )

    def fail_validation(*_args, **_kwargs):
        raise RuntimeError("validation-secret-value")

    monkeypatch.setattr(routes.ValidationAgent, "run", fail_validation)
    with TestClient(create_app()) as client:
        response = client.post(
            "/edit-route",
            json={
                "control_points": routed,
                "sport": "run",
                "name": "Edited route",
            },
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Edited route validation failed."}
    assert "validation-secret-value" not in response.text


def test_edit_endpoint_hides_unexpected_gpx_export_errors(monkeypatch) -> None:
    routed = [(47.5, 19.0), (47.5005, 19.0005), (47.501, 19.001)]
    monkeypatch.setattr(
        routes.ors_client,
        "snap_route_detailed",
        lambda *_args, **_kwargs: (routed, 200.0, True, SimpleNamespace()),
    )

    def fail_gpx(*_args, **_kwargs):
        raise RuntimeError("gpx-secret-value")

    monkeypatch.setattr(routes.gpx_writer, "to_gpx", fail_gpx)
    with TestClient(create_app()) as client:
        response = client.post(
            "/edit-route",
            json={
                "control_points": routed,
                "sport": "run",
                "name": "Edited route",
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": (
            "The edited street route was created, but its GPS file could not be prepared."
        )
    }
    assert "gpx-secret-value" not in response.text


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
