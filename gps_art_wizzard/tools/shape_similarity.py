"""Deterministic, scale-independent shape-similarity metrics.

The score blends discrete Fréchet distance (drawing order) and Hausdorff
distance (outline coverage). Inputs are resampled by arc length before scoring,
which prevents dense road geometry or template sampling from biasing results.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

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
    landmark_similarity: float = 0.0
    reversal_similarity: float = 1.0


_ZERO_DIAGNOSTICS = SimilarityDiagnostics(
    fidelity=0.0,
    spatial_similarity=0.0,
    coverage_similarity=0.0,
    turning_similarity=0.0,
    length_similarity=0.0,
    extent_similarity=0.0,
    route_length_ratio=0.0,
    mean_deviation_ratio=float("inf"),
    landmark_similarity=0.0,
    reversal_similarity=0.0,
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
    """Discrete Fréchet distance in O(n*m) time and O(n*m) working memory.

    The classic dynamic program is evaluated anti-diagonal by anti-diagonal so
    each wavefront is one vectorised ``min``/``max`` pass instead of a Python
    inner loop. ``min``/``max`` are exact for floats, and the pairwise
    distances are the same Euclidean values as before, so results match the
    scalar implementation bit for bit.
    """
    n, m = len(p), len(q)
    if n == 0 or m == 0:
        return float("inf")

    delta = q[np.newaxis, :, :] - p[:, np.newaxis, :]
    distances = np.sqrt(np.einsum("ijk,ijk->ij", delta, delta))
    # Flat padded table (row-major); row 0 / column 0 stay +inf except the
    # origin so the recurrence reproduces the classic prefix maxima exactly.
    width = m + 1
    cost = np.full((n + 1) * width, np.inf)
    cost[0] = 0.0
    index_pool = np.arange(max(n, m) + 1)
    for anti in range(2, n + m + 1):
        i_lo = max(1, anti - m)
        i_hi = min(n, anti - 1)
        ii = index_pool[i_lo : i_hi + 1]
        jj = anti - ii
        flat = ii * width + jj      # cell (i, j)
        up = flat - width           # (i-1, j)
        diagonal = up - 1           # (i-1, j-1)
        left = flat - 1             # (i, j-1)
        best = np.minimum(cost.take(up), cost.take(diagonal))
        best = np.minimum(best, cost.take(left))
        # distances holds the unpadded n×m table: row (i-1), column (j-1).
        step = distances.take(flat - ii - width)
        cost.put(flat, np.maximum(step, best))
    return float(cost[n * width + m])


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


def _signed_turns(points: np.ndarray, span: int) -> np.ndarray:
    """Return signed chord-turn angles at one geometric observation scale.

    Street geometry contains many kerb- and junction-scale wiggles that are not
    semantic parts of a drawing.  Chords spanning several arc-length samples
    suppress that noise while retaining a heart notch, arrow tip, ear, or
    similarly characteristic feature.  Endpoints of open curves deliberately
    remain zero because there is no two-sided turn to estimate there.
    """
    count = len(points)
    turns = np.zeros(count, dtype=float)
    closed = count >= 3 and bool(np.linalg.norm(points[0] - points[-1]) <= 0.05)
    core_count = count - 1 if closed else count
    if core_count < 2 * span + 1:
        return turns

    if closed:
        indices = np.arange(core_count)
        previous_indices = (indices - span) % core_count
        next_indices = (indices + span) % core_count
    else:
        indices = np.arange(span, core_count - span)
        previous_indices = indices - span
        next_indices = indices + span

    incoming = points[indices] - points[previous_indices]
    outgoing = points[next_indices] - points[indices]
    incoming_length = np.linalg.norm(incoming, axis=1)
    outgoing_length = np.linalg.norm(outgoing, axis=1)
    valid = (incoming_length > 1e-9) & (outgoing_length > 1e-9)
    valid_incoming = incoming[valid]
    valid_outgoing = outgoing[valid]
    cross = (
        valid_incoming[:, 0] * valid_outgoing[:, 1]
        - valid_incoming[:, 1] * valid_outgoing[:, 0]
    )
    dot = np.sum(valid_incoming * valid_outgoing, axis=1)
    turns[indices[valid]] = np.arctan2(cross, dot)
    if closed:
        turns[-1] = turns[0]
    return turns


def _reversal_event_count(points: np.ndarray) -> int:
    """Count distinct near-U-turn events in an arc-length sampled curve.

    A router can stay close to the intended outline while repeatedly doubling
    back along the same street.  Those extra strokes are visually destructive
    but can be diluted in an average tangent score.  Grouping adjacent extreme
    signed turns counts each hairpin once instead of counting its samples.
    """
    if len(points) < 7:
        return 0
    span = max(2, len(points) // 64)
    extreme = np.abs(_signed_turns(points, span)) >= math.radians(145.0)
    if not np.any(extreme):
        return 0
    starts = extreme & ~np.concatenate(([False], extreme[:-1]))
    count = int(np.count_nonzero(starts))
    # A closed curve can split one event across the sampling seam.
    closed = np.linalg.norm(points[0] - points[-1]) <= 0.05
    if closed and extreme[0] and extreme[-2] and count > 1:
        count -= 1
    return count


def _reversal_similarity(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Penalise U-turn/backtracking events not present in the drawing."""
    extra_events = max(
        0,
        _reversal_event_count(candidate) - _reversal_event_count(reference),
    )
    return math.exp(-extra_events / 1.25)


def _salient_indices(
    turns: np.ndarray,
    *,
    span: int,
    closed: bool,
    maximum: int = 12,
) -> list[int]:
    """Select separated curvature extrema instead of uniformly weighted noise."""
    if len(turns) == 0:
        return []
    magnitude = np.abs(turns)
    core_count = len(turns) - 1 if closed else len(turns)
    core_magnitude = magnitude[:core_count]
    mean_magnitude = float(np.mean(core_magnitude))
    if (
        mean_magnitude > 1e-9
        and float(np.std(core_magnitude)) / mean_magnitude < 0.08
    ):
        # Constant-curvature contours (notably circles) have no privileged
        # semantic corner. Selecting arbitrary equal maxima would make the
        # result depend on the route's starting phase.
        return []
    threshold = max(math.radians(10.0), float(np.quantile(magnitude, 0.78)))
    indices = range(core_count) if closed else range(span, core_count - span)
    candidates = [
        index
        for index in indices
        if magnitude[index] >= threshold
        and magnitude[index]
        >= magnitude[(index - 1) % core_count if closed else max(0, index - 1)]
        and magnitude[index]
        >= magnitude[(index + 1) % core_count if closed else min(core_count - 1, index + 1)]
    ]
    separation = max(2, span)
    selected: list[int] = []
    for index in sorted(candidates, key=lambda item: magnitude[item], reverse=True):
        if all(
            (
                min(abs(index - other), core_count - abs(index - other))
                if closed
                else abs(index - other)
            )
            > separation
            for other in selected
        ):
            selected.append(index)
            if len(selected) >= maximum:
                break
    return sorted(selected)


def _landmark_scale_similarity(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    span: int,
) -> float:
    """Compare the sign, magnitude, and arc-length phase of salient turns."""
    reference_turns = _signed_turns(reference, span)
    candidate_turns = _signed_turns(candidate, span)
    closed = (
        len(reference) >= 3
        and len(candidate) >= 3
        and np.linalg.norm(reference[0] - reference[-1]) <= 0.05
        and np.linalg.norm(candidate[0] - candidate[-1]) <= 0.05
    )
    landmarks = _salient_indices(reference_turns, span=span, closed=bool(closed))
    if not landmarks:
        # Smooth contours such as circles have no isolated dominant point at
        # this scale; the other curve/coverage metrics remain authoritative.
        return 1.0

    search_radius = max(2, len(reference) // 32)

    def score_with_sign(direction_sign: float) -> float:
        weighted_error = 0.0
        total_weight = 0.0
        for index in landmarks:
            target_turn = reference_turns[index]
            if closed:
                core_count = len(candidate_turns) - 1
                candidate_indices = [
                    (index + delta) % core_count
                    for delta in range(-search_radius, search_radius + 1)
                ]
            else:
                start = max(span, index - search_radius)
                end = min(len(candidate_turns) - span, index + search_radius + 1)
                candidate_indices = list(range(start, end))
            if not candidate_indices:
                best_error = math.pi
            else:
                best_error = math.pi
                for candidate_index in candidate_indices:
                    candidate_turn = direction_sign * candidate_turns[candidate_index]
                    angular_error = abs(
                        math.atan2(
                            math.sin(target_turn - candidate_turn),
                            math.cos(target_turn - candidate_turn),
                        )
                    )
                    # Arc-length resampling spreads a mathematically sharp
                    # corner across neighbouring samples. Treat sub-18°
                    # differences as the same landmark; larger changes still
                    # receive their full excess penalty.
                    angular_error = max(0.0, angular_error - math.radians(18.0))
                    index_distance = abs(candidate_index - index)
                    if closed:
                        index_distance = min(index_distance, core_count - index_distance)
                    phase_error = 0.06 * index_distance / search_radius
                    best_error = min(best_error, angular_error + phase_error)
            # Strong extrema carry more contour information.  Squaring the
            # bounded magnitude makes a destroyed arrow tip matter more than a
            # small street kink without allowing a single point to dominate.
            weight = min(math.pi, abs(target_turn)) ** 2
            weighted_error += weight * best_error
            total_weight += weight
        mean_error = weighted_error / max(total_weight, 1e-12)
        return math.exp(-mean_error / 0.58)

    # Reversing travel direction flips signed curvature. GPS art must not
    # change quality merely because the route is traversed backwards.
    return max(score_with_sign(1.0), score_with_sign(-1.0))


def _landmark_similarity(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Multiscale similarity of perceptually dominant contour landmarks."""
    if len(reference) < 9 or len(candidate) < 9:
        return 1.0
    spans = sorted({max(2, len(reference) // 32), max(3, len(reference) // 16)})
    scores = [
        _landmark_scale_similarity(reference, candidate, span=span)
        for span in spans
        if len(reference) >= 2 * span + 1 and len(candidate) >= 2 * span + 1
    ]
    if not scores:
        return 1.0
    return math.exp(sum(math.log(max(score, 1e-12)) for score in scores) / len(scores))


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
    # Orientation-invariant components: reversing or cyclically rotating a
    # polyline keeps its point set, arc length, extents, and extreme-turn
    # events unchanged (and Hausdorff is set-based), so these are computed
    # once instead of once per candidate variant below.
    haus = hausdorff(reference, candidate)
    coverage, mean_deviation = _coverage_components(reference, candidate)
    length, length_ratio = _length_components(reference, candidate)
    extent = _extent_similarity(reference, candidate)
    reversals = _reversal_similarity(reference, candidate)

    weights = (0.22, 0.18, 0.15, 0.19, 0.11, 0.08, 0.07)
    best: SimilarityDiagnostics | None = None
    best_fidelity = -1.0
    for oriented in _candidate_orientations(reference, candidate):
        frechet = discrete_frechet(reference, oriented)
        spatial = float(0.6 * math.exp(-frechet / 0.35) + 0.4 * math.exp(-haus / 0.30))
        turning = _turning_similarity(reference, oriented)
        landmarks = _landmark_similarity(reference, oriented)
        components = (spatial, coverage, turning, landmarks, length, extent, reversals)
        # A weighted geometric mean prevents a good distance/outline average
        # from hiding one catastrophically lost recognition cue.
        fidelity = math.exp(
            sum(
                weight * math.log(max(component, 1e-12))
                for component, weight in zip(components, weights, strict=True)
            )
        )
        if fidelity > best_fidelity:
            best_fidelity = fidelity
            best = SimilarityDiagnostics(
                fidelity=float(min(1.0, max(0.0, fidelity))),
                spatial_similarity=float(spatial),
                coverage_similarity=float(coverage),
                turning_similarity=float(turning),
                length_similarity=float(length),
                extent_similarity=float(extent),
                route_length_ratio=float(length_ratio),
                mean_deviation_ratio=float(mean_deviation),
                landmark_similarity=float(landmarks),
                reversal_similarity=float(reversals),
            )
    assert best is not None  # _candidate_orientations always yields variants
    return best


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


@lru_cache(maxsize=256)
def _similarity_diagnostics_cached(
    reference: tuple,
    snapped: tuple,
    n: int,
    closed_sample_floor: int,
) -> SimilarityDiagnostics:
    return _similarity_diagnostics_between_routes(
        list(reference),
        list(snapped),
        n=n,
        closed_sample_floor=closed_sample_floor,
    )


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

    Identical route pairs recur across refinement iterations and candidate
    merges, so results for identical inputs are memoised. The returned frozen
    dataclass is safe to share between callers.
    """
    if len(reference) < 2 or len(snapped) < 2:
        return _ZERO_DIAGNOSTICS
    try:
        reference_key = tuple(reference)
        snapped_key = tuple(snapped)
        hash(reference_key)
        hash(snapped_key)
    except TypeError:
        # Unhashable point containers still get a full computation.
        return _similarity_diagnostics_between_routes(
            reference,
            snapped,
            n=n,
            closed_sample_floor=closed_sample_floor,
        )
    return _similarity_diagnostics_cached(
        reference_key,
        snapped_key,
        int(n),
        int(closed_sample_floor),
    )


def _similarity_diagnostics_between_routes(
    reference: list[LatLon],
    snapped: list[LatLon],
    *,
    n: int = 128,
    closed_sample_floor: int = 256,
) -> SimilarityDiagnostics:
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
    # ``_diagnostics`` evaluates every start/direction variant internally and
    # keeps orientation-invariant components single-computed.
    return _diagnostics(Rr, Sr)


def salient_route_landmarks(
    route: list[LatLon],
    *,
    n: int = 128,
    maximum: int = 12,
) -> list[LatLon]:
    """Return displayable multiscale curvature landmarks for a route.

    The output is diagnostic only: these points explain which notches, tips,
    and corners carry extra recognition weight. They are not independently
    snapped waypoints and therefore do not claim graph connectivity.
    """
    if len(route) < 3 or maximum <= 0:
        return []
    ref = np.asarray(route, dtype=float)
    if (
        ref.ndim != 2
        or ref.shape[1] != 2
        or not np.isfinite(ref).all()
        or np.any(np.abs(ref[:, 0]) > 90.0)
        or np.any(np.abs(ref[:, 1]) > 180.0)
    ):
        return []
    clat, clon = float(ref[:, 0].mean()), float(ref[:, 1].mean())
    metres = _route_to_metres(route, clat, clon)
    sample_count = max(32, int(n))
    sampled = resample(metres, sample_count)
    # Keep this identical to ``_signed_turns``: using a looser display-only
    # closure threshold would mix cyclic non-maximum suppression with open
    # endpoint turns for nearly closed paths.
    closed = bool(np.linalg.norm(sampled[0] - sampled[-1]) <= 0.05)

    ranked: dict[int, float] = {}
    spans = sorted({max(2, sample_count // 32), max(3, sample_count // 16)})
    for span in spans:
        turns = _signed_turns(sampled, span)
        for index in _salient_indices(
            turns,
            span=span,
            closed=closed,
            maximum=maximum,
        ):
            ranked[index] = max(ranked.get(index, 0.0), abs(float(turns[index])))
    chosen = sorted(
        sorted(ranked, key=lambda index: ranked[index], reverse=True)[:maximum]
    )
    if not chosen:
        return []

    cos_lat = math.cos(math.radians(clat))
    if abs(cos_lat) <= 1e-12:
        return []
    return [
        (
            clat + math.degrees(float(sampled[index, 1]) / geo.EARTH_R_M),
            clon
            + math.degrees(float(sampled[index, 0]) / (geo.EARTH_R_M * cos_lat)),
        )
        for index in chosen
    ]
