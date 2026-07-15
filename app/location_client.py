import requests
from datetime import datetime
from zoneinfo import ZoneInfo

def get_location_details(lat, lon):
    # Reverse geocoding
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/reverse",
        params={
            "latitude": lat,
            "longitude": lon,
            "language": "en",
        },
        timeout=10,
    ).json()

    city = "Unknown"
    if geo.get("results"):
        city = geo["results"][0]["name"]

    # Timezone + current local time
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
        "timezone": timezone,
        "time": local_time,
    }
