"""Deterministic, scale-independent shape-similarity metrics.

The score blends discrete Fréchet distance (drawing order) and Hausdorff
distance (outline coverage). Inputs are resampled by arc length before scoring,
which prevents dense road geometry or template sampling from biasing results.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import geo

LatLon = tuple[float, float]


@dataclass(frozen=True)
class SimilarityDiagnostics:
    """Explainable perceptual checks for a routed drawing.

    A single Fréchet/Hausdorff blend is useful but too forgiving of routes
    that occupy roughly the right area while losing the characteristic turns
    of the drawing.  The additional components deliberately measure the
    properties a person uses to recognise a line drawing: outline coverage,
    turn sequence, detour/stretch, and preserved extents.
    """

    fidelity: float
    spatial_similarity: float
    coverage_similarity: float
    turning_similarity: float
    length_similarity: float
    extent_similarity: float
    route_length_ratio: float
    mean_deviation_ratio: float


_ZERO_DIAGNOSTICS = SimilarityDiagnostics(
    fidelity=0.0,
    spatial_similarity=0.0,
    coverage_similarity=0.0,
    turning_similarity=0.0,
    length_similarity=0.0,
    extent_similarity=0.0,
    route_length_ratio=0.0,
    mean_deviation_ratio=float("inf"),
)


def normalise_route(route: list[LatLon]) -> np.ndarray:
    """Normalise a lat/lon route to unit space: centroid at origin, max side = 1."""
    if len(route) < 2:
        return np.zeros((0, 2))
    # Convert to metres offset from the centroid (equirectangular) so the
    # comparison is metric and scale-invariant.
    arr = np.asarray(route, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2 or not np.isfinite(arr).all():
        return np.zeros((0, 2))
    if np.any(np.abs(arr[:, 0]) > 90.0) or np.any(np.abs(arr[:, 1]) > 180.0):
        return np.zeros((0, 2))
    cy, cx = arr[:, 0].mean(), arr[:, 1].mean()
    cos = math.cos(math.radians(cy))
    ys = np.radians(arr[:, 0] - cy) * geo.EARTH_R_M
    xs = np.radians(arr[:, 1] - cx) * geo.EARTH_R_M * cos
    pts = np.stack([xs, ys], axis=1)
    pts -= pts.mean(axis=0)
    extents = pts.max(axis=0) - pts.min(axis=0)
    scale = float(extents.max())
    if scale < 1e-9:
        scale = 1.0
    return pts / scale


def resample(points: np.ndarray, n: int) -> np.ndarray:
    """Evenly resample a polyline to ``n`` points along its length."""
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) == 0:
        return np.zeros((0, 2))
    target_count = max(2, int(n))
    if len(pts) == 1:
        return np.repeat(pts, target_count, axis=0)

    segment_lengths = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    keep = np.concatenate(([True], segment_lengths > 1e-12))
    pts = pts[keep]
    if len(pts) == 1:
        return np.repeat(pts, target_count, axis=0)

    cumulative = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))))
    targets = np.linspace(0.0, cumulative[-1], target_count)
    return np.column_stack(
        (
            np.interp(targets, cumulative, pts[:, 0]),
            np.interp(targets, cumulative, pts[:, 1]),
        )
    )


def discrete_frechet(p: np.ndarray, q: np.ndarray) -> float:
    """Discrete Fréchet distance in O(n*m) time and O(m) working memory."""
    n, m = len(p), len(q)
    if n == 0 or m == 0:
        return float("inf")

    distances = np.linalg.norm(q - p[0], axis=1)
    previous = np.empty(m, dtype=float)
    previous[0] = distances[0]
    for j in range(1, m):
        previous[j] = max(previous[j - 1], distances[j])
    for i in range(1, n):
        distances = np.linalg.norm(q - p[i], axis=1)
        current = np.empty(m, dtype=float)
        current[0] = max(previous[0], distances[0])
        for j in range(1, m):
            current[j] = max(
                min(previous[j], previous[j - 1], current[j - 1]),
                distances[j],
            )
        previous = current
    return float(previous[-1])


def hausdorff(p: np.ndarray, q: np.ndarray) -> float:
    """Symmetric Hausdorff distance between two point sets."""
    if len(p) == 0 or len(q) == 0:
        return float("inf")
    min_from_q = np.full(len(q), np.inf)
    max_from_p = 0.0
    for start in range(0, len(p), 64):
        batch = p[start : start + 64]
        distances = np.linalg.norm(batch[:, np.newaxis, :] - q[np.newaxis, :, :], axis=2)
        max_from_p = max(max_from_p, float(distances.min(axis=1).max()))
        min_from_q = np.minimum(min_from_q, distances.min(axis=0))
    return max(max_from_p, float(min_from_q.max()))


def _similarity(reference: np.ndarray, candidate: np.ndarray) -> float:
    frechet = discrete_frechet(reference, candidate)
    haus = hausdorff(reference, candidate)
    return float(0.6 * math.exp(-frechet / 0.35) + 0.4 * math.exp(-haus / 0.30))


def _nearest_distances(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Distance from every point in ``p`` to the closest point in ``q``."""
    nearest = np.full(len(p), np.inf)
    for start in range(0, len(q), 64):
        batch = q[start : start + 64]
        distances = np.linalg.norm(
            p[:, np.newaxis, :] - batch[np.newaxis, :, :],
            axis=2,
        )
        nearest = np.minimum(nearest, distances.min(axis=1))
    return nearest


def _coverage_components(reference: np.ndarray, candidate: np.ndarray) -> tuple[float, float]:
    """Return a robust outline-coverage score and its unit-space deviation."""
    from_reference = _nearest_distances(reference, candidate)
    from_candidate = _nearest_distances(candidate, reference)
    # RMS penalises sustained displacement, while a small amount of harmless
    # road wiggle cannot dominate as it would under a pure Hausdorff maximum.
    mean_deviation = math.sqrt(
        0.5
        * (
            float(np.mean(np.square(from_reference)))
            + float(np.mean(np.square(from_candidate)))
        )
    )
    return math.exp(-mean_deviation / 0.16), mean_deviation


def _turning_similarity(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Compare smoothed tangent directions along equal arc-length phases."""
    if len(reference) < 5 or len(candidate) < 5:
        return 1.0
    span = max(1, min(8, len(reference) // 48))
    ref_tangent = reference[2 * span :] - reference[: -2 * span]
    cand_tangent = candidate[2 * span :] - candidate[: -2 * span]
    ref_norm = np.linalg.norm(ref_tangent, axis=1)
    cand_norm = np.linalg.norm(cand_tangent, axis=1)
    valid = (ref_norm > 1e-9) & (cand_norm > 1e-9)
    if not np.any(valid):
        return 0.0
    dots = np.sum(ref_tangent[valid] * cand_tangent[valid], axis=1)
    dots /= ref_norm[valid] * cand_norm[valid]
    angular_error = np.arccos(np.clip(dots, -1.0, 1.0))
    return math.exp(-float(np.mean(angular_error)) / 0.70)


def _polyline_length(points: np.ndarray) -> float:
    if len(points) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def _length_components(reference: np.ndarray, candidate: np.ndarray) -> tuple[float, float]:
    reference_length = _polyline_length(reference)
    candidate_length = _polyline_length(candidate)
    if reference_length <= 1e-9 or candidate_length <= 1e-9:
        return 0.0, 0.0
    ratio = candidate_length / reference_length
    return math.exp(-abs(math.log(ratio)) / 0.55), ratio


def _extent_similarity(reference: np.ndarray, candidate: np.ndarray) -> float:
    ref_extent = reference.max(axis=0) - reference.min(axis=0)
    cand_extent = candidate.max(axis=0) - candidate.min(axis=0)
    meaningful = ref_extent > 0.03
    if not np.any(meaningful):
        return 1.0
    if np.any(cand_extent[meaningful] <= 1e-9):
        return 0.0
    log_errors = np.abs(np.log(cand_extent[meaningful] / ref_extent[meaningful]))
    return math.exp(-float(np.mean(log_errors)) / 0.55)


def _diagnostics(reference: np.ndarray, candidate: np.ndarray) -> SimilarityDiagnostics:
    spatial = _similarity(reference, candidate)
    coverage, mean_deviation = _coverage_components(reference, candidate)
    turning = _turning_similarity(reference, candidate)
    length, length_ratio = _length_components(reference, candidate)
    extent = _extent_similarity(reference, candidate)

    components = (spatial, coverage, turning, length, extent)
    weights = (0.28, 0.23, 0.22, 0.15, 0.12)
    # A weighted geometric mean prevents a good distance/outline average from
    # hiding one catastrophically lost recognition cue.
    fidelity = math.exp(
        sum(
            weight * math.log(max(component, 1e-12))
            for component, weight in zip(components, weights, strict=True)
        )
    )
    return SimilarityDiagnostics(
        fidelity=float(min(1.0, max(0.0, fidelity))),
        spatial_similarity=float(spatial),
        coverage_similarity=float(coverage),
        turning_similarity=float(turning),
        length_similarity=float(length),
        extent_similarity=float(extent),
        route_length_ratio=float(length_ratio),
        mean_deviation_ratio=float(mean_deviation),
    )


def _candidate_orientations(reference: np.ndarray, candidate: np.ndarray) -> tuple[np.ndarray, ...]:
    """Return direction/start-point variants representing the same drawing.

    Travel direction is irrelevant to GPS art. For closed loops, the starting
    vertex is irrelevant as well, so align each direction to the reference's
    first point before computing the order-aware distance.
    """
    if len(reference) < 3 or len(candidate) < 3:
        return (candidate, candidate[::-1])

    reference_closed = np.linalg.norm(reference[0] - reference[-1]) <= 0.05
    candidate_closed = np.linalg.norm(candidate[0] - candidate[-1]) <= 0.05
    if not (reference_closed and candidate_closed):
        return (candidate, candidate[::-1])

    core = candidate[:-1]
    variants: list[np.ndarray] = []
    for oriented in (core, core[::-1]):
        start = int(np.argmin(np.linalg.norm(oriented - reference[0], axis=1)))
        aligned = np.roll(oriented, -start, axis=0)
        variants.append(np.vstack((aligned, aligned[0])))
    return tuple(variants)


def shape_fidelity(intended_paths: list[geo.Path], snapped_route: list[LatLon], *, n: int = 128) -> float:
    """0..1 similarity between the intended *unit-space* shape and the snapped route.

    Both are normalised to unit space (max side = 1), resampled to ``n``
    points, and scored via blended Fréchet/Hausdorff distances.

    Note: this is rotation-sensitive — the intended shape must be in the same
    orientation as the placed route. For a rotation-robust score comparing two
    lat/lon routes, use :func:`fidelity_between_routes`.
    """
    intended = np.asarray(geo.stitch_paths(intended_paths), dtype=float)
    if len(intended) < 2 or len(snapped_route) < 2:
        return 0.0

    intended = intended - intended.mean(axis=0)
    ext = intended.max(axis=0) - intended.min(axis=0)
    iscale = float(ext.max()) or 1.0
    intended = intended / iscale

    snapped = normalise_route(snapped_route)
    # Closed-loop start vertices rarely land on the same resampling phase.
    # Doubling the bounded sample count keeps cyclic comparisons effectively
    # start-invariant without changing open-route cost.
    closed = (
        np.linalg.norm(intended[0] - intended[-1]) <= 0.05
        and np.linalg.norm(snapped[0] - snapped[-1]) <= 0.05
    )
    sample_count = max(n, 256) if closed else n
    intended_r = resample(intended, sample_count)
    snapped_r = resample(snapped, sample_count)

    return max(_similarity(intended_r, variant) for variant in _candidate_orientations(intended_r, snapped_r))


def _route_to_metres(route: list[LatLon], clat: float, clon: float) -> np.ndarray:
    """Convert a lat/lon route to metre offsets from a given centre."""
    if len(route) < 2:
        return np.zeros((0, 2))
    arr = np.asarray(route, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2 or not np.isfinite(arr).all():
        return np.zeros((0, 2))
    if np.any(np.abs(arr[:, 0]) > 90.0) or np.any(np.abs(arr[:, 1]) > 180.0):
        return np.zeros((0, 2))
    cos = math.cos(math.radians(clat))
    ys = np.radians(arr[:, 0] - clat) * geo.EARTH_R_M
    xs = np.radians(arr[:, 1] - clon) * geo.EARTH_R_M * cos
    return np.stack([xs, ys], axis=1)


def fidelity_between_routes(reference: list[LatLon], snapped: list[LatLon], *, n: int = 128) -> float:
    """0..1 similarity between two lat/lon routes (e.g. drawn vs. snapped).

    Robust to trimming/extremes: both routes are expressed in a *shared* frame
    (the reference's centroid + scale), so removing a few vertices from the
    snapped route only penalises the affected region instead of rescaling the
    whole shape. Rotation need not be aligned because both routes already share
    the placed orientation.
    """
    return similarity_diagnostics_between_routes(reference, snapped, n=n).fidelity


def similarity_diagnostics_between_routes(
    reference: list[LatLon],
    snapped: list[LatLon],
    *,
    n: int = 128,
    closed_sample_floor: int = 256,
) -> SimilarityDiagnostics:
    """Return perceptual similarity plus actionable failure diagnostics.

    Both polylines stay in the reference route's shared metre frame.  This is
    intentional: translating, shrinking, stretching, or detouring the routed
    result must lower its score instead of being normalised away.
    """
    if len(reference) < 2 or len(snapped) < 2:
        return _ZERO_DIAGNOSTICS
    ref = np.asarray(reference, dtype=float)
    if (
        ref.ndim != 2
        or ref.shape[1] != 2
        or not np.isfinite(ref).all()
        or np.any(np.abs(ref[:, 0]) > 90.0)
        or np.any(np.abs(ref[:, 1]) > 180.0)
    ):
        return _ZERO_DIAGNOSTICS
    clat, clon = float(ref[:, 0].mean()), float(ref[:, 1].mean())
    R = _route_to_metres(reference, clat, clon)
    S = _route_to_metres(snapped, clat, clon)
    if len(R) < 2 or len(S) < 2:
        return _ZERO_DIAGNOSTICS
    scale = float((R.max(axis=0) - R.min(axis=0)).max()) or 1.0
    Rn = R / scale
    Sn = S / scale
    closed = (
        np.linalg.norm(Rn[0] - Rn[-1]) <= 0.05
        and np.linalg.norm(Sn[0] - Sn[-1]) <= 0.05
    )
    # Full route validation deliberately uses a dense closed-loop sample so
    # cyclic start-point alignment stays precise. Coarse preflight compares
    # sparse road-snap guides for hundreds of placements, where forcing every
    # closed candidate to 256 samples turns the O(n²) Fréchet calculation into
    # the dominant runtime. Callers may lower the floor for that screening
    # phase without discarding any candidate; final routed candidates still
    # use the default high-resolution validation.
    sample_count = max(n, max(2, int(closed_sample_floor))) if closed else n
    Rr = resample(Rn, sample_count)
    Sr = resample(Sn, sample_count)
    return max(
        (_diagnostics(Rr, variant) for variant in _candidate_orientations(Rr, Sr)),
        key=lambda result: result.fidelity,
    )
