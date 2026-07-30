"""Focused regression tests for route geometry, snapping, and validation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from gps_art_wizzard.agents.export_agent import ExportAgent
from gps_art_wizzard.agents.intent_agent import IntentAgent
from gps_art_wizzard.agents.placement_agent import PlacementAgent
from gps_art_wizzard.agents.planning_agent import PlanningAgent
from gps_art_wizzard.agents.preflight_agent import PreflightAgent
from gps_art_wizzard.agents.refinement_agent import RefinementAgent
from gps_art_wizzard.agents.shape_agent import ShapeAgent, _validated_paths
from gps_art_wizzard.agents.validation_agent import ValidationAgent
from gps_art_wizzard.api.routes import (
    EditedRouteRequest,
    _even_sample,
    _state_to_response,
    edit_route,
)
from gps_art_wizzard.config import RoutingConfig
from gps_art_wizzard.llm import factory as llm_factory
from gps_art_wizzard.orchestrator import Orchestrator
from gps_art_wizzard.state import (
    Intent,
    Plan,
    RouteDraft,
    Shape,
    SnappedRoute,
    Validation,
    WorkflowState,
)
from gps_art_wizzard.tools import (
    geo,
    geocoder,
    gpx_writer,
    ors_client,
    shape_library,
    shape_similarity,
)


def test_keyword_matching_does_not_treat_letters_inside_city_as_shapes():
    cat = shape_library.find_by_keyword("draw a cat in London")
    assert cat is not None
    assert cat[0] == "cat"

    assert shape_library.find_by_keyword("jog around London") is None
    circle = shape_library.find_by_keyword("draw an O in London")
    assert circle is not None
    assert circle[0] == "circle"


def test_intent_fallback_distinguishes_a_shape_from_written_text():
    agent = IntentAgent()
    intent = agent._parse(agent._fallback("draw a heart in Budapest, 8 km").text)
    assert intent.shape == "heart"
    assert intent.text is None
    assert intent.distance_km == 8.0

    text_intent = agent._parse(agent._fallback("write HI in Berlin").text)
    assert text_intent.text == "HI"


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("draw the letter A in Miskolc, 10 km", "A"),
        ("draw the number 42 while cycling in Eger, 20 km", "42"),
    ],
)
def test_intent_fallback_parses_labelled_letters_and_numbers(prompt, expected):
    agent = IntentAgent()
    intent = agent._parse(agent._fallback(prompt).text)

    assert intent.shape == "text"
    assert intent.text == expected
    assert intent.city in {"Miskolc", "Eger"}


def test_common_template_intent_skips_remote_llm(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("a fully parsed template request must not call an LLM")

    monkeypatch.setattr(
        "gps_art_wizzard.agents.intent_agent.try_complete",
        fail_if_called,
    )
    state = WorkflowState(prompt="draw an 8 km heart run in Tatabánya")

    IntentAgent().run(state)

    assert state.intent is not None
    assert state.intent.shape == "heart"
    assert state.intent.city == "Tatabánya"
    assert state.intent.distance_km == 8.0


def test_intent_rejects_non_finite_distance_and_bounds_large_requests():
    agent = IntentAgent()
    invalid = agent._parse(
        json.dumps({"sport": "run", "distance_km": "NaN", "suggest": "false"})
    )
    assert invalid.distance_km is None
    assert invalid.suggest is False

    bounded = agent._parse(json.dumps({"sport": "run", "distance_km": 100_000}))
    assert bounded.distance_km == 60.0


def test_stitch_paths_reverses_next_stroke_to_minimise_transfer():
    paths = [
        [(0.0, 0.0), (1.0, 0.0)],
        [(5.0, 0.0), (2.0, 0.0)],
        [(8.0, 0.0), (6.0, 0.0)],
    ]
    stitched = geo.stitch_paths(paths)
    assert stitched == [
        (0.0, 0.0),
        (1.0, 0.0),
        (2.0, 0.0),
        (5.0, 0.0),
        (6.0, 0.0),
        (8.0, 0.0),
    ]
    assert geo.unit_path_length(stitched) == pytest.approx(8.0)


def test_wave_and_helix_templates_keep_recognisable_proportions():
    _, wave_paths, _ = shape_library.wave()
    assert all(
        all(next_point[0] > point[0] for point, next_point in zip(path, path[1:], strict=False))
        for path in wave_paths
    )

    _, helix_paths, _ = shape_library.helix()
    helix_y = [point[1] for path in helix_paths[:2] for point in path]
    assert max(helix_y) - min(helix_y) == pytest.approx(2.0)


def test_butterfly_is_a_short_closed_routable_silhouette():
    name, paths, closed = shape_library.butterfly()
    path = paths[0]

    assert name == "butterfly"
    assert closed is True
    assert path[0] == path[-1]
    assert 50 <= len(path) <= 150
    # The former mathematical curve travelled roughly forty unit-lengths and
    # repeatedly crossed itself. A compact outline gives ORS a feasible loop.
    assert 8.0 < geo.unit_path_length(path) < 14.0

    left = min(point[0] for point in path)
    right = max(point[0] for point in path)
    assert left == pytest.approx(-right)
    assert any(point[1] > 1.0 for point in path)  # recognisable antennae
    assert any(point[1] < -0.9 for point in path)  # lower-wing/body tip


def test_all_empty_shape_paths_normalise_safely():
    assert geo.normalize_shape([[], []]) == [[(0.0, 0.0)]]


def test_projection_rejects_invalid_scale_and_polar_centre():
    with pytest.raises(ValueError, match="positive"):
        geo.unit_to_latlon(0.0, 0.0, 47.5, 19.0, 0.0)
    with pytest.raises(ValueError, match="strictly"):
        geo.unit_to_latlon(0.0, 0.0, 90.0, 19.0, 100.0)


def test_unknown_offline_city_is_explicitly_marked_as_substituted():
    result = geocoder._default("Atlantis")
    assert result.name == "Budapest"
    assert result.substituted is True
    assert geocoder._default("Berlin").substituted is False


def test_known_city_geocoding_uses_local_route_database(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("known cities must not call public Nominatim")

    monkeypatch.setattr(geocoder.httpx, "get", fail_if_called)

    result = geocoder.geocode("Tatabánya")

    assert result.name == "Tatabánya"
    assert result.substituted is False
    assert result.lat == pytest.approx(47.5853)


@pytest.mark.parametrize("city", ["Miskolc", "Eger"])
def test_requested_additional_cities_have_local_route_profiles(city, monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("supported Hungarian cities must resolve locally")

    monkeypatch.setattr(geocoder.httpx, "get", fail_if_called)
    result = geocoder.geocode(city)

    assert result.name == city
    assert result.substituted is False
    assert geocoder.city_context(city, result)


def test_resample_expands_two_point_line_by_arc_length():
    sampled = shape_similarity.resample(np.array([[0.0, 0.0], [1.0, 0.0]]), 9)
    assert sampled.shape == (9, 2)
    assert sampled[4].tolist() == pytest.approx([0.5, 0.0])


def test_route_similarity_is_direction_independent_and_detects_distortion():
    reference = [
        (47.0, 19.0),
        (47.0, 19.01),
        (47.01, 19.01),
        (47.01, 19.0),
    ]
    reversed_score = shape_similarity.fidelity_between_routes(reference, reference[::-1])
    distorted = [
        (47.0, 19.0),
        (47.0, 19.01),
        (47.0001, 19.02),
        (47.0, 19.03),
    ]
    distorted_score = shape_similarity.fidelity_between_routes(reference, distorted)
    assert reversed_score > 0.99
    assert distorted_score < reversed_score - 0.15


def test_closed_route_similarity_ignores_start_vertex():
    loop = [
        (47.0, 19.0),
        (47.0, 19.01),
        (47.01, 19.01),
        (47.01, 19.0),
        (47.0, 19.0),
    ]
    shifted = loop[2:-1] + loop[:3]
    assert shifted[0] == shifted[-1]
    assert shape_similarity.fidelity_between_routes(loop, shifted) > 0.98


def test_similarity_rejects_backtracking_scribble_inside_the_right_outline():
    reference = [
        (47.0, 19.0),
        (47.0, 19.01),
        (47.01, 19.01),
        (47.01, 19.0),
        (47.0, 19.0),
    ]
    backtracking = [
        (47.0, 19.0),
        (47.0, 19.008),
        (47.0, 19.003),
        (47.0, 19.01),
        (47.008, 19.01),
        (47.003, 19.01),
        (47.01, 19.01),
        (47.01, 19.002),
        (47.01, 19.008),
        (47.01, 19.0),
        (47.002, 19.0),
        (47.007, 19.0),
        (47.0, 19.0),
    ]

    diagnostics = shape_similarity.similarity_diagnostics_between_routes(
        reference,
        backtracking,
    )

    assert diagnostics.coverage_similarity > 0.9
    assert diagnostics.turning_similarity < 0.5
    assert diagnostics.route_length_ratio > 1.8
    assert diagnostics.fidelity < 0.7


def test_subsample_honours_closed_coordinate_budget_and_extrema():
    _, paths, _ = shape_library.heart()
    route = [
        geo.unit_to_latlon(x, y, 47.5, 19.0, 2_000.0)
        for x, y in geo.normalize_shape(paths)[0]
    ]
    sampled = ors_client._subsample(route, closed=True, max_points=50)
    assert len(sampled) <= 50
    assert sampled[0] == sampled[-1]
    original_lats = [point[0] for point in route]
    original_lons = [point[1] for point in route]
    sampled_lats = [point[0] for point in sampled]
    sampled_lons = [point[1] for point in sampled]
    assert max(sampled_lats) - min(sampled_lats) >= 0.98 * (
        max(original_lats) - min(original_lats)
    )
    assert max(sampled_lons) - min(sampled_lons) >= 0.98 * (
        max(original_lons) - min(original_lons)
    )


def test_subsample_adds_guidance_along_sparse_long_edges_and_keeps_corners():
    route = [
        geo.unit_to_latlon(x, y, 47.5, 19.0, 2_500.0)
        for x, y in geo.normalize_shape(shape_library.diamond()[1])[0]
    ]

    sampled = ors_client._subsample(route, closed=True, max_points=50)

    assert 20 <= len(sampled) <= 50
    assert sampled[0] == sampled[-1]
    assert all(corner in sampled for corner in route)
    assert max(
        geo.haversine(*start, *end)
        for start, end in zip(sampled, sampled[1:], strict=False)
    ) <= 400.0


def test_tree_is_a_single_closed_route_without_transfer_stroke():
    name, paths, closed = shape_library.tree()

    assert name == "tree"
    assert closed is True
    assert len(paths) == 1
    assert paths[0][0] == paths[0][-1]


@pytest.mark.parametrize("shape_name", ["cat", "dog"])
def test_animal_templates_are_single_closed_street_routable_silhouettes(shape_name):
    generated = shape_library.get_shape(shape_name)

    assert generated is not None
    name, paths, closed = generated
    assert name == shape_name
    assert closed is True
    assert len(paths) == 1
    assert paths[0][0] == paths[0][-1]
    assert 12 <= len(paths[0]) <= 80


def test_dog_keyword_uses_template_instead_of_llm_fallback(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("known dog template must not call an LLM")

    monkeypatch.setattr(
        "gps_art_wizzard.agents.shape_agent.try_complete",
        fail_if_called,
    )
    state = WorkflowState(
        prompt="a dog run in Tatabánya, 10 km",
        intent=Intent("a dog", None, "Tatabánya", "run", 10.0, None),
        plan=Plan(shape_strategy="template"),
    )

    ShapeAgent().run(state)

    assert state.shape is not None
    assert state.shape.name == "dog"
    assert state.shape.source == "template"


def test_straight_preview_closes_once_and_is_not_claimed_as_routable():
    points = [(47.0, 19.0), (47.001, 19.001), (47.0, 19.0)]
    route, distance, snapped = ors_client._straight_line_connector(points, closed=True)
    assert route[0] == route[-1]
    assert route[-2] != route[-1]
    assert distance > 0
    assert snapped is False


class _FakeResponse:
    status_code = 200
    text = ""

    def json(self):
        return {
            "features": [
                {
                    "geometry": {
                        "coordinates": [
                            [19.0, 47.0],
                            [19.001, 47.0],
                            [19.002, 47.0],
                        ]
                    },
                    "properties": {
                        "segments": [
                            {"distance": 100.0},
                            {"distance": 120.0},
                        ]
                    },
                }
            ]
        }


class _FakeClient:
    def __init__(self):
        self.payload = None

    def post(self, _url, *, json, headers, timeout):
        assert headers["Content-Type"] == "application/json"
        assert timeout == ors_client._HTTP_TIMEOUT
        self.payload = json
        return _FakeResponse()


def test_ors_request_uses_boolean_and_sums_all_segment_distances():
    client = _FakeClient()
    result = ors_client._ors_request(
        "https://example.test/route",
        {"Content-Type": "application/json"},
        [[19.0, 47.0], [19.001, 47.0], [19.002, 47.0]],
        preference="recommended",
        continue_straight=True,
        radius=350,
        client=client,
    )
    assert result is not None
    route, distance = result
    assert len(route) == 3
    assert distance == pytest.approx(220.0)
    assert client.payload["continue_straight"] is True


class _FakeErrorResponse:
    status_code = 404
    text = "route not found"

    def json(self):
        return {
            "error": {
                "code": 2009,
                "message": (
                    "Route could not be found - Unable to find a route "
                    "between points 4 (19.1 47.5) and 5 (19.2 47.5)."
                ),
            }
        }


class _FakeErrorClient:
    def post(self, _url, *, json, headers, timeout):
        assert json["continue_straight"] is False
        return _FakeErrorResponse()


def test_ors_failure_preserves_internal_code_and_failed_pair():
    failure = ors_client._ors_request(
        "https://example.test/route",
        {"Content-Type": "application/json"},
        [[19.0, 47.0], [19.1, 47.1]],
        preference="recommended",
        continue_straight=False,
        radius=350,
        client=_FakeErrorClient(),
    )
    assert isinstance(failure, ors_client._ORSFailure)
    assert failure.status_code == 404
    assert failure.error_code == 2009
    assert "between points 4" in failure.message


def test_routing_default_allows_gps_art_u_turns(monkeypatch):
    monkeypatch.delenv("ORS_CONTINUE_STRAIGHT", raising=False)
    assert RoutingConfig().continue_straight is False


def test_failed_pair_pruning_preserves_closed_loop_endpoints():
    waypoints = [
        (47.0, 19.0),
        (47.1, 19.1),
        (47.2, 19.2),
        (47.3, 19.3),
        (47.0, 19.0),
    ]
    reduced = ors_client._prune_failed_pair(
        waypoints,
        "Unable to find a route between points 1 (x) and 2 (y).",
        closed=True,
    )
    assert reduced == [
        (47.0, 19.0),
        (47.1, 19.1),
        (47.3, 19.3),
        (47.0, 19.0),
    ]


def test_snap_route_uses_self_hosted_ors_without_api_key(monkeypatch):
    routing = SimpleNamespace(
        ors_api_key="",
        ors_base_url="http://ors.internal/ors",
        snap_radius_m=350,
        preference="recommended",
        continue_straight=True,
    )
    monkeypatch.setattr(ors_client, "get_settings", lambda: SimpleNamespace(routing=routing))
    requests: list[list[list[float]]] = []

    def fake_request(_url, _headers, coords, **_kwargs):
        requests.append(coords)
        polyline = [(lat, lon) for lon, lat in coords]
        return polyline, geo.path_distance_m(polyline)

    monkeypatch.setattr(ors_client, "_ors_request", fake_request)
    waypoints = [
        geo.unit_to_latlon(math.cos(t), math.sin(t), 47.5, 19.0, 1_000.0)
        for t in np.linspace(0, 2 * math.pi, 200)
    ]
    route, distance, snapped = ors_client.snap_route(waypoints, closed=True)
    assert requests
    assert len(requests[0]) <= ors_client._MAX_GUIDE_COORDINATES
    assert requests[0][0] == requests[0][-1]
    assert route[0] == route[-1]
    assert distance > 0
    assert snapped is True


def test_failed_snap_reduces_waypoint_budget_without_duplicate_round(monkeypatch):
    routing = SimpleNamespace(
        ors_api_key="test",
        ors_base_url="https://api.openrouteservice.org",
        snap_radius_m=350,
        preference="recommended",
        continue_straight=True,
    )
    monkeypatch.setattr(ors_client, "get_settings", lambda: SimpleNamespace(routing=routing))
    request_sizes: list[int] = []

    def always_fail(_url, _headers, coords, **_kwargs):
        request_sizes.append(len(coords))
        return ors_client._ORSFailure(
            404,
            2009,
            "Route could not be found without a reported waypoint pair.",
        )

    monkeypatch.setattr(ors_client, "_ors_request", always_fail)
    waypoints = [
        (47.0 + index * 0.0001, 19.001 if index % 2 else 19.0)
        for index in range(100)
    ]
    _, _, snapped = ors_client.snap_route(waypoints)
    assert snapped is False
    assert len(request_sizes) <= ors_client._MAX_ORS_ATTEMPTS
    distinct_sizes = list(dict.fromkeys(request_sizes))
    assert len(distinct_sizes) >= 2
    assert distinct_sizes == sorted(distinct_sizes, reverse=True)


def test_snap_preflight_ranks_shape_preservation_above_collapsed_points(monkeypatch):
    routing = SimpleNamespace(
        ors_base_url="http://localhost:8080/ors",
        ors_api_key="",
        snap_radius_m=120,
    )
    monkeypatch.setattr(ors_client, "get_settings", lambda: SimpleNamespace(routing=routing))

    collapsed = [
        (47.0000, 19.0000),
        (47.0000, 19.0010),
        (47.0010, 19.0010),
        (47.0010, 19.0000),
        (47.0000, 19.0000),
    ]
    preserved = [
        (47.1000, 19.1000),
        (47.1000, 19.1010),
        (47.1010, 19.1010),
        (47.1010, 19.1000),
        (47.1000, 19.1000),
    ]

    def fake_snap(_url, _headers, locations, *, radius, client):
        assert radius == 120
        midpoint = len(locations) // 2
        output = []
        for index, location in enumerate(locations):
            snapped_location = locations[0] if index < midpoint else location
            output.append(
                {
                    "location": snapped_location,
                    "snapped_distance": 70.0 if index < midpoint else 2.0,
                }
            )
        return output

    monkeypatch.setattr(ors_client, "_snap_request", fake_snap)

    results = ors_client.preflight_route_candidates(
        [collapsed, preserved],
        sport="run",
        closed=True,
        max_guide_points=5,
    )

    assert results is not None
    assert results[0].candidate_index == 1
    assert results[0].score > results[1].score
    assert results[0].snap_coverage == 1.0
    assert results[0].shape_fidelity > 0.9


def test_snap_preflight_keeps_original_index_when_an_invalid_route_is_skipped(
    monkeypatch,
):
    routing = SimpleNamespace(
        ors_base_url="http://localhost:8080/ors",
        ors_api_key="",
        snap_radius_m=120,
    )
    monkeypatch.setattr(ors_client, "get_settings", lambda: SimpleNamespace(routing=routing))

    def identity_snap(_url, _headers, locations, *, radius, client):
        return [
            {"location": location, "snapped_distance": 1.0}
            for location in locations
        ]

    monkeypatch.setattr(ors_client, "_snap_request", identity_snap)
    results = ors_client.preflight_route_candidates(
        [
            [(47.0, 19.0)],
            [(47.1, 19.1), (47.101, 19.101), (47.102, 19.100)],
        ],
        closed=False,
    )

    assert results is not None
    assert [result.candidate_index for result in results] == [1]


def test_connectivity_retry_drops_reported_via_point_before_success(monkeypatch):
    routing = SimpleNamespace(
        ors_api_key="test",
        ors_base_url="https://api.openrouteservice.org",
        snap_radius_m=350,
        preference="recommended",
        continue_straight=False,
    )
    monkeypatch.setattr(ors_client, "get_settings", lambda: SimpleNamespace(routing=routing))
    request_sizes: list[int] = []
    request_radii: list[int] = []

    def fail_once_then_route(_url, _headers, coords, **kwargs):
        request_sizes.append(len(coords))
        request_radii.append(kwargs["radius"])
        assert kwargs["continue_straight"] is False
        if len(request_sizes) == 1:
            return ors_client._ORSFailure(
                404,
                2009,
                "Unable to find a route between points 4 (x) and 5 (y).",
            )
        polyline = [(lat, lon) for lon, lat in coords]
        return polyline, geo.path_distance_m(polyline)

    monkeypatch.setattr(ors_client, "_ors_request", fail_once_then_route)
    waypoints = [
        (47.0 + index * 0.0001, 19.0 + (index % 3) * 0.0001)
        for index in range(12)
    ]
    route, distance, snapped = ors_client.snap_route(waypoints)
    assert snapped is True
    assert len(route) == 11
    assert distance > 0
    assert request_sizes == [12, 11]
    assert request_radii == [350, 350]


def test_refinement_ignores_non_finite_values_and_clamps_extremes():
    draft = RouteDraft(
        center_lat=47.5,
        center_lon=19.0,
        scale_m=1_000.0,
        rotation_deg=0.0,
        lat_offset_m=0.0,
        lon_offset_m=0.0,
        simplify_tolerance=0.8,
        waypoints=[],
        closed=False,
    )
    RefinementAgent()._apply(
        draft,
        {
            "scale_factor": "NaN",
            "rotation_delta_deg": 999,
            "lat_offset_m": 1_000_000,
            "lon_offset_m": -1_000_000,
            "simplify_tolerance": 1_000,
        },
    )
    assert draft.scale_m == 1_000.0
    assert draft.rotation_deg == 90.0
    assert draft.lat_offset_m == 20_000.0
    assert draft.lon_offset_m == -20_000.0
    assert draft.simplify_tolerance == 25.0


def test_preflight_agent_scans_city_wide_transforms_and_builds_shortlist(
    monkeypatch,
):
    workflow = SimpleNamespace(
        preflight_enabled=True,
        preflight_max_placements=180,
        preflight_shortlist=2,
        preflight_guide_points=12,
    )
    monkeypatch.setattr(
        "gps_art_wizzard.agents.preflight_agent.get_settings",
        lambda: SimpleNamespace(workflow=workflow),
    )
    observed: dict[str, int] = {}

    def fake_preflight(routes, **_kwargs):
        observed["count"] = len(routes)
        return [
            ors_client.SnapPreflightResult(1, 0.91, 1.0, 2.0, 0.9, 0.9, 0.9, 1.0),
            ors_client.SnapPreflightResult(0, 0.82, 1.0, 4.0, 0.8, 0.8, 0.8, 1.0),
        ]

    monkeypatch.setattr(ors_client, "preflight_route_candidates", fake_preflight)
    draft = RouteDraft(
        center_lat=47.5853,
        center_lon=18.4041,
        scale_m=600.0,
        rotation_deg=0.0,
        lat_offset_m=0.0,
        lon_offset_m=0.0,
        simplify_tolerance=0.8,
        waypoints=[],
        closed=True,
        target_distance_km=8.0,
    )
    shape_data = shape_library.triangle()
    state = WorkflowState(
        prompt="triangle in Tatabánya",
        intent=Intent("triangle", None, "Tatabánya", "run", 8.0, None),
        plan=Plan(
            shape_strategy="template",
            center_lat=draft.center_lat,
            center_lon=draft.center_lon,
            city_bbox=(47.56, 47.61, 18.35, 18.46),
        ),
        shape=Shape("triangle", shape_data[1], shape_data[2]),
        route_draft=draft,
    )

    PreflightAgent().run(state)

    assert observed["count"] >= 50
    assert state.preflight_count == observed["count"]
    assert state.route_draft is not None
    assert state.route_draft.preflight_score == pytest.approx(0.91)
    assert len(state.placement_candidates) == 1
    assert state.placement_candidates[0].preflight_score == pytest.approx(0.82)


def test_preflight_shortlist_prefers_a_diverse_high_quality_alternative():
    def draft(rotation, lat_offset, lon_offset):
        return RouteDraft(
            47.5,
            19.0,
            1_000.0,
            rotation,
            lat_offset,
            lon_offset,
            0.8,
            [(47.5, 19.0), (47.51, 19.01)],
            True,
            8.0,
        )

    drafts = [
        draft(0.0, 0.0, 0.0),
        draft(2.0, 20.0, 15.0),
        draft(90.0, 3_000.0, -2_500.0),
    ]
    results = [
        ors_client.SnapPreflightResult(0, 0.90, 1.0, 2.0, 0.9, 0.9, 0.9, 1.0),
        ors_client.SnapPreflightResult(1, 0.89, 1.0, 2.0, 0.9, 0.9, 0.9, 1.0),
        ors_client.SnapPreflightResult(2, 0.84, 1.0, 3.0, 0.84, 0.84, 0.84, 1.0),
    ]

    selected = PreflightAgent._diverse_shortlist(results, drafts, 2)

    assert [result.candidate_index for result in selected] == [0, 2]


def test_refinement_consumes_ranked_placement_before_local_heuristics():
    current = RouteDraft(
        47.5,
        19.0,
        1_000.0,
        0.0,
        0.0,
        0.0,
        0.8,
        [(47.5, 19.0), (47.51, 19.01)],
        True,
        8.0,
    )
    shortlisted = RouteDraft(
        47.5,
        19.0,
        900.0,
        60.0,
        1_200.0,
        -800.0,
        0.8,
        [(47.51, 18.99), (47.52, 19.0)],
        True,
        8.0,
        preflight_score=0.88,
    )
    state = WorkflowState(
        prompt="heart in Budapest",
        intent=Intent("heart", None, "Budapest", "run", 8.0, None),
        shape=Shape("heart", shape_library.heart()[1], True),
        route_draft=current,
        snapped=SnappedRoute(current.waypoints, 12_000.0, snapped=True),
        validation=Validation(0.5, 1.0, 0.4, 0.45, on_roads=True),
        placement_candidates=[shortlisted],
    )

    RefinementAgent().run(state)

    assert state.route_draft is not shortlisted
    assert state.route_draft.rotation_deg == 60.0
    assert state.route_draft.lat_offset_m == 1_200.0
    assert state.placement_candidates == []
    assert "shortlist" in state.history[-1]["note"]


def test_omitted_running_distance_uses_practical_eight_kilometre_default():
    state = WorkflowState(
        prompt="draw an arrow in Tatabánya",
        intent=Intent("arrow", None, "Tatabánya", "run", None, None),
        plan=Plan(
            shape_strategy="template",
            center_lat=47.58,
            center_lon=18.39,
            city_bbox=(47.5, 18.3, 47.7, 18.5),
        ),
        shape=Shape(
            name="arrow",
            paths=shape_library.arrow()[1],
            closed=False,
        ),
    )

    PlacementAgent().run(state)

    assert state.route_draft is not None
    assert state.route_draft.target_distance_km == pytest.approx(8.0)
    assert state.route_draft.scale_m < 3_000.0


def test_refinement_shrinks_a_measured_route_that_is_over_target():
    draft = RouteDraft(
        center_lat=47.5,
        center_lon=19.0,
        scale_m=1_000.0,
        rotation_deg=0.0,
        lat_offset_m=0.0,
        lon_offset_m=0.0,
        simplify_tolerance=0.8,
        waypoints=[(47.5, 19.0), (47.51, 19.01)],
        closed=True,
        target_distance_km=8.0,
    )
    state = WorkflowState(
        prompt="heart in Budapest, 8 km",
        intent=Intent("heart", None, "Budapest", "run", 8.0, None),
        shape=Shape("heart", shape_library.heart()[1], True),
        route_draft=draft,
        snapped=SnappedRoute(draft.waypoints, 10_650.0, snapped=True),
        validation=Validation(
            score=0.66,
            closure=0.9,
            distance_fit=0.37,
            shape_fidelity=0.699,
            on_roads=True,
        ),
        iterations=1,
    )

    RefinementAgent().run(state)

    assert draft.scale_m == pytest.approx(1_000.0 * 8.0 / 10.65)
    assert draft.scale_m < 1_000.0
    assert "shrink" in state.history[-1]["note"]


def test_refinement_preserves_promising_grid_alignment_during_large_scale_fix():
    draft = RouteDraft(
        center_lat=46.9,
        center_lon=18.05,
        scale_m=3_247.6,
        rotation_deg=330.0,
        lat_offset_m=-1_500.0,
        lon_offset_m=900.0,
        simplify_tolerance=0.3,
        waypoints=[(46.9, 18.05), (46.91, 18.06)],
        closed=True,
        target_distance_km=21.0,
    )
    state = WorkflowState(
        prompt="wave in Siófok",
        intent=Intent("wave", None, "Siófok", "run", 21.0, None),
        shape=Shape("wave", shape_library.wave()[1], False),
        route_draft=draft,
        snapped=SnappedRoute(draft.waypoints, 14_770.0, snapped=True),
        validation=Validation(
            score=0.63,
            closure=1.0,
            distance_fit=0.41,
            shape_fidelity=0.616,
            on_roads=True,
        ),
        iterations=3,
    )

    RefinementAgent().run(state)

    assert draft.scale_m == pytest.approx(3_247.6 * 21.0 / 14.77)
    assert draft.rotation_deg == 330.0
    assert draft.lat_offset_m == -1_500.0
    assert draft.lon_offset_m == 900.0


def test_refinement_brackets_then_escapes_a_rejected_scale_candidate():
    draft = RouteDraft(
        center_lat=47.69,
        center_lon=17.65,
        scale_m=772.1,
        rotation_deg=0.0,
        lat_offset_m=1_500.0,
        lon_offset_m=0.0,
        simplify_tolerance=0.5,
        waypoints=[(47.69, 17.65), (47.70, 17.66)],
        closed=True,
        target_distance_km=10.0,
    )
    actual_km = 7.24
    full_factor = 10.0 / actual_km
    damped_factor = math.sqrt(full_factor)
    common = dict(
        agent="refinement",
        rotation_deg=0.0,
        lat_offset_m=1_500.0,
        lon_offset_m=0.0,
        simplify_tolerance=0.325,
    )
    state = WorkflowState(
        prompt="star in Győr, 10 km",
        intent=Intent("star", None, "Győr", "run", 10.0, None),
        shape=Shape("star", shape_library.star()[1], True),
        route_draft=draft,
        snapped=SnappedRoute(draft.waypoints, actual_km * 1_000, snapped=True),
        validation=Validation(
            score=0.557,
            closure=1.0,
            distance_fit=0.437,
            shape_fidelity=0.451,
            on_roads=True,
        ),
        history=[
            {
                **common,
                "scale_m": draft.scale_m * full_factor,
            }
        ],
        iterations=3,
    )
    agent = RefinementAgent()

    damped = agent._heuristic(state)
    assert damped["scale_factor"] == pytest.approx(damped_factor)
    assert damped["rotation_delta_deg"] is None

    state.history.append(
        {
            **common,
            "scale_m": draft.scale_m * damped_factor,
        }
    )
    grid = agent._heuristic(state)
    assert grid["scale_factor"] is None
    assert grid["lon_offset_m"] < 0
    assert "grid" in str(grid["rationale"])


def test_shape_suggestion_avoids_complex_outline_on_hilly_sparse_streets():
    agent = PlanningAgent()
    assert (
        agent._heuristic_suggest(
            "Hilly city with sparse, irregular and winding streets", "run"
        )
        == "circle"
    )
    assert agent._heuristic_suggest("An excellent near-perfect grid", "bike") == "butterfly"


def test_city_suggestions_are_varied_across_hungarian_route_profiles():
    agent = PlanningAgent()
    cities = [
        "Budapest",
        "Debrecen",
        "Szeged",
        "Miskolc",
        "Pécs",
        "Győr",
        "Nyíregyháza",
        "Kecskemét",
        "Eger",
        "Sopron",
        "Székesfehérvár",
        "Siófok",
        "Veszprém",
        "Tatabánya",
    ]
    suggestions = {
        agent._heuristic_suggest("", "run", city=city)
        for city in cities
    }

    assert len(suggestions) >= 10
    assert agent._heuristic_suggest("", "run", city="Miskolc") == "mountain"
    assert agent._heuristic_suggest("", "run", city="Eger") == "crown"
    assert agent._heuristic_suggest("", "run", city="Siófok") == "wave"


def test_city_suggestion_builds_three_distinct_measurable_candidates():
    agent = PlanningAgent()
    result = agent._suggestion_candidates(
        "Eger is hilly with irregular and winding streets",
        "run",
        city="Eger",
    )

    assert result[0] == "crown"
    assert len(result) == 3
    assert len(set(result)) == 3
    assert all(shape_library.get_shape(name) for name in result)


def test_candidate_selection_prefers_visible_shape_over_distance_only_score():
    incumbent = Validation(
        score=0.666,
        closure=1.0,
        distance_fit=0.947,
        shape_fidelity=0.363,
        on_roads=True,
    )
    candidate = Validation(
        score=0.631,
        closure=1.0,
        distance_fit=0.411,
        shape_fidelity=0.616,
        on_roads=True,
    )

    assert Orchestrator._candidate_is_better(candidate, incumbent) is True
    assert Orchestrator._candidate_is_better(incumbent, candidate) is False


def test_suggestion_search_skips_extra_routes_when_primary_is_already_good():
    class UnexpectedNode:
        def run(self, _state):
            pytest.fail("a passing primary suggestion must not request another route")

    points = [(47.0, 19.0), (47.01, 19.01)]
    state = WorkflowState(
        prompt="suggest a run in Debrecen",
        intent=Intent("butterfly", None, "Debrecen", "run", 10.0, None),
        plan=Plan(
            shape_strategy="template",
            suggested_shape="butterfly",
            suggestion_candidates=["butterfly", "heart", "diamond"],
        ),
        shape=Shape("butterfly", shape_library.butterfly()[1], True),
        route_draft=RouteDraft(
            47.0, 19.0, 1_000.0, 0.0, 0.0, 0.0, 0.8, points, True, 10.0
        ),
        snapped=SnappedRoute(points, 10_000.0, snapped=True),
        validation=Validation(0.82, 1.0, 0.9, 0.78, on_roads=True),
    )
    nodes = {
        name: UnexpectedNode()
        for name in ("shape", "placement", "snap", "validation")
    }

    Orchestrator(nodes={})._evaluate_suggestion_candidates(state, nodes)

    assert state.shape.name == "butterfly"
    assert state.history == []


def test_suggestion_search_measures_alternatives_and_keeps_best_shape():
    class Node:
        def __init__(self, operation):
            self.operation = operation

        def run(self, state):
            self.operation(state)
            return state

    points = [(47.0, 19.0), (47.01, 19.01)]
    state = WorkflowState(
        prompt="suggest a run in Eger",
        intent=Intent("crown", None, "Eger", "run", 10.0, None),
        plan=Plan(
            shape_strategy="template",
            suggested_shape="crown",
            suggestion_candidates=["crown", "triangle", "diamond"],
        ),
        shape=Shape("crown", shape_library.crown()[1], True),
        route_draft=RouteDraft(
            47.0, 19.0, 1_000.0, 0.0, 0.0, 0.0, 0.8, points, True, 10.0
        ),
        snapped=SnappedRoute(points, 10_000.0, snapped=True),
        validation=Validation(0.44, 1.0, 0.9, 0.37, on_roads=True),
        errors=["snap: stale primary failure"],
    )
    fidelity_by_shape = {"triangle": 0.58, "diamond": 0.76}

    def shape_node(current):
        name = current.intent.shape
        generated = shape_library.get_shape(name)
        assert generated is not None
        current.shape = Shape(name, generated[1], generated[2])

    def placement_node(current):
        current.route_draft = RouteDraft(
            47.0, 19.0, 1_000.0, 0.0, 0.0, 0.0, 0.8, points, True, 10.0
        )

    def snap_node(current):
        current.snapped = SnappedRoute(points, 10_000.0, snapped=True)
        current.errors = []

    def validation_node(current):
        fidelity = fidelity_by_shape[current.shape.name]
        current.validation = Validation(
            score=0.8 if fidelity >= 0.7 else 0.6,
            closure=1.0,
            distance_fit=0.9,
            shape_fidelity=fidelity,
            on_roads=True,
        )

    nodes = {
        "shape": Node(shape_node),
        "placement": Node(placement_node),
        "snap": Node(snap_node),
        "validation": Node(validation_node),
    }

    Orchestrator(nodes={})._evaluate_suggestion_candidates(state, nodes)

    assert state.shape.name == "diamond"
    assert state.intent.shape == "diamond"
    assert state.plan.suggested_shape == "diamond"
    assert state.validation.shape_fidelity == pytest.approx(0.76)
    assert state.errors == []
    assert {
        entry["shape"]
        for entry in state.history
        if entry.get("agent") == "suggestion_search"
    } == {"triangle", "diamond"}


def test_failed_explicit_shape_is_replaced_only_by_a_measured_passing_route():
    class Node:
        def __init__(self, operation):
            self.operation = operation

        def run(self, state):
            self.operation(state)
            return state

    points = [(47.0, 19.0), (47.01, 19.01), (47.0, 19.0)]
    state = WorkflowState(
        prompt="a cat run in Tatabánya",
        requested_shape="cat",
        intent=Intent("cat", None, "Tatabánya", "run", 10.0, None),
        plan=Plan(
            shape_strategy="template",
            fallback_candidates=["triangle", "diamond", "arrow"],
        ),
        shape=Shape("cat", shape_library.cat()[1], True),
        route_draft=RouteDraft(
            47.0, 19.0, 1_000.0, 0.0, 0.0, 0.0, 0.8, points, True, 10.0
        ),
        snapped=SnappedRoute(points, 10_000.0, snapped=True),
        validation=Validation(
            0.48,
            1.0,
            0.9,
            0.42,
            on_roads=True,
            coverage_similarity=0.45,
            turning_similarity=0.40,
            length_similarity=0.50,
            extent_similarity=0.60,
            route_length_ratio=1.8,
        ),
        candidate_count=7,
    )
    fidelity_by_shape = {"triangle": 0.62, "diamond": 0.82}

    def shape_node(current):
        generated = shape_library.get_shape(current.intent.shape)
        assert generated is not None
        current.shape = Shape(generated[0], generated[1], generated[2])

    def placement_node(current):
        if current.route_draft is None:
            current.route_draft = RouteDraft(
                47.0, 19.0, 1_000.0, 0.0, 0.0, 0.0, 0.8, points, True, 10.0
            )
        current.route_draft.waypoints = points

    def snap_node(current):
        current.candidate_count += 1
        current.snapped = SnappedRoute(points, 10_000.0, snapped=True)

    def validation_node(current):
        fidelity = fidelity_by_shape[current.shape.name]
        current.validation = Validation(
            score=0.84 if fidelity >= 0.7 else 0.66,
            closure=1.0,
            distance_fit=0.95,
            shape_fidelity=fidelity,
            on_roads=True,
            spatial_similarity=fidelity,
            coverage_similarity=fidelity,
            turning_similarity=fidelity,
            length_similarity=fidelity,
            extent_similarity=fidelity,
            route_length_ratio=1.0,
        )

    nodes = {
        "shape": Node(shape_node),
        "placement": Node(placement_node),
        "snap": Node(snap_node),
        "validation": Node(validation_node),
    }

    Orchestrator(nodes={})._evaluate_fallback_candidates(state, nodes)

    assert state.shape.name == "diamond"
    assert state.intent.shape == "diamond"
    assert state.fit_decision is not None
    assert state.fit_decision.substituted is True
    assert state.fit_decision.requested_shape == "cat"
    assert state.fit_decision.selected_shape == "diamond"
    assert state.fit_decision.candidates_tested == ["triangle", "diamond"]
    assert state.validation.shape_fidelity == pytest.approx(0.82)
    assert state.candidate_count > 7


def test_validation_cap_preserves_fidelity_ordering(monkeypatch):
    points = [(47.0, 19.0), (47.01, 19.01), (47.0, 19.0)]

    def validate_with_fidelity(fidelity):
        monkeypatch.setattr(
            shape_similarity,
            "similarity_diagnostics_between_routes",
            lambda *_args, **_kwargs: shape_similarity.SimilarityDiagnostics(
                fidelity=fidelity,
                spatial_similarity=fidelity,
                coverage_similarity=fidelity,
                turning_similarity=fidelity,
                length_similarity=fidelity,
                extent_similarity=fidelity,
                route_length_ratio=1.0,
                mean_deviation_ratio=0.0,
            ),
        )
        state = WorkflowState(
            prompt="shape route",
            intent=Intent("circle", None, "Tatabánya", "run", 10.0, None),
            shape=Shape("circle", shape_library.circle()[1], True),
            route_draft=RouteDraft(
                47.0,
                19.0,
                1_000.0,
                0.0,
                0.0,
                0.0,
                0.8,
                points,
                True,
                10.0,
            ),
            snapped=SnappedRoute(points, 10_000.0, snapped=True),
        )
        ValidationAgent().run(state)
        assert state.validation is not None
        return state.validation.score

    low = validate_with_fidelity(0.363)
    promising = validate_with_fidelity(0.616)

    assert promising > low + 0.1
    assert promising < 0.72


def test_known_template_planning_is_local_and_uses_stable_city_offset(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("known template planning must not call an LLM")

    monkeypatch.setattr(
        "gps_art_wizzard.agents.planning_agent.try_complete",
        fail_if_called,
    )
    budapest = WorkflowState(
        prompt="heart in Budapest",
        intent=Intent("heart", None, "Budapest", "run", 8.0, None),
    )
    tatabanya = WorkflowState(
        prompt="heart in Tatabánya",
        intent=Intent("heart", None, "Tatabánya", "run", 8.0, None),
    )

    PlanningAgent().run(budapest)
    PlanningAgent().run(tatabanya)

    assert budapest.plan is not None
    assert budapest.plan.rotation_hint_deg == 0.0
    assert budapest.plan.lat_offset_m == 0.0
    assert budapest.plan.lon_offset_m == 1_500.0
    assert tatabanya.plan is not None
    assert tatabanya.plan.lat_offset_m == 0.0
    assert tatabanya.plan.lon_offset_m == -1_500.0


def test_template_keyword_alias_skips_llm_planning(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("template keyword aliases must not call an LLM planner")

    monkeypatch.setattr(
        "gps_art_wizzard.agents.planning_agent.try_complete",
        fail_if_called,
    )
    state = WorkflowState(
        prompt="a dog run in Győr, 10 km",
        intent=Intent("a dog", None, "Győr", "run", 10.0, None),
    )

    PlanningAgent().run(state)

    assert state.plan is not None
    assert state.plan.shape_strategy == "template"
    assert state.plan.lat_offset_m == 1_500.0


def test_llm_shape_validation_drops_bad_points_and_bounds_payload():
    paths = _validated_paths(
        [
            [[0, 0], [0, 0], [1, 1], [float("nan"), 2], [2_000_000, 1]],
            [["bad", 0]],
        ]
    )
    assert paths == [[(0.0, 0.0), (1.0, 1.0)]]
    with pytest.raises(ValueError, match="no drawable"):
        _validated_paths([[[0, 0]], [["bad", 1]]])


def test_preview_sampler_never_exceeds_limit_and_keeps_endpoints():
    points = list(range(1_000))
    sampled = _even_sample(points, 500)
    assert len(sampled) == 500
    assert sampled[0] == 0
    assert sampled[-1] == 999


def test_export_is_stateless_for_a_valid_road_route(monkeypatch):
    monkeypatch.delenv("EXPORT_DIR", raising=False)
    points = [(47.0, 19.0), (47.001, 19.001), (47.0, 19.0)]
    state = WorkflowState(
        prompt="heart route",
        intent=Intent("heart", None, "Budapest", "run", 1.0, None),
        snapped=SnappedRoute(points, geo.path_distance_m(points), snapped=True),
        validation=Validation(
            score=0.9,
            closure=1.0,
            distance_fit=0.8,
            shape_fidelity=0.9,
            on_roads=True,
        ),
    )
    ExportAgent().run(state)
    assert state.export is not None
    assert "<gpx" in state.export.gpx
    assert state.export.file_paths == {}


def test_export_retains_route_that_misses_recommended_quality_targets():
    points = [(47.0, 19.0), (47.001, 19.001), (47.0, 19.0)]
    state = WorkflowState(
        prompt="heart route",
        intent=Intent("heart", None, "Budapest", "run", 8.0, None),
        snapped=SnappedRoute(points, 10_650.0, snapped=True),
        validation=Validation(
            score=0.66,
            closure=1.0,
            distance_fit=0.37,
            shape_fidelity=0.75,
            on_roads=True,
        ),
    )

    ExportAgent().run(state)

    assert state.export is not None
    assert "<gpx" in state.export.gpx
    assert any("recommended minimum" in error for error in state.errors)


def test_validation_retains_every_fully_routed_candidate_for_the_editor():
    ideal = [(47.0, 19.0), (47.001, 19.001), (47.0, 19.0)]
    state = WorkflowState(
        prompt="heart route",
        intent=Intent("heart", None, "Budapest", "run", 1.0, None),
        shape=Shape("heart", shape_library.heart()[1], True),
        route_draft=RouteDraft(
            47.0,
            19.0,
            1_000.0,
            0.0,
            0.0,
            0.0,
            0.8,
            ideal,
            True,
            1.0,
        ),
        snapped=SnappedRoute(ideal, geo.path_distance_m(ideal), snapped=True),
    )

    ValidationAgent().run(state)
    state.route_draft.rotation_deg = 90.0
    ValidationAgent().run(state)

    assert len(state.candidates) == 2
    assert state.candidates[0].rotation_deg == 0.0
    assert state.candidates[1].rotation_deg == 90.0
    response = _state_to_response(state)
    assert len(response["candidates"]) == 2
    assert all(candidate["points_preview"] for candidate in response["candidates"])


def test_edit_route_reroutes_control_points_and_always_builds_gpx(monkeypatch):
    routed = [
        (47.0, 19.0),
        (47.0005, 19.0007),
        (47.001, 19.001),
    ]

    def fake_snap(waypoints, *, sport, closed):
        assert sport == "run"
        assert closed is False
        assert len(waypoints) == 3
        return routed, geo.path_distance_m(routed), True

    monkeypatch.setattr(ors_client, "snap_route", fake_snap)
    response = edit_route(
        EditedRouteRequest(
            control_points=[[lat, lon] for lat, lon in routed],
            reference_points=[[lat, lon] for lat, lon in routed],
            sport="run",
            closed=False,
            target_distance_km=0.2,
            name="Edited route",
        )
    )

    assert response["snapped"] is True
    assert response["points_preview"] == [[lat, lon] for lat, lon in routed]
    assert "<gpx" in response["gpx"]
    assert "Edited route" in response["gpx"]


def test_server_side_export_sanitises_user_derived_filename(tmp_path):
    paths = gpx_writer.write_files(
        [(47.0, 19.0), (47.001, 19.001)],
        name="../../outside route",
        sport="run",
        total_distance_m=150.0,
        out_dir=str(tmp_path),
    )
    assert paths
    assert all(Path(path).resolve().parent == tmp_path.resolve() for path in paths.values())


def test_unavailable_model_provider_is_probed_only_once(monkeypatch):
    class UnavailableProvider:
        name = "unavailable-test"

        def __init__(self):
            self.probes = 0

        def is_available(self):
            self.probes += 1
            return False

    provider = UnavailableProvider()
    monkeypatch.setattr(llm_factory, "available_providers", lambda: (provider,))
    llm_factory.reset_sticky()
    try:
        assert llm_factory.try_complete(lambda: "fallback") == "fallback"
        assert llm_factory.try_complete(lambda: "fallback") == "fallback"
        assert provider.probes == 1
    finally:
        llm_factory.reset_sticky()


def test_explicit_model_provider_is_prioritised_without_losing_fallbacks():
    config = llm_factory.LLMConfig(
        provider="anthropic",
        fallback_order=["opencode", "anthropic", "openai", "opencode"],
    )
    assert llm_factory._provider_order(config) == [
        "anthropic",
        "opencode",
        "openai",
    ]


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t"])
def test_orchestrator_rejects_blank_prompt(prompt):
    with pytest.raises(ValueError, match="empty"):
        Orchestrator(nodes={}).run(prompt)
