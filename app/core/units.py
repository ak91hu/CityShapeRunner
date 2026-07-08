from __future__ import annotations

import math
from dataclasses import dataclass

from pyproj import Proj

_EARTH_RADIUS_M = 6371000.0

type GeoPoint = tuple[float, float]  # (lat, lon)
type MetricPoint = tuple[float, float]  # (x, y) in a local projected CRS


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in meters between two (lat, lon) points.

    Used only for rough bbox/distance sanity checks, never for geometry
    operations (those use a projected metric CRS, see Projector).
    """
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def select_projected_crs(lat: float, lon: float) -> str:
    """Return a PROJ string for a local azimuthal-equidistant projection.

    AEQD centered on the city centroid gives metric coordinates that are
    accurate enough for city-scale distance/angle work and avoids UTM
    zone-boundary edge cases.
    """
    return f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs"


@dataclass
class Projector:
    """Bidirectional WGS84 <-> local metric coordinate converter."""

    proj: Proj
    lat0: float
    lon0: float

    @classmethod
    def around(cls, lat: float, lon: float) -> "Projector":
        return cls(proj=Proj(select_projected_crs(lat, lon)), lat0=lat, lon0=lon)

    def to_metric(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = self.proj(lon, lat)
        return float(x), float(y)

    def to_metric_polyline(self, polyline_lonlat: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [self.to_metric(lon, lat) for lat, lon in polyline_lonlat]

    def to_wgs84(self, x: float, y: float) -> tuple[float, float]:
        lon, lat = self.proj(x, y, inverse=True)
        return float(lat), float(lon)

    def to_wgs84_polyline(self, polyline_xy: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [self.to_wgs84(x, y) for x, y in polyline_xy]


def polyline_length_m(polyline_xy: list[tuple[float, float]]) -> float:
    return sum(
        math.hypot(polyline_xy[i + 1][0] - polyline_xy[i][0], polyline_xy[i + 1][1] - polyline_xy[i][1])
        for i in range(len(polyline_xy) - 1)
    )


def heading_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Compass heading of segment a->b in metric coordinates (degrees, 0=east)."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return math.degrees(math.atan2(dy, dx))


def angle_difference_deg(a_deg: float, b_deg: float) -> float:
    diff = (a_deg - b_deg + 180.0) % 360.0 - 180.0
    return abs(diff)
