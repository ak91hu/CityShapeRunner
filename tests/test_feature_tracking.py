"""Semantic geometry survives shared transforms and drives targeted repair."""
from copy import deepcopy

import pytest

from gps_art_wizzard.agents.placement_agent import PlacementAgent
from gps_art_wizzard.state import RouteDraft, Shape, SnappedRoute, Validation, WorkflowState
from gps_art_wizzard.tools import geo
from gps_art_wizzard.tools.feature_tracking import (
    feature_repair_guides,
    measure_features,
    normalize_with_features,
    projected_features,
    propose_feature_repair,
)


def feature_state():
    path = [(0, 0), (1, 0), (1, 1), (0.5, 1.5), (0, 1), (0, 0)]
    shape = Shape("house", [path], True, feature_paths={"roof": [path[2:5]]})
    normalize_with_features(shape)
    draft = RouteDraft(47.5, 19, 600, 35, 80, -20, 0.8, [], True)
    draft.waypoints = PlacementAgent().project(shape, draft)
    return WorkflowState("house", shape=shape, route_draft=draft,
                         snapped=SnappedRoute(draft.waypoints, geo.path_distance_m(draft.waypoints), True))


def test_feature_normalization_and_projection_share_the_whole_shape_frame():
    state = feature_state()
    for a, b in zip(state.shape.feature_paths["roof"][0], state.shape.paths[0][2:5], strict=True):
        assert a == pytest.approx(b)
    for a, b in zip(projected_features(state)["roof"][0], state.route_draft.waypoints[2:5], strict=True):
        assert a == pytest.approx(b)
    state.route_draft.anchored_start = (47.7, 19.2)
    state.route_draft.waypoints = PlacementAgent().project(state.shape, state.route_draft)
    actual = projected_features(state)["roof"][0]
    for a, b in zip(actual, state.route_draft.waypoints[2:5], strict=True):
        assert a == pytest.approx(b)


def test_removed_roof_tip_is_measured_as_lost_even_when_other_edges_match():
    state = feature_state()
    intact, intact_score = measure_features(state)
    assert intact_score == pytest.approx(1)
    state.snapped.points = state.snapped.points[:3] + state.snapped.points[4:]
    measurements, score = measure_features(state)
    assert score < 0.65
    assert not measurements[0]["preserved"]
    assert measurements[0]["max_deviation_m"] > 100


def test_repair_keeps_ideal_reference_and_endpoints_and_is_bounded():
    state = feature_state()
    state.snapped.points = state.snapped.points[:3] + state.snapped.points[4:]
    rows, score = measure_features(state)
    state.validation = Validation(0.5, 1, 1, 0.5, feature_measurements=rows, feature_preservation=score)
    original = deepcopy(state.route_draft.waypoints)
    assert propose_feature_repair(state)
    first = feature_repair_guides(state)
    assert len(first) <= 24
    assert first[0] == original[0] and first[-1] == original[-1]
    assert original[3] in first
    assert propose_feature_repair(state)
    second = feature_repair_guides(state)
    assert second != first
    assert state.route_draft.waypoints == original
    assert not propose_feature_repair(state)


def test_unrouted_geometry_cannot_claim_feature_preservation():
    state = feature_state()
    state.snapped.snapped = False
    assert measure_features(state) == ([], None)
