"""
Geolocation Client — reads the browser's native GPS location via
streamlit_js_eval's Geolocation API wrapper.

get_browser_location_status() is the single point of contact with the
browser's geolocation prompt for a given script run: a Streamlit custom
component's return value is tied to its `key`, and calling it twice with the
same key in one run raises StreamlitDuplicateElementKey — so callers that
want both the parsed coordinates and a reason for failure must go through
this one function rather than querying the component twice.

Never raises. Returns a dict with a "status" of:
  - "success" (plus "lat"/"lon")
  - "denied"  — the user or browser blocked the permission prompt
  - "pending" — the browser hasn't responded yet, or geolocation isn't
                supported (indistinguishable from JS's point of view)
"""

from streamlit_js_eval import get_geolocation


def get_browser_location_status(component_key="browser_geolocation"):
    try:
        result = get_geolocation(component_key=component_key)
    except (KeyError, TypeError):
        return {"status": "pending"}

    if isinstance(result, dict) and "coords" in result:
        try:
            coords = result["coords"]
            return {"status": "success", "lat": coords["latitude"], "lon": coords["longitude"]}
        except (KeyError, TypeError):
            return {"status": "pending"}

    if isinstance(result, dict) and "error" in result:
        return {"status": "denied"}

    return {"status": "pending"}
