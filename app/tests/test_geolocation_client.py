"""Tests for geolocation_client.py — mocked streamlit_js_eval.get_geolocation,
no real browser/JS execution."""

import geolocation_client


def test_get_browser_location_status_returns_success_with_lat_lon(monkeypatch):
    monkeypatch.setattr(
        geolocation_client,
        "get_geolocation",
        lambda component_key=None: {
            "coords": {"latitude": 40.7128, "longitude": -74.006, "accuracy": 20},
            "timestamp": 123456,
        },
    )

    assert geolocation_client.get_browser_location_status() == {
        "status": "success",
        "lat": 40.7128,
        "lon": -74.006,
    }


def test_get_browser_location_status_returns_denied_on_permission_error(monkeypatch):
    monkeypatch.setattr(
        geolocation_client,
        "get_geolocation",
        lambda component_key=None: {"error": {"code": 1, "message": "User denied Geolocation"}},
    )

    assert geolocation_client.get_browser_location_status() == {"status": "denied"}


def test_get_browser_location_status_returns_pending_when_not_yet_responded(monkeypatch):
    monkeypatch.setattr(geolocation_client, "get_geolocation", lambda component_key=None: None)

    assert geolocation_client.get_browser_location_status() == {"status": "pending"}


def test_get_browser_location_status_returns_pending_on_malformed_payload(monkeypatch):
    monkeypatch.setattr(
        geolocation_client,
        "get_geolocation",
        lambda component_key=None: {"coords": {"unexpected": "shape"}},
    )

    assert geolocation_client.get_browser_location_status() == {"status": "pending"}
