from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from app.core.units import haversine_m

type GeoPoint = tuple[float, float]  # (lat, lon)

GPX_NS = "http://www.topografix.com/GPX/1/1"


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "route"


def _dedupe(points: list[GeoPoint]) -> list[GeoPoint]:
    out: list[GeoPoint] = []
    for p in points:
        if not out or out[-1] != p:
            out.append(p)
    return out


def _format_coord(v: float) -> str:
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f"invalid coordinate: {v}")
    return f"{v:.6f}"


def build_gpx(
    points: list[GeoPoint],
    name: str,
    description: str,
    mode: str = "continuous",
    ele: list[float | None] | None = None,
) -> str:
    """Build a GPX 1.1 document (section 24/54)."""
    pts = _dedupe(points)
    if len(pts) < 2:
        raise ValueError("GPX requires at least 2 distinct trackpoints")

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<gpx version="1.1" creator="CityShapeRunner" '
        f'xmlns="{GPX_NS}">'
    )
    lines.append("  <metadata>")
    lines.append(f"    <name>{escape(name)}</name>")
    lines.append(f"    <desc>{escape(description)}</desc>")
    lines.append("  </metadata>")
    lines.append("  <trk>")
    lines.append(f"    <name>{escape(name)}</name>")
    lines.append("  <trkseg>")
    for i, (lon, lat) in enumerate(pts):
        extra = ""
        if ele and i < len(ele) and ele[i] is not None:
            extra += f"<ele>{ele[i]:.1f}</ele>"
        lines.append(
            f"    <trkpt lat=\"{_format_coord(lat)}\" lon=\"{_format_coord(lon)}\">{extra}</trkpt>"
        )
    lines.append("  </trkseg>")
    lines.append("  </trk>")
    lines.append("</gpx>")
    return "\n".join(lines) + "\n"


def build_continuous_gpx(route_lonlat: list[GeoPoint], name: str, description: str) -> str:
    return build_gpx(route_lonlat, name, description, mode="continuous")





def file_name(city: str, artwork: str, distance_km: float, activity: str) -> str:
    dist_rounded = int(round(distance_km))
    return f"{slugify(city)}-{slugify(artwork)}-{dist_rounded}k-{slugify(activity)}.gpx"


@dataclass
class GpxValidation:
    valid: bool
    errors: list[str] = field(default_factory=list)
    point_count: int = 0
    total_distance_km: float = 0.0


def validate_gpx(text: str) -> GpxValidation:
    """Validate a GPX 1.1 document per section 24.5."""
    errors: list[str] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return GpxValidation(valid=False, errors=[f"xml_parse_error: {exc}"])

    tag = root.tag.split("}")[-1]
    if tag != "gpx":
        errors.append("missing_gpx_root")
    if root.get("version") != "1.1":
        errors.append("invalid_gpx_version")

    pts: list[tuple[float, float]] = []
    for trkpt in root.iter():
        local = trkpt.tag.split("}")[-1]
        if local != "trkpt":
            continue
        lat_s = trkpt.get("lat")
        lon_s = trkpt.get("lon")
        if lat_s is None or lon_s is None:
            errors.append("trkpt_missing_coords")
            continue
        try:
            lat = float(lat_s)
            lon = float(lon_s)
        except ValueError:
            errors.append("trkpt_non_numeric_coords")
            continue
        if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
            errors.append("trkpt_nan_coords")
            continue
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            errors.append("trkpt_coord_out_of_range")
            continue
        pts.append((lat, lon))

    if len(pts) < 2:
        errors.append("insufficient_trackpoints")

    total_m = 0.0
    for i in range(len(pts) - 1):
        total_m += haversine_m(pts[i], pts[i + 1])
    total_km = total_m / 1000.0
    if pts and total_km <= 0.0:
        errors.append("zero_distance")

    return GpxValidation(
        valid=len(errors) == 0,
        errors=errors,
        point_count=len(pts),
        total_distance_km=round(total_km, 4),
    )
