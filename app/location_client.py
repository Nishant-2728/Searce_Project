import requests
from datetime import datetime
from zoneinfo import ZoneInfo


def get_location_details(lat, lon):
    # Reverse geocoding
    geo = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
        },
        headers={
            "User-Agent": "NeuralTasteProfile/1.0"
        },
        timeout=10,
    ).json()

    address = geo.get("address", {})

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
    # Get timezone
    weather = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m",
            "timezone": "auto",
        },
        timeout=10,
    ).json()

    timezone = weather["timezone"]

    local_time = datetime.now(ZoneInfo(timezone))

    return {
    "city": city,
    "state": state,
    "country": country,
    "timezone": timezone,
    "time": local_time,
    }
