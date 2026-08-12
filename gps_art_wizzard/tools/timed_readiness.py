"""Time-aware route context with a resilient weather fallback."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import httpx


def _sun_altitude(latitude: float, longitude: float, when: datetime) -> float:
    """Approximate solar altitude, sufficient for a conservative daylight flag."""

    local = when.astimezone(UTC)
    day = local.timetuple().tm_yday
    hour = local.hour + local.minute / 60 + local.second / 3600
    declination = math.radians(23.44 * math.sin(math.radians((360 / 365) * (day - 81))))
    solar_hour = math.radians(15 * (hour + longitude / 15 - 12))
    lat = math.radians(latitude)
    return math.degrees(
        math.asin(math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(declination) * math.cos(solar_hour))
    )


def time_readiness(latitude: float, longitude: float, when: datetime) -> dict:
    """Return a compact weather and daylight briefing without blocking planning."""

    altitude = _sun_altitude(latitude, longitude, when)
    daylight = "daylight" if altitude >= 0 else "after_dark"
    response = {
        "departure_at": when.astimezone(UTC).isoformat(),
        "daylight": daylight,
        "sun_altitude_deg": round(altitude, 1),
        "weather": None,
        "seasonal_note": "Check temporary closures and local access rules before leaving.",
    }
    try:
        payload = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "hourly": "temperature_2m,precipitation,weather_code,wind_speed_10m",
                "timezone": "UTC",
            },
            timeout=3.0,
        ).json()
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") if isinstance(hourly, dict) else []
        if isinstance(times, list) and times:
            requested_hour = when.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
            index = min(
                range(len(times)),
                key=lambda item: abs(
                    datetime.fromisoformat(str(times[item])).replace(tzinfo=UTC) - requested_hour
                ),
            )
            response["weather"] = {
                "temperature_c": (hourly.get("temperature_2m") or [None])[index],
                "precipitation_mm": (hourly.get("precipitation") or [None])[index],
                "wind_kph": (hourly.get("wind_speed_10m") or [None])[index],
                "weather_code": (hourly.get("weather_code") or [None])[index],
            }
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    return response
