"""Fail-closed checks for every user-visible GPS route or download.

The application may keep an ideal or straight-line guide internally for
diagnostics and retries.  It must never present or serialise that guide as a
performable GPS route.  Only geometry returned successfully by the configured
Directions provider may cross a public/export boundary.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def is_provider_routed_geometry(
    points: object,
    total_distance_m: object,
    *,
    routed: bool,
) -> bool:
    """Validate the minimum contract carried by a successful Directions call."""

    if not routed or not isinstance(points, Sequence) or isinstance(points, str | bytes):
        return False
    if len(points) < 2:
        return False
    if isinstance(total_distance_m, bool) or not isinstance(
        total_distance_m,
        int | float,
    ):
        return False
    distance = float(total_distance_m)
    if not math.isfinite(distance) or distance <= 0:
        return False
    distinct: set[tuple[float, float]] = set()
    for point in points:
        if not isinstance(point, Sequence) or isinstance(point, str | bytes) or len(point) < 2:
            return False
        try:
            lat, lon = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            return False
        if (
            not math.isfinite(lat)
            or not math.isfinite(lon)
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            return False
        distinct.add((lat, lon))
    return len(distinct) >= 2
