"""Shared metric sampling helpers for corridor-based route context layers.

Night readiness, accessibility readiness, and landmark lookup all answer the
same question — what does the map say about small neighbourhoods of this routed
polyline? — so they share one sampling and nearest-segment implementation.
"""

from __future__ import annotations

import math

import numpy as np

from . import geo

SAMPLE_STEP_M = 25.0
MAX_SAMPLES = 900


def sample_route(
    points: list[tuple[float, float]],
    *,
    step_m: float = SAMPLE_STEP_M,
    max_samples: int = MAX_SAMPLES,
) -> list[tuple[float, float]]:
    """Resample a polyline at a fixed metric step, keeping both endpoints."""

    if not points:
        return []
    if len(points) == 1:
        return [points[0]]
    if not math.isfinite(step_m) or step_m <= 0:
        raise ValueError("step_m must be a positive finite number")
    if max_samples < 2:
        raise ValueError("max_samples must be at least 2")
    total = geo.path_distance_m(points)
    if not math.isfinite(total) or total <= 0:
        return [points[0], points[-1]]
    count = max(2, min(max_samples, int(total / step_m) + 1))
    step = total / (count - 1) if count > 1 else 0.0
    samples: list[tuple[float, float]] = [points[0]]
    covered = 0.0
    next_target = step
    for start, end in zip(points, points[1:], strict=False):
        leg = geo.haversine(*start, *end)
        while leg > 0 and covered + leg >= next_target:
            ratio = (next_target - covered) / leg
            samples.append(
                (
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio,
                )
            )
            next_target += step
        covered += leg
    if samples[-1] != points[-1]:
        samples.append(points[-1])
    return samples


def local_xy(
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    center_lat: float,
    center_lon: float,
) -> np.ndarray:
    """Equirectangular local-metre projection around one centre point."""

    x = (longitudes - center_lon) * math.cos(math.radians(center_lat)) * 111_320.0
    y = (latitudes - center_lat) * 110_540.0
    return np.column_stack((x, y))


def segment_distances(samples: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """Distance from each sample to each of the stacked segments."""

    seg = ends - starts
    lengths_sq = np.einsum("ij,ij->i", seg, seg)
    delta = samples[:, None, :] - starts[None, :, :]
    scale = np.einsum("ijk,jk->ij", delta, seg) / np.where(lengths_sq > 0, lengths_sq, 1.0)
    t = np.clip(scale, 0.0, 1.0)
    projection = starts[None, :, :] + t[:, :, None] * seg[None, :, :]
    diff = samples[:, None, :] - projection
    return np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))


SEGMENT_CHUNK = 2_048


def nearest_segment_attributes(
    samples: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    attributes: list[np.ndarray],
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Nearest-segment distance plus one attribute array per requested layer.

    Segments are processed in bounded chunks so the (samples x segments)
    distance matrix never materialises for a dense urban bounding box.
    """

    count = len(samples)
    best_distance = np.full(count, np.inf)
    best_attributes = [np.zeros(count, dtype=values.dtype) for values in attributes]
    rows = np.arange(count)
    for chunk_start in range(0, len(starts), SEGMENT_CHUNK):
        chunk_end = chunk_start + SEGMENT_CHUNK
        chunk_distances = segment_distances(
            samples, starts[chunk_start:chunk_end], ends[chunk_start:chunk_end]
        )
        local_best = np.argmin(chunk_distances, axis=1)
        candidate = chunk_distances[rows, local_best]
        improved = candidate < best_distance
        if not improved.any():
            continue
        best_distance[improved] = candidate[improved]
        for index, values in enumerate(attributes):
            best_attributes[index][improved] = values[chunk_start:chunk_end][local_best[improved]]
    return best_distance, best_attributes
