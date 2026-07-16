"""
Location Client — reverse-geocodes a lat/lon into a city/state/country plus
the correct local timezone, so time-of-day context reflects where the user
actually is instead of the server's clock.

Same never-raise contract as weather_client.get_current_weather and
geolocation_client.get_browser_location: on any failure (network error,
timeout, unexpected response shape) get_location_details() returns None
rather than raising. The caller (app.py) is responsible for deciding what
None means for the UI.
"""

from datetime import datetime

import requests
from zoneinfo import ZoneInfo

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_location_details(lat, lon, timeout=10.0):
    """Reverse-geocodes (lat, lon) into city/state/country/timezone/local time.

    Returns a dict or None on any failure.
    """
    try:
        geo_response = requests.get(
            _NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "jsonv2"},
            headers={"User-Agent": "NeuralTasteProfile/1.0"},
            timeout=timeout,
        )
        geo_response.raise_for_status()
        address = geo_response.json().get("address", {})

        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("county")
            or "Unknown"
        )
        state = address.get("state", "Unknown")
        country = address.get("country", "Unknown")

        weather_response = requests.get(
            _OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m",
                "timezone": "auto",
            },
            timeout=timeout,
        )
        weather_response.raise_for_status()
        timezone = weather_response.json()["timezone"]
        local_time = datetime.now(ZoneInfo(timezone))

        return {
            "city": city,
            "state": state,
            "country": country,
            "timezone": timezone,
            "time": local_time,
        }
    except (requests.RequestException, KeyError, ValueError):
        return None
