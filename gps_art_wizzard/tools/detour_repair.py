"""Propose local guide repairs; never produce export geometry.

Proposals are routing guides only. Directions must route them again and the
original drawing remains the validation reference.
"""
from __future__ import annotations

import math

import numpy as np

from . import geo, shape_similarity


def turning_repair_guides(
    reference: list[geo.LatLon],
    route: list[geo.LatLon],
    *,
    limit: int = 18,
) -> list[list[geo.LatLon]]:
    """Propose local reference guides around the worst turning phases.

    Equal-arc turning diagnostics identify a bounded set of separated weak
    phases.  Each proposal keeps the incumbent route outside one local window
    and replaces that window with three points from the original contour.  The
    points are only graph-search guides: callers must still route and validate
    the resulting connected street geometry.
    """
    if (
        len(reference) < 5
        or len(route) < 15
        or limit <= 0
        or geo.haversine(*reference[0], *reference[-1]) >= 1
        or geo.haversine(*route[0], *route[-1]) >= 1
    ):
        return []
    total = geo.path_distance_m(route)
    if total < 300:
        return []

    ref = np.asarray(reference, dtype=float)
    if (
        ref.ndim != 2
        or ref.shape[1] != 2
        or not np.isfinite(ref).all()
        or np.any(np.abs(ref[:, 0]) > 90)
        or np.any(np.abs(ref[:, 1]) > 180)
    ):
        return []
    clat, clon = float(ref[:, 0].mean()), float(ref[:, 1].mean())
    reference_m = shape_similarity._route_to_metres(reference, clat, clon)
    route_m = shape_similarity._route_to_metres(route, clat, clon)
    if len(reference_m) < 2 or len(route_m) < 2:
        return []
    scale = float((reference_m.max(axis=0) - reference_m.min(axis=0)).max())
    if not math.isfinite(scale) or scale <= 1e-9:
        return []
    reference_r = shape_similarity.resample(reference_m / scale, 256)
    route_r = shape_similarity.resample(route_m / scale, 256)
    variants = shape_similarity._candidate_orientations(reference_r, route_r)
    variant = max(
        variants,
        key=lambda item: shape_similarity._turning_similarity(reference_r, item),
    )

    # Recover the chosen cyclic phase and direction so diagnostic phases can
    # be mapped back to physical vertices in the incumbent route.
    core = route_r[:-1]
    alignment: tuple[float, bool, int] | None = None
    for reversed_route, oriented in ((False, core), (True, core[::-1])):
        for start in range(len(core)):
            error = float(np.square(np.roll(oriented, -start, axis=0) - variant[:-1]).sum())
            row = (error, reversed_route, start)
            if alignment is None or row < alignment:
                alignment = row
    assert alignment is not None
    _, reversed_route, aligned_start = alignment

    span = max(1, min(8, len(reference_r) // 48))
    ref_tangent = reference_r[2 * span :] - reference_r[: -2 * span]
    route_tangent = variant[2 * span :] - variant[: -2 * span]
    ref_norm = np.linalg.norm(ref_tangent, axis=1)
    route_norm = np.linalg.norm(route_tangent, axis=1)
    valid = (ref_norm > 1e-9) & (route_norm > 1e-9)
    if not np.any(valid):
        return []
    dots = np.ones(len(ref_tangent), dtype=float)
    dots[valid] = np.sum(ref_tangent[valid] * route_tangent[valid], axis=1)
    dots[valid] /= ref_norm[valid] * route_norm[valid]
    errors = np.arccos(np.clip(dots, -1.0, 1.0))

    bins = []
    for start in range(0, len(errors), 16):
        end = min(len(errors), start + 16)
        aligned_phase = start + span + (end - start) // 2
        if reversed_route:
            raw_phase = len(core) - 1 - ((aligned_start + aligned_phase) % len(core))
        else:
            raw_phase = (aligned_start + aligned_phase) % len(core)
        bins.append((float(errors[start:end].mean()), raw_phase / len(core)))
    weak_phases: list[tuple[float, float]] = []
    for mean_error, phase in sorted(bins, reverse=True):
        if mean_error < math.radians(5):
            break
        if all(
            min(abs(phase - other), 1 - abs(phase - other)) >= 24 / len(core)
            for _, other in weak_phases
        ):
            weak_phases.append((mean_error, phase))
        if len(weak_phases) >= 6:
            break

    cumulative = np.asarray([0.0] + [
        geo.haversine(*a, *b) for a, b in zip(route, route[1:], strict=False)
    ]).cumsum()
    reference_center = reference[0]
    reference_xy = np.asarray([
        geo.latlon_to_unit(*point, *reference_center, 1) for point in reference
    ])
    if len(reference_xy) < 128:
        reference_xy = shape_similarity.resample(reference_xy, 257)
    elif len(reference_xy) > 513:
        reference_xy = shape_similarity.resample(reference_xy, 513)
    # The repeated closing sample is useful during resampling but must not
    # participate twice in cyclic reference progress below.
    reference_xy = reference_xy[:-1]
    if reversed_route:
        reference_xy = reference_xy[::-1]

    def reference_phase_index(distance: float) -> int:
        """Map physical route progress through the chosen whole-loop phase.

        Nearest-coordinate matching is ambiguous at self-crossings: both
        visits occupy the same point but belong to different contour phases.
        The turning diagnostic already selected a direction and cyclic start,
        so reuse that alignment to keep a repair on the intended stroke.
        """
        raw_phase = distance / total
        aligned_shift = aligned_start / len(core)
        reference_phase = (
            raw_phase + aligned_shift
            if reversed_route
            else raw_phase - aligned_shift
        ) % 1.0
        return round(reference_phase * len(reference_xy)) % len(reference_xy)

    def nearest_reference(point: geo.LatLon) -> int:
        xy = np.asarray(geo.latlon_to_unit(*point, *reference_center, 1))
        return int(np.argmin(np.linalg.norm(reference_xy - xy, axis=1)))

    proposals: list[list[geo.LatLon]] = []
    seen = set()
    for _, phase in weak_phases:
        center_distance = phase * total
        # Physical windows are stable when provider vertex density varies.
        # Screen the common centred window, a slightly wider/earlier variant,
        # and a phase-forced centred variant for crossings or nearby arms.
        # The six-phase/eighteen-candidate bound remains unchanged.
        window_specs = []
        for half_width_m, offset_m in ((300.0, 0.0), (335.0, -85.0)):
            start_distance = max(
                0.0, center_distance + offset_m - half_width_m,
            )
            end_distance = min(
                total, center_distance + offset_m + half_width_m,
            )
            start = max(
                0,
                min(len(route) - 2, int(np.searchsorted(cumulative, start_distance))),
            )
            end = max(
                start + 2,
                min(len(route) - 1, int(np.searchsorted(cumulative, end_distance))),
            )
            window_specs.append((start, end, False))
        center_index = int(np.searchsorted(cumulative, center_distance))
        phase_half_window = max(4, round((len(route) - 1) * 0.09))
        window_specs.append((
            max(0, center_index - phase_half_window),
            min(len(route) - 1, center_index + phase_half_window),
            True,
        ))
        for start, end, force_phase in window_specs:
            if end <= start + 1:
                continue
            window_distance = float(cumulative[end] - cumulative[start])
            if not 150 <= window_distance <= 1200:
                continue
            if force_phase:
                first = reference_phase_index(float(cumulative[start]))
                progress = (
                    reference_phase_index(float(cumulative[end])) - first
                ) % len(reference_xy)
            else:
                first = nearest_reference(route[start])
                progress = (
                    nearest_reference(route[end]) - first
                ) % len(reference_xy)
            if not force_phase and not 3 < progress < len(reference_xy) * 0.3:
                # Nearby arms and crossings can make coordinate-nearest phase
                # jump backwards or to the wrong visit. Fall back to the
                # already-selected whole-contour alignment in that case.
                first = reference_phase_index(float(cumulative[start]))
                progress = (
                    reference_phase_index(float(cumulative[end])) - first
                ) % len(reference_xy)
            if not 3 < progress < len(reference_xy) * 0.3:
                continue
            middle = []
            for index in range(1, 4):
                reference_index = (first + round(progress * index / 4)) % len(reference_xy)
                x, y = reference_xy[reference_index]
                middle.append(
                    geo.unit_to_latlon(float(x), float(y), *reference_center, 1)
                )
            candidate = route[: start + 1] + middle + route[end:]
            signature = tuple(candidate)
            if signature in seen:
                continue
            seen.add(signature)
            proposals.append(candidate)
            if len(proposals) >= limit:
                return proposals
    return proposals


def reconnect_guides(reference: list[geo.LatLon], route: list[geo.LatLon], *, limit: int = 2,
                     reference_guided: bool = False) -> list[list[geo.LatLon]]:
    """Release a bounded local street section for fresh Directions routing.

    The chord left by omitted guides is an optimistic screening proxy, never
    road evidence. Preserve the endpoints and the rest of the incumbent, then
    require Directions and full validation to decide whether a repair works.
    Reference-guided proposals add one or two points from the corresponding
    original contour section, in the route's travel direction. They remain
    speculative guides and never replace the validation reference.
    """
    if len(reference) < 2 or len(route) < 5 or limit <= 0:
        return []
    cumulative = [0.0]
    for a, b in zip(route, route[1:], strict=False):
        cumulative.append(cumulative[-1] + geo.haversine(*a, *b))
    total = cumulative[-1]
    if total < 300:
        return []
    step = max(120.0 if reference_guided else 100.0, total / 48)
    anchors = [0]
    for index, distance in enumerate(cumulative):
        if distance - cumulative[anchors[-1]] >= step:
            anchors.append(index)
    if anchors[-1] != len(route) - 1:
        anchors.append(len(route) - 1)
    if len(route) <= 50:
        # Sparse street polylines already fit the bound. Retain their corner
        # endpoints instead of skipping an entire small bend between anchors.
        anchors = list(range(len(route)))
    maximum = min(1200.0, max(400.0, total * (0.2 if reference_guided else 0.15)))
    reference_xy = None
    nearest = {}
    reference_closed = geo.haversine(*reference[0], *reference[-1]) < 1
    if reference_guided:
        center = reference[0]
        reference_xy = np.asarray([
            geo.latlon_to_unit(*point, *center, 1) for point in reference
        ])
        if len(reference_xy) < 128:
            reference_xy = shape_similarity.resample(reference_xy, 257)
        elif len(reference_xy) > 513:
            reference_xy = shape_similarity.resample(reference_xy, 513)
        if reference_closed:
            reference_xy = reference_xy[:-1]
        anchor_xy = np.asarray([geo.latlon_to_unit(*route[i], *center, 1) for i in anchors])
        nearest_indices = np.argmin(np.linalg.norm(
            anchor_xy[:, None, :] - reference_xy[None, :, :], axis=2,
        ), axis=1)
        progress = np.diff(nearest_indices)
        if reference_closed:
            count = len(reference_xy)
            progress = (progress + count / 2) % count - count / 2
        if np.sum(progress) < 0:
            reference_xy = reference_xy[::-1]
            nearest_indices = len(reference_xy) - 1 - nearest_indices
        nearest = dict(zip(anchors, map(int, nearest_indices), strict=True))
    screened = []
    for start in anchors:
        for end in anchors:
            if end <= start + 1 or not 150 <= cumulative[end] - cumulative[start] <= maximum:
                continue
            middles: list[list[geo.LatLon]] = [[]]
            if reference_xy is not None:
                progress_count = nearest[end] - nearest[start]
                if reference_closed:
                    progress_count %= len(reference_xy)
                if not 2 < progress_count < len(reference_xy) * 0.3:
                    continue
                middles = []
                for fractions in ((0.5,), (1 / 3, 2 / 3)):
                    middle = []
                    for fraction in fractions:
                        index = (nearest[start] + int(progress_count * fraction)) % len(reference_xy)
                        x, y = reference_xy[index]
                        middle.append(geo.unit_to_latlon(float(x), float(y), *reference[0], 1))
                    middles.append(middle)
            for middle in middles:
                candidate = route[:start + 1] + middle + route[end:]
                measured = shape_similarity.similarity_diagnostics_between_routes(
                    reference, candidate, n=64, closed_sample_floor=64,
                )
                screened.append((min(measured.turning_similarity, measured.length_similarity),
                                 measured.fidelity, start, end, candidate))
    screened.sort(key=lambda row: (-row[0], -row[1], row[2], row[3]))
    baseline = shape_similarity.similarity_diagnostics_between_routes(reference, route)
    ranked = []
    # Only the strongest cheap proxies receive full-resolution diagnostics.
    for _, _, start, end, candidate in screened[:16]:
        measured = shape_similarity.similarity_diagnostics_between_routes(reference, candidate)
        if measured.fidelity <= baseline.fidelity + 0.002:
            continue
        if min(measured.turning_similarity, measured.length_similarity) <= min(
            baseline.turning_similarity, baseline.length_similarity,
        ):
            continue
        if any(getattr(measured, metric) < 0.95 * getattr(baseline, metric)
               for metric in ("coverage_similarity", "landmark_similarity", "extent_similarity")):
            continue
        ranked.append((min(measured.turning_similarity, measured.length_similarity),
                       measured.fidelity, start, end, candidate))
    ranked.sort(key=lambda row: (-row[0], -row[1], row[2], row[3]))
    selected: list[tuple[float, float, int, int, list[geo.LatLon]]] = []
    for row in ranked:
        if reference_guided and any(
            max(0, min(cumulative[row[3]], cumulative[other[3]])
                - max(cumulative[row[2]], cumulative[other[2]]))
            >= 0.5 * (max(cumulative[row[3]], cumulative[other[3]])
                      - min(cumulative[row[2]], cumulative[other[2]]))
            for other in selected
        ):
            continue
        if any(abs(cumulative[row[2]] - cumulative[other[2]])
               + abs(cumulative[row[3]] - cumulative[other[3]]) < 2 * step for other in selected):
            continue
        selected.append(row)
        if len(selected) >= min(limit, 2):
            break
    return [row[4] for row in selected]


def detour_guides(reference: list[geo.LatLon], route: list[geo.LatLon], *, limit: int = 2) -> list[list[geo.LatLon]]:
    if len(route) < 5 or limit <= 0:
        return []
    baseline = shape_similarity.similarity_diagnostics_between_routes(reference, route)
    # Exact repeated coordinates avoid joining nearby but disconnected streets.
    previous: dict[geo.LatLon, int] = {}
    loops = []
    for end, point in enumerate(route):
        start = previous.get(point)
        if start is not None and 1 < end - start < len(route) - 1:
            distance = geo.path_distance_m(route[start:end + 1])
            if 10 <= distance <= 400:
                loops.append((start, end, distance))
        previous[point] = end
    loops = sorted(loops, key=lambda row: row[2], reverse=True)[:8]
    if not loops:
        return []
    # Single removals plus cumulative largest-first removals keep evaluation
    # bounded without the exponential combination search.
    groups = [[loop] for loop in loops] + [loops[:count] for count in range(2, len(loops) + 1)]
    ranked = []
    seen = set()
    for group in groups:
        candidate = [point for index, point in enumerate(route)
                     if not any(start < index <= end for start, end, _ in group)]
        signature = tuple(candidate)
        if len(candidate) < 3 or signature in seen:
            continue
        seen.add(signature)
        measured = shape_similarity.similarity_diagnostics_between_routes(reference, candidate)
        if measured.fidelity <= baseline.fidelity + 0.002:
            continue
        if any(getattr(measured, metric) < 0.95 * getattr(baseline, metric)
               for metric in ("coverage_similarity", "landmark_similarity", "extent_similarity")):
            continue
        ranked.append((measured.fidelity, candidate))
    ranked.sort(key=lambda row: row[0], reverse=True)
    return [points for _, points in ranked[:min(limit, 2)]]
