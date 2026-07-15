"""
Geolocation Client — reads the browser's native GPS location via
streamlit_js_eval's Geolocation API wrapper.

This is a pure I/O boundary, same shape as weather_client.py: on any failure
(permission denied, unsupported browser, not yet responded, malformed
result) get_browser_location() returns None rather than raising, so a
rejected/pending location prompt never takes down the rest of the app. The
caller (app.py) is responsible for deciding what None means for the UI.
"""

from streamlit_js_eval import get_geolocation


def get_browser_location(component_key="browser_geolocation"):
    """Reads the browser's detected GPS location. Returns {"lat", "lon"} or
    None if the browser hasn't responded yet, permission was denied, or
    geolocation isn't supported."""
    try:
        result = get_geolocation(component_key=component_key)
        if not result or "coords" not in result:
            return None
        coords = result["coords"]
        return {"lat": coords["latitude"], "lon": coords["longitude"]}
    except (KeyError, TypeError):
        return None
