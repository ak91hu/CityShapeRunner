"""Contracts for the GPS Art Intelligence product layer."""

from __future__ import annotations

from datetime import UTC, date, datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient

from gps_art_wizzard.api import gallery as gallery_api
from gps_art_wizzard.api import niche
from gps_art_wizzard.main import create_app
from gps_art_wizzard.state import RouteReadiness
from gps_art_wizzard.tools import (
    art_rescue,
    destination_catalog,
    gpx_writer,
    lesson_pack,
    occasions,
    ors_client,
    osm_data,
    route_sampling,
    timed_readiness,
)

POINTS = [[47.0, 19.0], [47.001, 19.0], [47.001, 19.001], [47.0, 19.001], [47.0, 19.0]]


def test_mural_plan_splits_one_route_into_balanced_gpx_sections():
    with TestClient(create_app()) as client:
        response = client.post(
            "/mural-plan", json={"points": POINTS, "participants": 2, "name": "Team heart"}
        )
    assert response.status_code == 200
    sections = response.json()["sections"]
    assert len(sections) == 2
    assert all("<gpx" in section["gpx"] for section in sections)
    assert abs(sections[0]["distance_km"] - sections[1]["distance_km"]) < 0.02


def test_timed_readiness_exposes_daylight_and_resilient_weather(monkeypatch):
    monkeypatch.setattr(
        niche, "time_readiness", lambda *_: {"daylight": "daylight", "weather": None}
    )
    with TestClient(create_app()) as client:
        response = client.post(
            "/timed-readiness",
            json={
                "latitude": 47.5,
                "longitude": 19.0,
                "departure_at": datetime.now(UTC).isoformat(),
            },
        )
    assert response.status_code == 200
    assert response.json()["daylight"] == "daylight"


# ---- real solar-position math ------------------------------------------------ #
# The network is never reachable here: both early-return branches (past /
# outside forecast window) still compute daylight, so these fixed far-future
# dates keep the assertions valid regardless of when the suite runs.
def _readiness_without_network(latitude: float, longitude: float, when: datetime) -> dict:
    return timed_readiness.time_readiness(
        latitude,
        longitude,
        when,
        now=datetime(2026, 8, 13, 9, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("latitude", "longitude", "when", "expected"),
    [
        # Budapest, midsummer solar noon -> high sun.
        (47.5, 19.0, datetime(2099, 6, 21, 12, 0, tzinfo=UTC), "daylight"),
        # Budapest, midsummer 01:30 local solar time -> deep night.
        (47.5, 19.0, datetime(2099, 6, 21, 23, 30, tzinfo=UTC), "after_dark"),
        # Tromsø, winter solstice noon -> polar night.
        (69.65, 18.96, datetime(2099, 12, 21, 11, 0, tzinfo=UTC), "after_dark"),
        # Tromsø, midsummer late morning -> midnight sun.
        (69.65, 18.96, datetime(2099, 6, 21, 11, 0, tzinfo=UTC), "daylight"),
    ],
)
def test_time_readiness_classifies_real_solar_positions(latitude, longitude, when, expected):
    result = _readiness_without_network(latitude, longitude, when)

    assert result["daylight"] == expected
    altitude = result["sun_altitude_deg"]
    if expected == "daylight":
        assert altitude >= 0
    else:
        assert altitude < 0


def test_time_readiness_midnight_sun_stays_high_and_polar_night_stays_low():
    midnight_sun = _readiness_without_network(
        69.65, 18.96, datetime(2099, 6, 21, 11, 0, tzinfo=UTC)
    )
    polar_night = _readiness_without_network(
        69.65, 18.96, datetime(2099, 12, 21, 11, 0, tzinfo=UTC)
    )

    assert midnight_sun["sun_altitude_deg"] > 5.0
    # Solar noon at 69.65°N on the winter solstice: 90 - 69.65 - 23.44 ≈ -3.1°.
    assert polar_night["sun_altitude_deg"] < -1.0


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
    # A polygon with distinct salient corners (a constant-curvature square has
    # no privileged landmarks, so it would degenerate to a two-point guide).
    guide = [
        [47.0, 19.0],
        [47.002, 19.0005],
        [47.003, 19.0],
        [47.004, 19.001],
        [47.003, 19.002],
        [47.002, 19.0015],
        [47.001, 19.002],
        [47.0, 19.003],
        [47.0, 19.0],
    ]

    def fake_snap(points, **_):
        return points, 500.0, True, RouteReadiness(status="ready", data_quality="good")

    monkeypatch.setattr(ors_client, "snap_route_detailed", fake_snap)
    with TestClient(create_app()) as client:
        response = client.post(
            "/recognition-repair", json={"reference_points": guide, "sport": "run", "closed": True}
        )
    assert response.status_code == 200
    body = response.json()

    assert body["snapped"] is True
    assert body["distance_km"] == pytest.approx(0.5)  # from the stubbed router
    assert body["readiness"]["status"] == "ready"
    assert body["readiness"]["data_quality"] == "good"
    # Anchor guide keeps closure plus all 7 salient landmarks of the drawing.
    assert body["guide_points"][0] == body["guide_points"][-1]
    assert len(body["guide_points"]) == 8
    # Deterministic fidelity between the full drawing and its anchor version.
    assert body["recognition_score"] == pytest.approx(0.9554, abs=1e-3)
    assert "<gpx" in body["gpx"]
    assert "Refined GPS art" in body["gpx"]


def test_inkproof_forecast_reports_drift_resilience_and_mappable_details():
    with TestClient(create_app()) as client:
        response = client.post(
            "/inkproof-analysis",
            json={"points": POINTS, "accuracy_m": 10},
        )
    assert response.status_code == 200
    body = response.json()
    # The 100 m square is a clean drawing: deterministic simulations put it
    # just above the "durable" boundary with no fragile sections at all.
    assert body["resilience_score"] == pytest.approx(0.8595, abs=2e-3)
    assert body["expected_recognition"] == pytest.approx(0.8049, abs=2e-3)
    assert body["fragile_share"] == 0.0
    assert body["fragile_segments"] == []
    assert body["rating"] == "durable"
    assert body["tips"] == ["Wait for a stable GPS lock before starting the activity."]
    assert body["method"] == (
        "24 deterministic correlated-drift simulations plus detail-clearance analysis"
    )


def test_inkproof_forecast_flags_a_tight_pinch_as_fragile():
    # A hairpin whose two strokes pass ~15 m apart: normal 10 m drift merges
    # them into an unreadable blob.
    pinch = [
        [47.0, 19.0],
        [47.004, 19.0],
        [47.004, 19.0002],
        [47.0002, 19.0002],
        [47.0002, 19.001],
        [47.0, 19.001],
        [47.0, 19.0],
    ]

    body = art_rescue.inkproof_analysis([(lat, lon) for lat, lon in pinch], accuracy_m=10.0)

    assert body["fragile_share"] == pytest.approx(1.0)
    assert len(body["fragile_segments"]) == 1
    assert body["resilience_score"] == pytest.approx(0.6639, abs=2e-3)
    assert body["rating"] == "fragile"
    assert len(body["tips"]) == 3  # lock tip + slow-down + widen/enlarge advice
    first = body["fragile_segments"][0]
    assert first["id"] == "inkproof-1"
    assert 0 < first["risk_score"] <= 1
    assert first["reason"] in (
        "Nearby strokes may visually merge when the recorded position drifts.",
        "A tight turn may be rounded off by sparse or drifting GPS samples.",
    )
    assert first["points_preview"]


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


# ---- occasion catalog ------------------------------------------------------- #
def test_occasion_dates_resolve_movable_feasts_deterministically():
    by_id = {occasion.id: occasion for occasion in occasions.CATALOGUE}

    assert occasions.occasion_date(by_id["easter"], 2027) == date(2027, 3, 28)
    assert occasions.occasion_date(by_id["easter"], 2026) == date(2026, 4, 5)
    # First Advent 2026 is the Sunday between Nov 27 and Dec 3.
    assert occasions.occasion_date(by_id["first_advent"], 2026) == date(2026, 11, 29)
    assert occasions.occasion_date(by_id["first_advent"], 2022) == date(2022, 11, 27)
    # Mother's Day is the second Sunday of May.
    assert occasions.occasion_date(by_id["mothers_day"], 2026) == date(2026, 5, 10)
    # Children's Day (HU) is the last Sunday of May.
    assert occasions.occasion_date(by_id["childrens_day"], 2026) == date(2026, 5, 31)


def test_occasions_endpoint_lists_sorted_upcoming_entries():
    with TestClient(create_app()) as client:
        response = client.get("/occasions", params={"days_ahead": 365})
    assert response.status_code == 200
    payload = response.json()
    items = payload["occasions"]
    dates = [item["date"] for item in items]
    assert dates == sorted(dates)
    assert all(item["days_until"] >= 0 for item in items)
    ids = {item["id"] for item in items}
    assert {"valentines_day", "state_foundation_day", "remembrance_october_23"} <= ids
    heart = next(item for item in items if item["id"] == "valentines_day")
    assert heart["shape_prompt"] == "heart"


def test_occasions_endpoint_respects_the_requested_window():
    with TestClient(create_app()) as client:
        wide = client.get("/occasions", params={"days_ahead": 365}).json()["occasions"]
        narrow = client.get("/occasions", params={"days_ahead": 10}).json()["occasions"]

    assert len(narrow) <= len(wide)
    wide_by_id = {item["id"]: item for item in wide}
    for item in narrow:
        match = wide_by_id.get(item["id"])
        assert match is not None
        assert match["date"] == item["date"]
        assert item["days_until"] <= 10


def test_ongoing_multi_day_occasions_never_report_a_negative_countdown():
    # New Year's Eve lasts two days: on 1 January the occasion that started
    # on 31 December is still listed as "today", never with a past date or a
    # negative countdown.
    items = occasions.upcoming_occasions(today=date(2027, 1, 1), days_ahead=365)
    listed = next(item for item in items if item["id"] == "new_years_eve")
    assert listed["date"] == "2026-12-31"
    assert listed["days_until"] == 0
    assert all(item["days_until"] >= 0 for item in items)

    on_the_day = occasions.upcoming_occasions(today=date(2026, 12, 31), days_ahead=30)
    assert next(item for item in on_the_day if item["id"] == "new_years_eve")["days_until"] == 0


# ---- night readiness -------------------------------------------------------- #
def test_night_readiness_flags_unlit_and_busy_stretches(monkeypatch):
    route = [
        [47.5000, 19.0000],
        [47.5000, 19.0100],  # ~750 m east on an unlit primary road
        [47.5030, 19.0100],  # ~330 m north on a lit residential street
    ]
    ways = [
        {
            "highway": "primary",
            "lit": "no",
            "points": [(47.5000, 18.9995), (47.5000, 19.0105)],
        },
        {
            "highway": "residential",
            "lit": "yes",
            "points": [(47.4995, 19.0100), (47.5035, 19.0100)],
        },
    ]
    monkeypatch.setattr(osm_data, "fetch_lit_highways", lambda _bbox: ways)

    with TestClient(create_app()) as client:
        response = client.post("/night-readiness", json={"points": route})

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["status"] == "review"
    assert body["unlit_share"] > 0.6
    assert body["lit_share"] < 0.4
    assert body["traffic_label"] == "high"
    dark = [item for item in body["concerns"] if item["code"].startswith("dark_section")]
    assert len(dark) == 1
    assert dark[0]["distance_m"] > 500
    assert dark[0]["severity"] == "warning"
    assert dark[0]["segments_preview"]


def test_night_readiness_reports_a_fully_lit_quiet_route_as_ready(monkeypatch):
    route = [
        [47.5000, 19.0000],
        [47.5000, 19.0100],
        [47.5030, 19.0100],
        [47.5030, 19.0000],
        [47.5000, 19.0000],
    ]

    def lit_copy(points):
        return [{"highway": "cycleway", "lit": "yes", "points": list(points)}]

    # One tagged segment per leg keeps every sample within a few metres.
    ways = [
        lit_copy(route[0:2])[0],
        lit_copy(route[1:3])[0],
        lit_copy(route[2:4])[0],
        lit_copy([route[3], route[0]])[0],
    ]
    monkeypatch.setattr(osm_data, "fetch_lit_highways", lambda _bbox: ways)

    with TestClient(create_app()) as client:
        response = client.post("/night-readiness", json={"points": route})

    body = response.json()
    assert body["available"] is True
    assert body["status"] == "ready"
    assert body["lit_share"] > 0.9
    assert body["unlit_share"] < 0.05
    assert body["traffic_label"] == "low"
    assert not [item for item in body["concerns"] if item["severity"] == "warning"]


def test_night_readiness_degrades_when_openstreetmap_is_unreachable(monkeypatch):
    def unavailable(_bbox):
        raise osm_data.OsmUnavailable(
            "The OpenStreetMap context service is temporarily unavailable."
        )

    monkeypatch.setattr(osm_data, "fetch_lit_highways", unavailable)
    with TestClient(create_app()) as client:
        response = client.post("/night-readiness", json={"points": POINTS})

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["status"] == "unavailable"
    assert body["concerns"] == []


def test_night_readiness_rejects_invalid_coordinates():
    with TestClient(create_app()) as client:
        response = client.post("/night-readiness", json={"points": [[95.0, 19.0], [47.0, 19.0]]})
    assert response.status_code == 422


def test_nearest_segment_search_survives_chunk_boundaries():
    rng = np.random.default_rng(7)
    samples = rng.normal(0.0, 30.0, size=(60, 2))
    # 5,000 segments across three chunks; the true nearest segment sits in
    # the final chunk so a chunking bug would miss it.
    starts = rng.normal(0.0, 200.0, size=(5_000, 2))
    ends = starts + rng.normal(0.0, 5.0, size=(5_000, 2))
    weights = rng.uniform(0.0, 1.0, size=5_000)
    lit_values = np.array(["yes", "no"] * 2_500, dtype=object)
    true_target = 4_999
    starts[true_target] = samples[10]
    ends[true_target] = samples[10] + (1.0, 0.0)
    weights[true_target] = 0.42
    lit_values[true_target] = "no"

    distance, (weight, lit) = route_sampling.nearest_segment_attributes(
        samples, starts, ends, [weights, lit_values]
    )

    assert distance[10] == pytest.approx(0.0, abs=1e-6)
    assert weight[10] == pytest.approx(0.42)
    assert lit[10] == "no"
    assert distance.min() >= 0.0


def test_route_sampling_handles_degenerate_routes_and_rejects_invalid_settings():
    point = (47.5, 19.0)

    assert route_sampling.sample_route([]) == []
    assert route_sampling.sample_route([point]) == [point]
    assert route_sampling.sample_route([point, point]) == [point, point]
    with pytest.raises(ValueError, match="step_m"):
        route_sampling.sample_route([point, (47.51, 19.01)], step_m=0)
    with pytest.raises(ValueError, match="max_samples"):
        route_sampling.sample_route([point, (47.51, 19.01)], max_samples=1)


# ---- route landmarks -------------------------------------------------------- #
def test_route_landmarks_keep_corridor_hits_ordered_along_the_route(monkeypatch):
    route = [[47.5, 19.0], [47.5, 19.008], [47.5, 19.012], [47.5, 19.02]]
    places = [
        {"name": "Midway Museum", "kind": "museum", "lat": 47.5, "lon": 19.005},
        {"name": "Start Statue", "kind": "memorial", "lat": 47.5, "lon": 19.001},
        {"name": "Far Park", "kind": "attraction", "lat": 47.55, "lon": 19.005},
        {"name": "Midway Museum", "kind": "museum", "lat": 47.5, "lon": 19.015},
    ]
    monkeypatch.setattr(osm_data, "fetch_attractions", lambda _bbox: places)

    with TestClient(create_app()) as client:
        response = client.post("/route-landmarks", json={"points": route})

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    names = [landmark["name"] for landmark in body["landmarks"]]
    assert names == ["Start Statue", "Midway Museum"]
    offsets = [landmark["offset_km"] for landmark in body["landmarks"]]
    assert offsets == sorted(offsets)
    first = body["landmarks"][0]
    assert {first["latitude"], first["longitude"], first["kind"]} and first["offset_km"] >= 0


def test_route_landmarks_degrade_gracefully(monkeypatch):
    def unavailable(_bbox):
        raise osm_data.OsmUnavailable("down")

    monkeypatch.setattr(osm_data, "fetch_attractions", unavailable)
    with TestClient(create_app()) as client:
        response = client.post("/route-landmarks", json={"points": POINTS})
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["landmarks"] == []


def test_route_landmarks_skip_overpass_for_an_excessively_large_area(monkeypatch):
    def must_not_fetch(_bbox):  # pragma: no cover - assertion guard
        pytest.fail("large-area landmark requests must not reach Overpass")

    monkeypatch.setattr(osm_data, "fetch_attractions", must_not_fetch)
    with TestClient(create_app()) as client:
        response = client.post(
            "/route-landmarks",
            json={"points": [[47.5, 19.0], [47.7, 19.3], [47.8, 19.4], [47.5, 19.0]]},
        )

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert "too large" in response.json()["message"]


# ---- accessibility readiness ------------------------------------------------ #
def test_accessibility_flags_steps_and_wheelchair_barriers(monkeypatch):
    route = [
        [47.5000, 19.0000],
        [47.5000, 19.0100],  # steps: impassable for wheels
        [47.5030, 19.0100],  # wheelchair=yes residential street
    ]
    ways = [
        {"highway": "steps", "class": "steps", "points": [(47.5000, 18.9995), (47.5000, 19.0105)]},
        {
            "highway": "residential",
            "class": "wheelchair_yes",
            "points": [(47.4995, 19.0100), (47.5035, 19.0100)],
        },
    ]
    monkeypatch.setattr(osm_data, "fetch_accessibility_ways", lambda _bbox: ways)

    with TestClient(create_app()) as client:
        response = client.post("/accessibility-readiness", json={"points": route})

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["status"] == "review"
    assert body["steps_share"] > 0.6
    assert body["wheelchair_yes_share"] > 0.2
    barriers = body["concerns"]
    assert len(barriers) == 1
    assert barriers[0]["severity"] == "warning"
    assert barriers[0]["distance_m"] > 500


def test_accessibility_degrades_when_openstreetmap_is_unreachable(monkeypatch):
    def unavailable(_bbox):
        raise osm_data.OsmUnavailable("down")

    monkeypatch.setattr(osm_data, "fetch_accessibility_ways", unavailable)
    with TestClient(create_app()) as client:
        response = client.post("/accessibility-readiness", json={"points": POINTS})
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["concerns"] == []


def test_accessibility_treats_untagged_as_unknown_not_accessible(monkeypatch):
    route = [
        [47.5, 19.0],
        [47.5, 19.005],
        [47.505, 19.005],
        [47.5, 19.0],
    ]
    ways = [
        {
            "highway": "residential",
            "class": "untagged",
            "points": [(47.4995, 18.9995), (47.5055, 19.0055)],
        }
    ]
    monkeypatch.setattr(osm_data, "fetch_accessibility_ways", lambda _bbox: ways)
    with TestClient(create_app()) as client:
        response = client.post("/accessibility-readiness", json={"points": route})
    body = response.json()
    assert body["available"] is True
    assert body["wheelchair_yes_share"] == 0.0
    assert body["untagged_share"] > 0.9
    assert body["concerns"] == []


# ---- lesson pack ------------------------------------------------------------ #
def test_lesson_pack_produces_lettered_bearing_worksheet():
    square = [
        [47.5, 19.0],
        [47.5, 19.01],
        [47.505, 19.01],
        [47.505, 19.0],
        [47.5, 19.0],
    ]
    body = lesson_pack.build_lesson_pack(
        [(lat, lon) for lat, lon in square],
        closed=True,
        title="Square walk",
        shape_name="square",
    )
    assert body["available"] is True
    assert body["title"] == "Square walk"
    ids = [waypoint["id"] for waypoint in body["waypoints"]]
    assert ids[0] == "A"
    assert len(ids) >= 3
    for waypoint in body["waypoints"]:
        assert 0.0 <= waypoint["bearing_deg"] < 360.0
        assert waypoint["compass"] in {
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        }
        assert waypoint["leg_distance_m"] > 0
    # Eastward first leg on this square points at 90 degrees.
    assert body["waypoints"][0]["bearing_deg"] == pytest.approx(90.0, abs=1.0)
    assert body["scale_ratio"] > 100
    assert body["total_distance_km"] > 0.5
    assert body["waypoints"][-1]["to_id"] == "A"


def test_lesson_pack_closes_a_closed_shape_without_a_repeated_endpoint():
    triangle = [(47.5, 19.0), (47.5, 19.01), (47.506, 19.005)]

    body = lesson_pack.build_lesson_pack(triangle, closed=True)

    assert body["available"] is True
    assert body["waypoints"][-1]["to_id"] == "A"
    assert body["waypoint_count"] == len(body["waypoints"])


def test_lesson_pack_rejects_tiny_drawings():
    tiny = [[47.5, 19.0], [47.5, 19.00001], [47.50001, 19.0]]
    body = lesson_pack.build_lesson_pack([(lat, lon) for lat, lon in tiny])
    assert body["available"] is False


def test_lesson_pack_endpoint_validates_input():
    with TestClient(create_app()) as client:
        response = client.post(
            "/lesson-pack",
            json={"reference_points": [[47.0, 19.0], [47.001, 19.0]]},
        )
    assert response.status_code == 422


# ---- destinations ----------------------------------------------------------- #
def test_destination_catalog_maps_only_known_templates():
    from gps_art_wizzard.tools import shape_library

    for entry in destination_catalog.CATALOGUE:
        assert entry.shape_prompt in shape_library.SHAPES


def test_destination_art_for_city_filters_case_insensitively():
    picks = destination_catalog.destination_art_for_city("balatonfured")
    assert len(picks) == 1
    assert picks[0]["shape_prompt"] == "fish"
    assert picks[0]["partner_ready"] is True
    assert destination_catalog.destination_art_for_city("Nowhereville") == []


def test_destinations_endpoint_lists_curated_picks():
    with TestClient(create_app()) as client:
        response = client.get("/destinations")
    assert response.status_code == 200
    body = response.json()
    assert len(body["destinations"]) >= 8
    cities = {entry["city"] for entry in body["destinations"]}
    assert "Budapest" in cities


# ---- gallery campaign tags -------------------------------------------------- #
def test_gallery_publish_rejects_a_malformed_campaign_slug():
    with TestClient(create_app()) as client:
        response = client.post(
            "/gallery",
            json={
                "image_data_url": "data:image/png;base64," + "A" * 120,
                "publish_token": "t" * 24,
                "confirm_public_location": True,
                "campaign": "Bad Slug!",
            },
        )
    assert response.status_code == 422


def test_gallery_publish_forwards_the_campaign_tag(monkeypatch):
    captured: dict = {}

    def fake_upload(image_data_url, publish_token, *, campaign=None):
        captured["campaign"] = campaign
        return {
            "asset": {
                "id": "gps-art-gallery/" + "a" * 32,
                "image_url": "https://example.com/image.png",
                "width": 100,
                "height": 80,
                "campaign": campaign,
            },
            "removal_token": "r" * 64,
        }

    monkeypatch.setattr(gallery_api.cloudinary_gallery, "upload_gallery_image", fake_upload)
    monkeypatch.setattr(gallery_api.cloudinary_gallery, "is_configured", lambda: True)
    with TestClient(create_app()) as client:
        response = client.post(
            "/gallery",
            json={
                "image_data_url": "data:image/png;base64," + "A" * 120,
                "publish_token": "t" * 24,
                "confirm_public_location": True,
                "campaign": "pink-ribbon-2026",
            },
        )
    assert response.status_code == 200
    assert captured["campaign"] == "pink-ribbon-2026"
