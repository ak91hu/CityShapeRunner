"""Time-aware route context with a resilient weather fallback."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import httpx

FORECAST_DAYS = 16


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _hourly_value(hourly: dict, key: str, index: int):
    values = hourly.get(key)
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _sun_altitude(latitude: float, longitude: float, when: datetime) -> float:
    """Approximate solar altitude, sufficient for a conservative daylight flag."""

    local = _as_utc(when)
    day = local.timetuple().tm_yday
    hour = local.hour + local.minute / 60 + local.second / 3600
    declination = math.radians(23.44 * math.sin(math.radians((360 / 365) * (day - 81))))
    solar_hour = math.radians(15 * (hour + longitude / 15 - 12))
    lat = math.radians(latitude)
    return math.degrees(
        math.asin(math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(declination) * math.cos(solar_hour))
    )


def time_readiness(
    latitude: float,
    longitude: float,
    when: datetime,
    *,
    now: datetime | None = None,
) -> dict:
    """Return daylight plus the exact hourly forecast for a departure."""

    departure = _as_utc(when)
    current = _as_utc(now or datetime.now(UTC))
    requested_hour = departure.replace(minute=0, second=0, microsecond=0)
    altitude = _sun_altitude(latitude, longitude, departure)
    daylight = "daylight" if altitude >= 0 else "after_dark"
    response = {
        "departure_at": departure.isoformat(),
        "daylight": daylight,
        "sun_altitude_deg": round(altitude, 1),
        "weather": None,
        "weather_status": "unavailable",
        "weather_message": "The hourly forecast is temporarily unavailable.",
        "seasonal_note": "Check temporary closures and local access rules before leaving.",
    }

    first_forecast_date = current.date()
    last_forecast_date = first_forecast_date + timedelta(days=FORECAST_DAYS - 1)
    if requested_hour.date() < first_forecast_date:
        response["weather_status"] = "past"
        response["weather_message"] = "Weather forecasts are not available for past departures."
        return response
    if requested_hour.date() > last_forecast_date:
        response["weather_status"] = "outside_forecast_window"
        response["weather_message"] = (
            f"Hourly weather is available up to {FORECAST_DAYS} days ahead. "
            "Daylight is still calculated for your selected time."
        )
        return response

    try:
        weather_response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "hourly": "temperature_2m,precipitation,weather_code,wind_speed_10m",
                "timezone": "UTC",
                "forecast_days": FORECAST_DAYS,
            },
            timeout=3.0,
        )
        weather_response.raise_for_status()
        payload = weather_response.json()
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") if isinstance(hourly, dict) else []
        if isinstance(times, list) and times:
            matching_index = next(
                (
                    index
                    for index, timestamp in enumerate(times)
                    if _as_utc(datetime.fromisoformat(str(timestamp))) == requested_hour
                ),
                None,
            )
            if matching_index is None:
                response["weather_message"] = (
                    "No hourly forecast was returned for the selected departure."
                )
                return response
            response["weather"] = {
                "forecast_at": requested_hour.isoformat(),
                "temperature_c": _hourly_value(hourly, "temperature_2m", matching_index),
                "precipitation_mm": _hourly_value(hourly, "precipitation", matching_index),
                "wind_kph": _hourly_value(hourly, "wind_speed_10m", matching_index),
                "weather_code": _hourly_value(hourly, "weather_code", matching_index),
            }
            response["weather_status"] = "available"
            response["weather_message"] = None
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return response
    return response
