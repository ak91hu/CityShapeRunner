"""Order comparable route alternatives by measured map coverage.

The coarse coverage grid is a presentation heuristic, never routing evidence.
Every original candidate and every street vertex is retained unchanged.
"""
from __future__ import annotations

import math

import numpy as np

from .geo import EARTH_R_M


def _coverage(points, origin):
    if len(points) < 2:
        return set()
    coordinates = np.asarray(points, dtype=float)
    xy = np.column_stack((
        np.radians(coordinates[:, 1] - origin[1]) * EARTH_R_M * math.cos(math.radians(origin[0])),
        np.radians(coordinates[:, 0] - origin[0]) * EARTH_R_M,
    ))
    distances = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))))
    count = max(2, min(2048, int(distances[-1] / 70) + 2))
    samples = np.linspace(0, distances[-1], count)
    x = np.interp(samples, distances, xy[:, 0])
    y = np.interp(samples, distances, xy[:, 1])
    # Two staggered grids reduce sensitivity to a route lying on a cell edge.
    return {(grid, int(px), int(py)) for grid, shift in enumerate((0, 75))
            for px, py in zip(np.floor((x + shift) / 150), np.floor((y + shift) / 150), strict=True)}


def diverse_route_order(candidates: list[dict]) -> list[dict]:
    """Keep the recommendation first and all candidates; diversify two cards."""
    if len(candidates) < 3:
        return candidates
    origin = candidates[0]["points_preview"][0]
    coverage = {id(candidate): _coverage(candidate["points_preview"], origin) for candidate in candidates}

    def likeness(candidate):
        return candidate.get("validation", {}).get("shape_fidelity", 0.0)

    chosen = [candidates[0]]
    remaining = list(candidates[1:])
    floor = max(0.35, likeness(chosen[0]) * 0.80)
    while remaining and len(chosen) < 3:
        ready = [candidate for candidate in remaining if candidate.get("verification", {}).get("passed")]
        pool = ready or remaining
        comparable = [candidate for candidate in pool if likeness(candidate) >= floor]

        def utility(candidate):
            cells = coverage[id(candidate)]
            overlap = max((len(cells & coverage[id(other)]) /
                           max(1, min(len(cells), len(coverage[id(other)])))) for other in chosen)
            return 0.65 * likeness(candidate) + 0.35 * (1 - overlap)

        winner = max(comparable or pool, key=utility)
        chosen.append(winner)
        remaining.remove(winner)
    return [*chosen, *remaining]
