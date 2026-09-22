"""Closed-route phase alignment must distinguish repeated visits to a crossing."""
import numpy as np
import pytest

from gps_art_wizzard.tools import geo, shape_similarity


def _route(points):
    return [geo.unit_to_latlon(x, y, 47, 19, 1) for x, y in points]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("start", [1, 4, 6])
def test_same_crossing_route_keeps_quality_after_start_or_direction_change(start, reverse):
    reference = _route([(0, 0), (300, 0), (300, 300), (0, 300), (0, 0),
                        (-500, 0), (-500, -200), (0, -200), (0, 0)])
    core = reference[:-1]
    shifted = core[start:] + core[:start]
    candidate = shifted + [shifted[0]]
    if reverse:
        candidate.reverse()
    measured = shape_similarity.similarity_diagnostics_between_routes(reference, candidate)
    assert measured.fidelity > 0.98
    assert measured.turning_similarity > 0.96
    assert measured.spatial_similarity > 0.97


def test_alignment_does_not_reorder_loops_with_identical_point_coverage():
    loops = [
        [(0, 0), (300, 0), (300, 300), (0, 300), (0, 0)],
        [(0, 0), (-400, 0), (-400, 200), (-100, 200), (0, 0)],
        [(0, 0), (-300, -200), (0, -500), (200, -200), (0, 0)],
    ]
    reference = _route([(0, 0)] + [p for i in (0, 1, 2) for p in loops[i][1:]])
    reordered = _route([(0, 0)] + [p for i in (0, 2, 1) for p in loops[i][1:]])
    measured = shape_similarity.similarity_diagnostics_between_routes(reference, reordered)
    assert measured.coverage_similarity > 0.95
    assert measured.length_similarity > 0.98
    assert measured.turning_similarity < 0.4
    assert measured.fidelity < 0.7


def test_phase_variants_are_bounded_and_never_change_street_vertices():
    reference = np.asarray([(0, 0), (1, 0), (1, 1), (0, 0), (-1, 0), (-1, -1), (0, 0)])
    candidate = np.vstack((np.roll(reference[:-1], 3, axis=0), reference[3]))
    before = candidate.copy()
    variants = shape_similarity._candidate_orientations(reference, candidate)
    assert 2 <= len(variants) <= 4
    assert np.array_equal(candidate, before)
    for variant in variants:
        assert np.array_equal(variant[0], variant[-1])
        assert sorted(map(tuple, variant[:-1])) == sorted(map(tuple, candidate[:-1]))
