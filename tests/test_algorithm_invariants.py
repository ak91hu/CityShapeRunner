"""Regression contracts for the deterministic route-planning algorithms.

These tests deliberately assert mathematical and product-safety invariants
instead of duplicating implementation steps.  They should remain useful when
an algorithm is refactored, while still catching behaviour changes that would
alter route geometry, candidate selection, or export eligibility.
"""

from __future__ import annotations

import copy
import math
from dataclasses import replace

import numpy as np
import pytest

from gps_art_wizzard.agents.preflight_agent import PreflightAgent
from gps_art_wizzard.agents.refinement_agent import RefinementAgent
from gps_art_wizzard.orchestrator import Orchestrator
from gps_art_wizzard.quality import quality_bottleneck, quality_gate_report
from gps_art_wizzard.state import RouteDraft, Validation, WorkflowState
from gps_art_wizzard.tools import geo


def _good_validation(**overrides: object) -> Validation:
    values: dict[str, object] = {
        "score": 0.95,
        "closure": 0.95,
        "distance_fit": 0.95,
        "shape_fidelity": 0.95,
        "on_roads": True,
        "spatial_similarity": 0.95,
        "coverage_similarity": 0.95,
        "turning_similarity": 0.95,
        "landmark_similarity": 0.95,
        "reversal_similarity": 0.95,
        "length_similarity": 0.95,
        "extent_similarity": 0.95,
        "route_length_ratio": 1.0,
    }
    values.update(overrides)
    return Validation(**values)  # type: ignore[arg-type]


def _draft(
    *,
    rotation_deg: float = 0.0,
    scale_m: float = 1_000.0,
    lat_offset_m: float = 0.0,
    lon_offset_m: float = 0.0,
    simplify_tolerance: float = 0.8,
) -> RouteDraft:
    return RouteDraft(
        center_lat=47.5,
        center_lon=19.05,
        scale_m=scale_m,
        rotation_deg=rotation_deg,
        lat_offset_m=lat_offset_m,
        lon_offset_m=lon_offset_m,
        simplify_tolerance=simplify_tolerance,
        waypoints=[(47.5, 19.05), (47.501, 19.051)],
        closed=False,
    )


def test_geographic_distance_is_symmetric_additive_and_antimeridian_safe() -> None:
    west_of_dateline = (0.0, 179.9)
    east_of_dateline = (0.0, -179.9)
    next_point = (0.0, -179.8)

    crossing = geo.haversine(*west_of_dateline, *east_of_dateline)

    assert crossing == pytest.approx(
        geo.haversine(*east_of_dateline, *west_of_dateline), rel=1e-12
    )
    assert crossing == pytest.approx(22_239.0, rel=0.002)
    assert geo.path_distance_m([west_of_dateline, east_of_dateline, next_point]) == pytest.approx(
        crossing + geo.haversine(*east_of_dateline, *next_point), rel=1e-12
    )
    assert geo.path_distance_m([]) == 0.0
    assert geo.path_distance_m([west_of_dateline]) == 0.0


@pytest.mark.parametrize(
    "coordinates",
    [
        (math.nan, 0.0, 0.0, 0.0),
        (0.0, math.inf, 0.0, 0.0),
        (-90.1, 0.0, 0.0, 0.0),
        (0.0, 0.0, 90.1, 0.0),
    ],
)
def test_geographic_distance_rejects_non_finite_or_invalid_latitudes(
    coordinates: tuple[float, float, float, float],
) -> None:
    with pytest.raises(ValueError):
        geo.haversine(*coordinates)


def test_shape_normalisation_ignores_positive_scale_and_translation_without_mutation() -> None:
    original = [
        [(-2.0, -1.0), (0.0, 2.0), (3.0, -1.0)],
        [(4.0, 0.0), (5.0, 1.0)],
    ]
    original_copy = copy.deepcopy(original)
    transformed = [
        [(x * 7.5 + 123.0, y * 7.5 - 48.0) for x, y in path]
        for path in original
    ]

    normalised = geo.normalize_shape(original)
    transformed_normalised = geo.normalize_shape(transformed)

    assert original == original_copy
    assert len(normalised) == len(transformed_normalised)
    for first, second in zip(normalised, transformed_normalised, strict=True):
        assert np.asarray(first) == pytest.approx(np.asarray(second), abs=1e-12)
    all_points = np.concatenate([np.asarray(path) for path in normalised])
    extents = np.ptp(all_points, axis=0)
    assert float(extents.max()) == pytest.approx(1.0, abs=1e-12)


def test_rigid_shape_transforms_preserve_drawn_length_and_are_reversible() -> None:
    paths = [[(-0.5, 0.0), (0.0, 0.75), (0.5, 0.0)], [(0.2, -0.1), (0.4, -0.4)]]
    perimeter = geo.unit_perimeter(paths)

    moved = geo.offset_shape(geo.rotate_shape(paths, math.radians(137.0)), 12.5, -8.25)
    restored = geo.rotate_shape(
        geo.offset_shape(moved, -12.5, 8.25),
        math.radians(-137.0),
    )

    assert geo.unit_perimeter(moved) == pytest.approx(perimeter, rel=1e-12)
    for expected, actual in zip(paths, restored, strict=True):
        assert np.asarray(actual) == pytest.approx(np.asarray(expected), abs=1e-12)


def test_densification_preserves_endpoints_and_length_while_bounding_every_step() -> None:
    path = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.75), (1.3, 1.15)]
    dense = geo.densify_path(path, max_step=0.13)
    steps = [
        math.hypot(x1 - x0, y1 - y0)
        for (x0, y0), (x1, y1) in zip(dense, dense[1:], strict=False)
    ]

    assert dense[0] == path[0]
    assert dense[-1] == path[-1]
    assert max(steps) <= 0.13 + 1e-12
    assert geo.unit_path_length(dense) == pytest.approx(geo.unit_path_length(path), rel=1e-12)


@pytest.mark.parametrize("center_lat", [-70.0, -47.5, 0.0, 47.5, 70.0])
def test_projection_round_trip_is_stable_across_city_latitudes(center_lat: float) -> None:
    expected = (0.73, -0.41)
    lat, lon = geo.unit_to_latlon(*expected, center_lat, 19.0, 12_500.0)
    actual = geo.latlon_to_unit(lat, lon, center_lat, 19.0, 12_500.0)

    assert actual == pytest.approx(expected, abs=1e-12)


def test_bounding_box_heading_follows_the_longer_metric_axis() -> None:
    east_west = geo.bbox_long_axis_heading((47.49, 47.51, 18.8, 19.3))
    north_south = geo.bbox_long_axis_heading((47.0, 48.0, 19.0, 19.02))

    assert east_west == pytest.approx(90.0, abs=0.2)
    assert min(north_south, 360.0 - north_south) == pytest.approx(0.0, abs=0.2)


def test_every_numeric_quality_gate_is_independent_and_boundary_inclusive() -> None:
    baseline = _good_validation()
    thresholds = quality_gate_report(baseline, closed=True)["thresholds"]
    fields = {
        "score": ("overall_score", thresholds["overall_score"]),
        "shape_fidelity": ("shape_fidelity", thresholds["shape"]),
        "spatial_similarity": ("spatial_similarity", thresholds["shape"]),
        "coverage_similarity": ("coverage_similarity", thresholds["shape"]),
        "turning_similarity": ("turning_similarity", thresholds["shape"]),
        "landmark_similarity": ("landmark_similarity", thresholds["shape"]),
        "reversal_similarity": ("reversal_similarity", thresholds["shape"]),
        "length_similarity": ("length_similarity", thresholds["shape"]),
        "extent_similarity": ("extent_similarity", thresholds["shape"]),
        "distance_fit": ("distance_fit", thresholds["usability"]),
        "closure": ("closure", thresholds["usability"]),
    }

    for field, (gate_key, minimum) in fields.items():
        at_boundary = quality_gate_report(
            replace(baseline, **{field: minimum}),
            closed=True,
        )
        just_below = quality_gate_report(
            replace(baseline, **{field: minimum - 1e-6}),
            closed=True,
        )

        assert at_boundary["passed"], field
        assert gate_key not in at_boundary["failed_gates"], field
        assert not just_below["passed"], field
        assert just_below["failed_gates"] == [gate_key], field


def test_open_route_ignores_closure_but_shape_identity_and_roads_remain_hard_gates() -> None:
    open_validation = _good_validation(closure=0.0)

    open_report = quality_gate_report(
        open_validation,
        closed=False,
        candidate_shape="Heart",
        selected_shape="heart",
    )
    closed_report = quality_gate_report(
        open_validation,
        closed=True,
        candidate_shape="Heart",
        selected_shape="heart",
    )
    wrong_shape = quality_gate_report(
        open_validation,
        closed=False,
        candidate_shape="star",
        selected_shape="heart",
    )
    off_roads = quality_gate_report(
        replace(open_validation, on_roads=False),
        closed=False,
    )

    assert open_report["passed"]
    assert open_report["required_count"] + 1 == closed_report["required_count"]
    assert closed_report["failed_gates"] == ["closure"]
    assert wrong_shape["failed_gates"] == ["selected_shape"]
    assert off_roads["failed_gates"] == ["road_network"]


def test_quality_bottleneck_and_candidate_order_reward_balanced_safe_routes() -> None:
    lopsided = _good_validation(distance_fit=0.61, score=0.97)
    balanced = _good_validation(
        score=0.84,
        closure=0.84,
        distance_fit=0.84,
        shape_fidelity=0.84,
        spatial_similarity=0.84,
        coverage_similarity=0.84,
        turning_similarity=0.84,
        landmark_similarity=0.84,
        reversal_similarity=0.84,
        length_similarity=0.84,
        extent_similarity=0.84,
    )
    unsafe = replace(_good_validation(score=1.0), on_roads=False)

    assert quality_bottleneck(balanced, closed=True) > quality_bottleneck(
        lopsided, closed=True
    )
    assert quality_bottleneck(unsafe, closed=True) == 0.0
    assert Orchestrator._candidate_is_better(balanced, lopsided)
    assert Orchestrator._candidate_is_better(balanced, unsafe)
    assert not Orchestrator._candidate_is_better(unsafe, balanced)


def test_preflight_diversity_is_symmetric_and_wraps_rotation_at_north() -> None:
    west_of_north = _draft(rotation_deg=350.0)
    east_of_north = _draft(rotation_deg=10.0)
    far_alternative = _draft(
        rotation_deg=170.0,
        scale_m=2_000.0,
        lat_offset_m=10_000.0,
        lon_offset_m=-10_000.0,
    )

    wrapped = PreflightAgent._draft_diversity(west_of_north, east_of_north)

    assert PreflightAgent._draft_diversity(west_of_north, west_of_north) == 0.0
    assert wrapped == pytest.approx(0.3 * (20.0 / 90.0), abs=1e-12)
    assert wrapped == pytest.approx(
        PreflightAgent._draft_diversity(east_of_north, west_of_north),
        abs=1e-12,
    )
    assert PreflightAgent._draft_diversity(west_of_north, far_alternative) == pytest.approx(1.0)


def test_city_grid_offsets_are_deterministic_unique_and_cover_every_direction() -> None:
    draft = _draft(lat_offset_m=140.0, lon_offset_m=-220.0)
    bbox = (47.43, 47.58, 18.93, 19.23)

    first = PreflightAgent._city_grid_offsets(draft, bbox)
    second = PreflightAgent._city_grid_offsets(draft, bbox)

    assert first == second
    assert first[0] == (0.0, 0.0)
    assert len(first) == len(set(first))
    assert 9 <= len(first) <= 10
    latitudes = [lat for lat, _ in first[1:]]
    longitudes = [lon for _, lon in first[1:]]
    assert min(latitudes) < 0.0 < max(latitudes)
    assert min(longitudes) < 0.0 < max(longitudes)


def test_refinement_signatures_canonicalise_equivalent_rotations_and_audit_entries() -> None:
    agent = RefinementAgent()
    north = _draft(rotation_deg=0.0)
    full_turn = _draft(rotation_deg=360.0)
    state = WorkflowState(
        prompt="heart route",
        history=[
            {
                "agent": "refinement",
                "scale_m": full_turn.scale_m,
                "rotation_deg": 720.0,
                "lat_offset_m": full_turn.lat_offset_m,
                "lon_offset_m": full_turn.lon_offset_m,
                "simplify_tolerance": full_turn.simplify_tolerance,
            }
        ],
    )

    north_signature = agent._draft_signature(north)

    assert north_signature == agent._draft_signature(full_turn)
    assert agent._tested_candidate_signatures(state) == {north_signature}
