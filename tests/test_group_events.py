"""Group allocations respect actual route distances and retain routing evidence."""

import gpxpy
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from gps_art_wizzard.api import niche
from gps_art_wizzard.main import create_app
from gps_art_wizzard.state import RouteReadiness
from gps_art_wizzard.tools import art_rescue, geo, gpx_writer, ors_client

POINTS = [[47.0, 19.0], [47.001, 19.0], [47.001, 19.001], [47.0, 19.001], [47.0, 19.0]]


@pytest.fixture
def routed(monkeypatch):
    calls = []

    def snap(points, **kwargs):
        calls.append((points, kwargs))
        return points, geo.path_distance_m(points), True, RouteReadiness(status="ready")

    monkeypatch.setattr(ors_client, "snap_route_detailed", snap)
    return calls


def test_named_roster_allocates_shorter_sections_to_shorter_distance_limits(routed):
    with TestClient(create_app()) as client:
        response = client.post(
            "/mural-plan",
            json={
                "points": POINTS,
                "members": [
                    {"name": "Walker", "max_distance_km": 0.1},
                    {"name": "Runner", "max_distance_km": 0.3},
                ],
            },
        )
    assert response.status_code == 200
    short, long = response.json()["sections"]
    assert short["label"] == "Walker"
    assert long["art_distance_km"] == pytest.approx(short["art_distance_km"] * 3, rel=0.001)
    assert short["finish"] == long["start"]
    assert short["start"] == POINTS[0] and long["finish"] == POINTS[-1]
    assert all(item["distance_km"] <= item["max_distance_km"] for item in (short, long))
    assert response.json()["points_preview"] == POINTS
    assert len(routed) == 1


def test_legacy_equal_sections_do_not_acquire_unrequested_distance_limits(routed):
    points = [[40, 10], [50, 10], [50, 20], [40, 20], [40, 10]]
    with TestClient(create_app()) as client:
        response = client.post("/mural-plan", json={"points": points, "participants": 2})
    assert response.status_code == 200
    for section in response.json()["sections"]:
        assert section["distance_km"] > 500
        assert section["max_distance_km"] is None


def test_shared_meeting_point_routes_travel_and_keeps_it_in_each_limit(routed):
    with TestClient(create_app()) as client:
        response = client.post(
            "/mural-plan",
            json={
                "points": POINTS,
                "return_to_start": True,
                "route_preferences": {"avoid_steps": True},
                "members": [
                    {"name": "Ada", "max_distance_km": 1},
                    {"name": "Bea", "max_distance_km": 2},
                ],
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["meeting_point"] == POINTS[0]
    for section in body["sections"]:
        assert section["travel_distance_km"] > 0
        assert section["distance_km"] == pytest.approx(
            section["art_distance_km"] + section["travel_distance_km"]
        )
        assert section["distance_km"] <= section["max_distance_km"]
        tracks = gpxpy.parse(section["gpx"]).tracks[0].segments
        assert [tracks[0].points[0].latitude, tracks[0].points[0].longitude] == POINTS[0]
        assert [tracks[-1].points[-1].latitude, tracks[-1].points[-1].longitude] == POINTS[0]
        assert len(tracks) >= 2
    assert len(routed) == 3
    assert all(kwargs["route_preferences"].avoid_steps for _, kwargs in routed)


def test_travel_that_exceeds_a_limit_never_becomes_a_successful_assignment(routed):
    with TestClient(create_app()) as client:
        response = client.post(
            "/mural-plan",
            json={
                "points": POINTS,
                "return_to_start": True,
                "members": [
                    {"name": "Ada", "max_distance_km": 0.2},
                    {"name": "Bea", "max_distance_km": 0.2},
                ],
            },
        )
    assert response.status_code == 422
    assert "including meeting-point travel" in response.json()["detail"]
    assert "sections" not in response.json()


def test_insufficient_group_capacity_explains_how_to_recover(routed):
    with TestClient(create_app()) as client:
        response = client.post(
            "/mural-plan",
            json={
                "points": POINTS,
                "members": [
                    {"name": "Ada", "max_distance_km": 0.05},
                    {"name": "Bea", "max_distance_km": 0.05},
                ],
            },
        )
    assert response.status_code == 422
    assert "combined distance limits" in response.json()["detail"]
    assert len(routed) == 1


@pytest.mark.parametrize(
    "roster",
    [
        {},
        {"participants": 3, "members": [{"name": "Ada", "max_distance_km": 1}] * 2},
        {
            "members": [
                {"name": "Ada", "max_distance_km": 1},
                {"name": " ada ", "max_distance_km": 2},
            ]
        },
        {"members": [{"name": " ", "max_distance_km": 1}, {"name": "Bea", "max_distance_km": 2}]},
        {
            "members": [
                {"name": "Ada", "max_distance_km": -1},
                {"name": "Bea", "max_distance_km": 2},
            ]
        },
        {
            "members": [
                {"name": "Ada", "max_distance_km": 0.001},
                {"name": "Bea", "max_distance_km": 2},
            ]
        },
    ],
)
def test_bad_rosters_fail_before_contacting_a_provider(roster, routed):
    with TestClient(create_app()) as client:
        response = client.post("/mural-plan", json={"points": POINTS, **roster})
    assert response.status_code == 422
    assert not routed


@pytest.mark.parametrize("failure", ["unrouted", "missed_endpoint", "nearby_parallel_street"])
def test_unusable_meeting_point_connections_fail_closed(monkeypatch, failure):
    def snap(points, **_kwargs):
        if len(points) == 2:
            if failure == "unrouted":
                return points, 100.0, False, RouteReadiness()
            if failure == "nearby_parallel_street":
                shifted = [(latitude + 0.0001, longitude) for latitude, longitude in points]
                return shifted, geo.path_distance_m(shifted), True, RouteReadiness()
            return [(48.0, 20.0), (48.001, 20.0)], 100.0, True, RouteReadiness()
        return points, geo.path_distance_m(points), True, RouteReadiness()

    monkeypatch.setattr(ors_client, "snap_route_detailed", snap)
    with TestClient(create_app()) as client:
        response = client.post(
            "/mural-plan", json={"points": POINTS, "participants": 2, "return_to_start": True}
        )
    assert response.status_code == 503
    assert "sections" not in response.json()


def test_recording_coverage_cannot_be_inflated_by_the_routers_reconstruction(monkeypatch):
    monkeypatch.setattr(
        ors_client,
        "snap_route_detailed",
        lambda _points, **_kwargs: (
            [tuple(point) for point in POINTS],
            geo.path_distance_m(POINTS),
            True,
            RouteReadiness(),
        ),
    )
    recording = gpx_writer.to_gpx([tuple(point) for point in POINTS[:2]])
    with TestClient(create_app()) as client:
        response = client.post(
            "/art-rescue",
            json={
                "planned_points": POINTS,
                "recordings": [{"name": "partial.gpx", "gpx": recording}],
                "tolerance_m": 5,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["coverage"] < 0.5
    assert body["missing_segments"]
    assert body["recorded_distance_km"] == pytest.approx(geo.path_distance_m(POINTS[:2]) / 1000)
    assert body["recorded_segments_preview"] == [POINTS[:2]]
    assert "not the original recording or proof" in body["authenticity"]


def test_group_completion_accepts_24_files_but_keeps_the_bound(routed):
    recording = {
        "name": "partial.gpx",
        "gpx": gpx_writer.to_gpx([tuple(point) for point in POINTS[:2]]),
    }
    with TestClient(create_app()) as client:
        response = client.post(
            "/art-rescue", json={"planned_points": POINTS, "recordings": [recording] * 24}
        )
        rejected = client.post(
            "/art-rescue", json={"planned_points": POINTS, "recordings": [recording] * 25}
        )
    assert response.status_code == 200
    assert response.json()["recording_count"] == 24
    assert rejected.status_code == 422


@pytest.mark.parametrize("endpoint", ["/mural-plan", "/art-rescue"])
def test_cancelling_an_event_stops_before_starting_another_provider_call(
    monkeypatch, routed, endpoint
):
    checks = 0

    async def disconnected(_request):
        nonlocal checks
        checks += 1
        return checks > 1

    monkeypatch.setattr(Request, "is_disconnected", disconnected)
    if endpoint == "/mural-plan":
        payload = {"points": POINTS, "participants": 2, "return_to_start": True}
    else:
        payload = {
            "planned_points": POINTS,
            "recordings": [
                {
                    "name": "outing.gpx",
                    "gpx": gpx_writer.to_gpx([tuple(point) for point in POINTS[:2]]),
                }
            ],
        }
    with TestClient(create_app()) as client:
        response = client.post(endpoint, json=payload)
    assert response.status_code == 499
    assert len(routed) == 1


@pytest.mark.parametrize(
    "segments",
    [
        [[(47.0, 19.0), (47.001, 19.0)]] * 49,
        [[(47.0, 19.0)] * 80_001],
    ],
)
def test_aggregate_recording_limits_are_checked_before_any_provider_call(
    monkeypatch, routed, segments
):
    monkeypatch.setattr(
        niche.art_rescue, "parse_recording", lambda name, _gpx: art_rescue.Recording(name, segments)
    )
    with TestClient(create_app()) as client:
        response = client.post(
            "/art-rescue",
            json={
                "planned_points": POINTS,
                "recordings": [{"name": "too-large.gpx", "gpx": "<gpx />"}],
            },
        )
    assert response.status_code == 422
    assert not routed


@pytest.mark.parametrize("point", [(91, 19), (47, 181), (float("nan"), 19), (47, float("inf"))])
def test_invalid_recording_coordinates_are_rejected_before_routing(routed, point):
    with TestClient(create_app()) as client:
        response = client.post(
            "/art-rescue",
            json={
                "planned_points": POINTS,
                "recordings": [
                    {"name": "bad-coordinates.gpx", "gpx": gpx_writer.to_gpx([point, (47, 19)])}
                ],
            },
        )
    assert response.status_code == 422
    assert not routed


def test_oversized_groups_stop_parsing_as_soon_as_the_shared_budget_is_exceeded(
    monkeypatch, routed
):
    parsed = []

    def parse(name, _xml):
        parsed.append(name)
        return art_rescue.Recording(name, [[(47.0, 19.0)] * 40_001])

    monkeypatch.setattr(niche.art_rescue, "parse_recording", parse)
    with TestClient(create_app()) as client:
        response = client.post(
            "/art-rescue",
            json={
                "planned_points": POINTS,
                "recordings": [{"name": str(index), "gpx": "<gpx />"} for index in range(24)],
            },
        )
    assert response.status_code == 422
    assert len(parsed) == 2
    assert not routed
