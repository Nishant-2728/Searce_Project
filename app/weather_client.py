"""
Weather Client — fetches current weather from Open-Meteo for a lat/lon.

This is a pure I/O boundary: on any failure (network error, timeout,
unexpected response shape) get_current_weather() returns None rather than
raising, so a flaky weather call never takes down the rest of the app. The
caller (app.py) is responsible for deciding what None means for the UI.
"""

import requests

# Order matters: the first entry's coordinates are used as the default for
# the "Custom location" lat/lon inputs in app.py.
PRESET_CITIES = {
    "Mumbai": (19.076, 72.8777),
    "Delhi": (28.6139, 77.209),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Pune": (18.5204, 73.8567),
    "Custom location": None,
}

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_current_weather(lat, lon, timeout=5.0):
    """Fetches current weather for (lat, lon). Returns a dict or None on any failure."""
    try:
        response = requests.get(
            _OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,precipitation,weather_code,is_day",
                "timezone": "auto",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        current = response.json()["current"]
        return {
            "temperature_c": current["temperature_2m"],
            "precipitation_mm": current["precipitation"],
            "weather_code": current["weather_code"],
            "is_day": bool(current["is_day"]),
        }
    except (requests.RequestException, KeyError, ValueError):
        return None
