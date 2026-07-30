"""GPX / TCX serialisers for the final snapped route."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from xml.sax.saxutils import escape

import gpxpy
import gpxpy.gpx

LatLon = tuple[float, float]


def to_gpx(
    points: list[LatLon],
    *,
    name: str = "GPS Art Wizard route",
    sport: str = "run",
    total_distance_m: float = 0.0,
) -> str:
    """Build a GPX 1.1 document with a single track from ``points``."""
    gpx = gpxpy.gpx.GPX()
    gpx.name = name
    gpx.tracks.append(gpxpy.gpx.GPXTrack(name=name))
    seg = gpxpy.gpx.GPXTrackSegment()
    gpx.tracks[0].segments.append(seg)
    for lat, lon in points:
        seg.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon))
    if total_distance_m:
        gpx.description = f"{total_distance_m / 1000:.2f} km, sport={sport}"
    return gpx.to_xml()


def to_tcx(
    points: list[LatLon],
    *,
    name: str = "GPS Art Wizard route",
    sport: str = "running",
    total_distance_m: float = 0.0,
    pace_s_per_m: float | None = None,
) -> str:
    """Minimal TrainingCenterDB v2 TCX course."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    step = timedelta(seconds=max(1.0, (pace_s_per_m or 0.5)))
    t = start
    pts_xml: list[str] = []
    for lat, lon in points:
        pts_xml.append(
            f"      <Trackpoint><Time>{t.isoformat()}</Time>"
            f"<Position><LatitudeDegrees>{lat:.7f}</LatitudeDegrees>"
            f"<LongitudeDegrees>{lon:.7f}</LongitudeDegrees></Position></Trackpoint>"
        )
        t += step
    dist = float(total_distance_m) or 0.0
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">'
        f'<Courses><Course><Name>{escape(name)}</Name><Lap><TotalTimeSeconds>{int(t.timestamp()-start.timestamp())}</TotalTimeSeconds>'
        f'<DistanceMeters>{dist:.1f}</DistanceMeters><BeginTime>{start.isoformat()}</BeginTime>'
        f'<Intensity>Active</Intensity></Lap><Track>\n'
        + "\n".join(pts_xml)
        + '\n    </Track></Course></Courses></TrainingCenterDatabase>'
    )


def write_files(points: list[LatLon], *, name: str, sport: str, total_distance_m: float, out_dir: str) -> dict[str, str]:
    """Serialise to GPX + TCX and write to ``out_dir``. Returns {format: path}."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")[:40] or "route"
    paths: dict[str, str] = {}
    gpx = to_gpx(points, name=name, sport=sport, total_distance_m=total_distance_m)
    gpx_path = os.path.join(out_dir, f"{safe}.gpx")
    with open(gpx_path, "w", encoding="utf-8") as fh:
        fh.write(gpx)
    paths["gpx"] = gpx_path
    try:
        tcx = to_tcx(points, name=name, sport=sport, total_distance_m=total_distance_m)
        tcx_path = os.path.join(out_dir, f"{safe}.tcx")
        with open(tcx_path, "w", encoding="utf-8") as fh:
            fh.write(tcx)
        paths["tcx"] = tcx_path
    except Exception:  # noqa: BLE001
        pass
    return paths
