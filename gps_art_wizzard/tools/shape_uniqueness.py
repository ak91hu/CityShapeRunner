"""Rotation-independent duplicate detection for routed shape templates.

The comparison uses the same deterministic multi-stroke stitching that turns a
template into one GPS route. Contours are sampled uniformly by travelled
distance, centred, and scale-normalised before an optimal planar rotation is
fitted. Closed outlines also ignore their authored starting vertex and every
route may be traversed in either direction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

import numpy as np

from . import geo, shape_library, shape_similarity

DUPLICATE_DISTANCE_THRESHOLD = 0.02


@dataclass(frozen=True)
class ShapePairDistance:
    """One scale/rotation/traversal-invariant catalog comparison."""

    first: str
    second: str
    distance: float


@dataclass(frozen=True)
class _PreparedContour:
    points: np.ndarray
    closed: bool


def _prepare_contour(paths: list[geo.Path], sample_count: int) -> _PreparedContour:
    if sample_count < 8:
        raise ValueError("sample_count must be at least eight")

    route = np.asarray(geo.stitch_paths(geo.normalize_shape(paths)), dtype=float)
    if route.ndim != 2 or route.shape[1:] != (2,) or len(route) < 2:
        raise ValueError("a comparable shape needs at least two two-dimensional points")
    if not np.isfinite(route).all():
        raise ValueError("shape coordinates must be finite")

    closed = len(route) >= 3 and float(np.linalg.norm(route[0] - route[-1])) <= 1e-7
    if closed:
        sampled = shape_similarity.resample(route, sample_count + 1)[:-1]
    else:
        sampled = shape_similarity.resample(route, sample_count)

    sampled -= sampled.mean(axis=0)
    rms_radius = math.sqrt(float(np.mean(np.sum(np.square(sampled), axis=1))))
    if rms_radius <= 1e-9:
        raise ValueError("a comparable shape must have a non-zero extent")
    return _PreparedContour(sampled / rms_radius, closed)


def _best_rotation_correlation(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    cyclic: bool,
) -> float:
    reference_complex = reference[:, 0] + 1j * reference[:, 1]
    best = 0.0
    for direction in (candidate, candidate[::-1]):
        candidate_complex = direction[:, 0] + 1j * direction[:, 1]
        if cyclic:
            alignments = np.stack(
                [np.roll(candidate_complex, shift) for shift in range(len(candidate_complex))]
            )
        else:
            alignments = candidate_complex[np.newaxis, :]
        correlations = np.abs(
            np.mean(np.conjugate(alignments) * reference_complex[np.newaxis, :], axis=1)
        )
        best = max(best, float(np.max(correlations)))
    return min(1.0, best)


def _prepared_distance(first: _PreparedContour, second: _PreparedContour) -> float:
    correlation = _best_rotation_correlation(
        first.points,
        second.points,
        cyclic=first.closed and second.closed,
    )
    # Both point sets have unit RMS radius. After the best rigid rotation,
    # mean squared error is therefore 2 - 2 * normalized correlation.
    return math.sqrt(max(0.0, 2.0 - 2.0 * correlation))


def contour_distance(
    first_paths: list[geo.Path],
    second_paths: list[geo.Path],
    *,
    sample_count: int = 96,
) -> float:
    """Return a near-zero distance under safe placement transforms.

    Translation, uniform scale, rotation, traversal direction, and the starting
    point of a closed loop do not affect duplicate classification. A seam that
    falls between two arc-length samples can leave a small numerical residual.
    Reflection deliberately remains distinct because the placement pipeline
    does not mirror templates.
    """

    first = _prepare_contour(first_paths, sample_count)
    second = _prepare_contour(second_paths, sample_count)
    return _prepared_distance(first, second)


def template_distance(first_name: str, second_name: str, *, sample_count: int = 96) -> float:
    """Compare the map-bound polylines produced by two registered templates."""

    first = shape_library.get_shape(first_name)
    second = shape_library.get_shape(second_name)
    if first is None:
        raise KeyError(f"unknown shape: {first_name}")
    if second is None:
        raise KeyError(f"unknown shape: {second_name}")
    return contour_distance(first[1], second[1], sample_count=sample_count)


@lru_cache(maxsize=8)
def _cached_catalog_pair_distances(sample_count: int) -> tuple[ShapePairDistance, ...]:
    prepared = {
        name: _prepare_contour(shape_library.SHAPES[name]()[1], sample_count)
        for name in sorted(shape_library.SHAPES)
    }
    distances = [
        ShapePairDistance(first, second, _prepared_distance(prepared[first], prepared[second]))
        for first, second in combinations(prepared, 2)
    ]
    return tuple(sorted(distances, key=lambda item: (item.distance, item.first, item.second)))


def catalog_pair_distances(*, sample_count: int = 96) -> list[ShapePairDistance]:
    """Measure every unique pair in the registered template catalog.

    The immutable matrix is cached by sample count; callers receive a fresh
    list so one audit cannot mutate a later audit's ordering or contents.
    """

    return list(_cached_catalog_pair_distances(sample_count))


def find_catalog_duplicates(
    *,
    max_distance: float = DUPLICATE_DISTANCE_THRESHOLD,
    sample_count: int = 96,
) -> list[ShapePairDistance]:
    """Return catalog pairs too similar to be independent GPS-art targets."""

    if not math.isfinite(max_distance) or max_distance < 0.0:
        raise ValueError("max_distance must be a non-negative finite number")
    return [
        pair
        for pair in catalog_pair_distances(sample_count=sample_count)
        if pair.distance <= max_distance
    ]
