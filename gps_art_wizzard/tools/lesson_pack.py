"""Classroom worksheet data: turn a drawing into a bearing-and-distance walk.

The GPS-art lesson plan used in schools (sketch a figure, scale it, walk the
bearings, log the track) needs exactly the numbers this module produces: the
drawing reduced to lettered waypoints, the initial bearing and metric length of
every leg, the cumulative distance, and the paper scale that fits the figure on
a worksheet. All values are deterministic and derived from the same guide the
planner routes over, so the worksheet and the real route stay consistent.
"""

from __future__ import annotations

import math

from . import geo
from .shape_similarity import salient_route_landmarks

PAPER_LONG_SIDE_M = 0.17  # usable drawing height on an A4 worksheet, metres
MIN_LEG_M = 20.0
MIN_TOTAL_M = 100.0
MAX_WAYPOINTS = 12
_COMPASS = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]


def compass_point(bearing_deg: float) -> str:
    """16-point compass name for one bearing in degrees."""

    index = int(((bearing_deg % 360.0) + 11.25) // 22.5) % 16
    return _COMPASS[index]


def _extent_m(points: list[tuple[float, float]]) -> tuple[float, float]:
    center_lat = sum(point[0] for point in points) / len(points)
    latitudes = [point[0] for point in points]
    longitudes = [point[1] for point in points]
    height_m = (max(latitudes) - min(latitudes)) * 110_540.0
    width_m = (max(longitudes) - min(longitudes)) * 111_320.0 * math.cos(math.radians(center_lat))
    return abs(width_m), abs(height_m)


def build_lesson_pack(
    reference_points: list[tuple[float, float]],
    *,
    closed: bool = True,
    title: str = "My GPS drawing",
    shape_name: str = "drawing",
) -> dict:
    """Reduce a drawing guide to lettered waypoints with bearings and lengths."""

    if len(reference_points) < 3:
        return {
            "available": False,
            "message": "A drawing with at least three guide points is needed for a worksheet.",
        }

    route_core = (
        reference_points[:-1]
        if closed and reference_points[0] == reference_points[-1]
        else reference_points
    )
    anchors: list[tuple[float, float]] = [route_core[0]]
    landmark_limit = max(1, MAX_WAYPOINTS - (1 if closed else 0))
    for landmark in salient_route_landmarks(reference_points, maximum=landmark_limit):
        if geo.haversine(*anchors[-1], *landmark) >= MIN_LEG_M:
            anchors.append(landmark)
    if closed:
        if anchors[-1] != anchors[0]:
            anchors.append(anchors[0])
    elif route_core[-1] != anchors[-1]:
        anchors.append(route_core[-1])

    # Degenerate anchors (dense landmarks on a tiny sketch) collapse toward an
    # even spread so a worksheet always has a manageable number of legs.
    if len(anchors) < 3:
        stride = max(1, len(route_core) // 8)
        anchors = route_core[::stride]
        if not closed and anchors[-1] != route_core[-1]:
            anchors.append(route_core[-1])
        if closed and anchors[0] != anchors[-1]:
            anchors.append(anchors[0])

    waypoints: list[dict] = []
    cumulative = 0.0
    legs: list[tuple[tuple[float, float], tuple[float, float], float]] = []
    for start, end in zip(anchors[:-1], anchors[1:], strict=False):
        legs.append((start, end, geo.haversine(*start, *end)))
    if sum(leg_m for _, _, leg_m in legs) < MIN_TOTAL_M:
        return {
            "available": False,
            "message": "The drawing is too small for a worksheet; scale it up first.",
        }
    # Tiny intermediate hops are merged into the next leg; the closing leg of a
    # closed figure always survives so the walk returns to its start.
    for index, (start, end, leg_m) in enumerate(legs):
        if leg_m < MIN_LEG_M and index < len(legs) - 1:
            continue
        bearing_deg = geo.bearing(*start, *end)
        letter = chr(ord("A") + len(waypoints)) if len(waypoints) < 26 else f"P{len(waypoints) + 1}"
        is_closing_leg = closed and index == len(legs) - 1
        next_letter = (
            "A"
            if is_closing_leg
            else (
                chr(ord("A") + len(waypoints) + 1)
                if len(waypoints) + 1 < 26
                else f"P{len(waypoints) + 2}"
            )
        )
        waypoints.append(
            {
                "id": letter,
                "latitude": round(start[0], 6),
                "longitude": round(start[1], 6),
                "bearing_deg": round(bearing_deg, 1),
                "compass": compass_point(bearing_deg),
                "leg_distance_m": round(leg_m),
                "cumulative_m": round(cumulative),
                "to_id": next_letter,
            }
        )
        cumulative += leg_m

    if not waypoints:
        return {
            "available": False,
            "message": "The drawing is too small for a worksheet; scale it up first.",
        }

    width_m, height_m = _extent_m(reference_points)
    extent_m = max(width_m, height_m)
    scale_ratio = int(round(extent_m / PAPER_LONG_SIDE_M))
    total_distance_m = sum(item["leg_distance_m"] for item in waypoints)

    notes = [
        "Bearings are measured from north and turn clockwise, exactly like a compass.",
        "Walk each leg from its lettered point towards the next letter.",
        f"On paper 1 cm stands for about {scale_ratio / 100:.0f} m; check your sketch matches before walking.",
    ]
    if closed:
        notes.append("The last leg returns to point A, closing the figure.")

    return {
        "available": True,
        "title": title,
        "shape_name": shape_name,
        "closed": closed,
        "waypoint_count": len(waypoints),
        "waypoints": waypoints,
        "total_distance_m": round(total_distance_m),
        "total_distance_km": round(total_distance_m / 1000.0, 2),
        "extent_m": round(extent_m),
        "scale_ratio": scale_ratio,
        "notes": notes,
    }
