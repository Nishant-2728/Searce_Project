"""Tests for location_client.py — mocked requests.get, no real network calls."""

import requests

import location_client
from location_client import get_location_details


class _FakeResponse:
    def __init__(self, json_data, status_ok=True):
        self._json_data = json_data
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise requests.exceptions.HTTPError("bad status")

    def json(self):
        return self._json_data


_NOMINATIM_PAYLOAD = {
    "address": {
        "city": "Pune",
        "state": "Maharashtra",
        "country": "India",
    }
}
_OPEN_METEO_PAYLOAD = {"timezone": "Asia/Kolkata"}


def _fake_get(nominatim_payload=_NOMINATIM_PAYLOAD, open_meteo_payload=_OPEN_METEO_PAYLOAD, fail_on=None):
    def _get(url, *args, **kwargs):
        if url == location_client._NOMINATIM_URL:
            if fail_on == "nominatim":
                raise requests.exceptions.ConnectionError("no network")
            return _FakeResponse(nominatim_payload)
        if fail_on == "open_meteo":
            raise requests.exceptions.ConnectionError("no network")
        return _FakeResponse(open_meteo_payload)

    return _get


def test_get_location_details_returns_parsed_dict_on_success(monkeypatch):
    monkeypatch.setattr(requests, "get", _fake_get())

    result = get_location_details(18.5204, 73.8567)

    assert result["city"] == "Pune"
    assert result["state"] == "Maharashtra"
    assert result["country"] == "India"
    assert result["timezone"] == "Asia/Kolkata"
    assert result["time"].tzinfo is not None


def test_get_location_details_falls_back_through_address_fields(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        _fake_get(nominatim_payload={"address": {"county": "Some County", "country": "India"}}),
    )

    result = get_location_details(18.5204, 73.8567)

    assert result["city"] == "Some County"
    assert result["state"] == "Unknown"


def test_get_location_details_returns_none_on_nominatim_failure(monkeypatch):
    monkeypatch.setattr(requests, "get", _fake_get(fail_on="nominatim"))

    assert get_location_details(18.5204, 73.8567) is None


def test_get_location_details_returns_none_on_open_meteo_failure(monkeypatch):
    monkeypatch.setattr(requests, "get", _fake_get(fail_on="open_meteo"))

    assert get_location_details(18.5204, 73.8567) is None


def test_get_location_details_returns_none_on_malformed_payload(monkeypatch):
    monkeypatch.setattr(requests, "get", _fake_get(open_meteo_payload={"unexpected": "shape"}))

    assert get_location_details(18.5204, 73.8567) is None
