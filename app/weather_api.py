"""
Weather API client — fetches real-time weather and maps to flavor contexts.

Uses Open-Meteo (free, no API key required) to get current weather by lat/lon,
then maps weather codes to our WEATHER_CONDITIONS for context engine integration.
"""

import requests
from typing import Tuple, Optional

# WMO Weather Interpretation codes
# https://www.open-meteo.com/en/docs
WEATHER_CODE_MAP = {
    0: "Sunny",           # Clear sky
    1: "Sunny",           # Mainly clear
    2: "Cloudy",          # Partly cloudy
    3: "Cloudy",          # Overcast
    45: "Cloudy",         # Foggy
    48: "Cloudy",         # Foggy rime
    51: "Rainy",          # Light drizzle
    53: "Rainy",          # Moderate drizzle
    55: "Rainy",          # Dense drizzle
    61: "Rainy",          # Slight rain
    63: "Rainy",          # Moderate rain
    65: "Rainy",          # Heavy rain
    71: "Rainy",          # Slight snow
    73: "Rainy",          # Moderate snow
    75: "Rainy",          # Heavy snow
    77: "Rainy",          # Snow grains
    80: "Rainy",          # Slight rain showers
    81: "Rainy",          # Moderate rain showers
    82: "Rainy",          # Violent rain showers
    85: "Rainy",          # Slight snow showers
    86: "Rainy",          # Heavy snow showers
    95: "Rainy",          # Thunderstorm
    96: "Rainy",          # Thunderstorm with slight hail
    97: "Rainy",          # Thunderstorm with heavy hail
}


def map_temperature_to_weather(temperature: float) -> Optional[str]:
    """
    Maps temperature (°C) to a weather condition.
    Refined based on local conditions.
    """
    if temperature > 32:
        return "Hot"
    elif temperature < 5:
        return "Cold"
    return None


def get_weather_by_coords(latitude: float, longitude: float) -> Tuple[Optional[str], dict]:
    """
    Fetches current weather from Open-Meteo API and maps to flavor context.

    Args:
        latitude: User's latitude (e.g., 28.6139 for Delhi)
        longitude: User's longitude (e.g., 77.2090 for Delhi)

    Returns:
        Tuple of (weather_condition, raw_data)
        - weather_condition: one of WEATHER_CONDITIONS or None if API fails
        - raw_data: dict with temperature, weather_code, etc. for debugging
    """
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitude}&longitude={longitude}"
            f"&current=weather_code,temperature_2m,relative_humidity_2m"
            f"&timezone=auto"
        )
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        current = data.get("current", {})
        weather_code = current.get("weather_code")
        temperature = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m", 0)

        raw_data = {
            "temperature": temperature,
            "weather_code": weather_code,
            "humidity": humidity,
            "location": f"{latitude}, {longitude}",
        }

        # Map weather code first (highest priority)
        if weather_code is not None:
            weather = WEATHER_CODE_MAP.get(weather_code)
            if weather:
                return weather, raw_data

        # Fall back to temperature-based mapping
        if temperature is not None:
            weather = map_temperature_to_weather(temperature)
            if weather:
                return weather, raw_data

        # If both fail, return None
        return None, raw_data

    except requests.exceptions.RequestException as e:
        return None, {"error": str(e), "latitude": latitude, "longitude": longitude}


def get_weather_by_city(city_name: str) -> Tuple[Optional[str], dict]:
    """
    Fetches weather by city name using geocoding (slower, optional fallback).

    Args:
        city_name: e.g., "Delhi", "New York", "London"

    Returns:
        Tuple of (weather_condition, raw_data)
    """
    try:
        # First, geocode the city name
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=en&format=json"
        geo_response = requests.get(geo_url, timeout=5)
        geo_response.raise_for_status()
        geo_data = geo_response.json()

        results = geo_data.get("results", [])
        if not results:
            return None, {"error": f"City '{city_name}' not found"}

        location = results[0]
        lat = location.get("latitude")
        lon = location.get("longitude")
        city_display = f"{location.get('name')}, {location.get('country')}"

        # Now fetch weather for those coords
        weather, raw = get_weather_by_coords(lat, lon)
        raw["city_display"] = city_display
        return weather, raw

    except requests.exceptions.RequestException as e:
        return None, {"error": str(e), "city": city_name}
