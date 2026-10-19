"""The accuracy report must expose regressions and retain invalid comparisons."""
from __future__ import annotations

import copy

import pytest

from gps_art_wizzard.tools import geo, shape_similarity
from scripts.render_generation_comparison import compare_pair, line_error_m, measurement


def record(shift_m=0):
    ideal = [geo.unit_to_latlon(x, y, 46.25, 20.14, 1)
             for x, y in [(0, 0), (300, 0), (150, 300), (0, 0)]]
    points = [geo.unit_to_latlon(x + shift_m, y, 46.25, 20.14, 1)
              for x, y in [(0, 0), (300, 0), (150, 300), (0, 0)]]
    fidelity = shape_similarity.similarity_diagnostics_between_routes(ideal, points).fidelity
    return {"case": {"id": "test", "distance_km": 1}, "points": points, "ideal_points": ideal,
            "validation": {"shape_fidelity": fidelity, "actual_distance_km": 0.9},
            "road_connected": True, "provider_geometry_preserved": True, "elapsed_seconds": 10,
            "quality": {"passed": False, "failed_gates": ["shape_fidelity"]},
            "workflow": {"routing_failures": {}, "degraded_reasons": []},
            "ors_engines": [{"version": "test", "graph_date": "fixed"}]}


def test_report_exposes_lower_fidelity_and_distinguishes_percentage_points():
    original, current = record(), record(80)
    pair = compare_pair(original["case"], original, current)
    assert pair["clean_comparison"]
    assert pair["fidelity_delta_pp"] < -10
    assert pair["original"]["shape_fidelity"] > pair["current"]["shape_fidelity"]
    assert pair["outline_rms_delta_m"] > 10
    assert pair["original"]["distance_error_pct"] == pytest.approx(10)


@pytest.mark.parametrize("problem", ["provider_failure", "engine_change", "score_mismatch", "no_route"])
def test_invalid_pairs_remain_visible_but_cannot_support_an_accuracy_claim(problem):
    original = record()
    current = copy.deepcopy(original)
    if problem == "provider_failure":
        current["workflow"]["routing_failures"] = {"directions.http_429": 1}
    elif problem == "engine_change":
        current["ors_engines"][0]["graph_date"] = "changed"
    elif problem == "score_mismatch":
        current["validation"]["shape_fidelity"] = 0.1
    else:
        current["road_connected"] = False
    pair = compare_pair(original["case"], original, current)
    assert not pair["clean_comparison"]
    assert pair["original"] and pair["current"]


def test_unrouted_guide_never_appears_as_a_perfect_accuracy_result():
    row = record()
    row["road_connected"] = False
    row["quality"]["passed"] = True  # even inconsistent input must fail closed
    result = measurement(row)
    assert result["shape_fidelity"] is None
    assert not result["quality_passed"]


def test_physical_error_uses_metres_and_retains_the_target_position():
    reference = [geo.unit_to_latlon(x, 0, 46.25, 20.14, 1) for x in (0, 1000)]
    shifted = [geo.unit_to_latlon(x, 100, 46.25, 20.14, 1) for x in (0, 1000)]
    assert line_error_m(reference, reference) == pytest.approx(0, abs=1e-9)
    assert line_error_m(reference, shifted) == pytest.approx(100, abs=1e-6)
