"""Tests for geolocation_client.py — mocked streamlit_js_eval.get_geolocation,
no real browser/JS execution."""

import geolocation_client


def test_get_browser_location_returns_lat_lon_on_success(monkeypatch):
    monkeypatch.setattr(
        geolocation_client,
        "get_geolocation",
        lambda component_key=None: {
            "coords": {"latitude": 40.7128, "longitude": -74.006, "accuracy": 20},
            "timestamp": 123456,
        },
    )

    assert geolocation_client.get_browser_location() == {"lat": 40.7128, "lon": -74.006}


def test_get_browser_location_returns_none_on_permission_denied(monkeypatch):
    monkeypatch.setattr(
        geolocation_client,
        "get_geolocation",
        lambda component_key=None: {"error": {"code": 1, "message": "User denied Geolocation"}},
    )

    assert geolocation_client.get_browser_location() is None


def test_get_browser_location_returns_none_when_pending(monkeypatch):
    monkeypatch.setattr(geolocation_client, "get_geolocation", lambda component_key=None: None)

    assert geolocation_client.get_browser_location() is None


def test_get_browser_location_returns_none_on_malformed_payload(monkeypatch):
    monkeypatch.setattr(
        geolocation_client,
        "get_geolocation",
        lambda component_key=None: {"coords": {"unexpected": "shape"}},
    )

    assert geolocation_client.get_browser_location() is None
