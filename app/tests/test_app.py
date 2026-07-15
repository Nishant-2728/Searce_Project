"""
Integration tests for app.py, driven through Streamlit's official AppTest
harness (streamlit.testing.v1) — runs the real UI script headlessly, without
a browser, and lets us click/type/select exactly like a user would.

None of these tests make a real Claude API call or a real weather call.
`llm_context_engine.get_target_vector` (or, for one test, just its
`_get_client` seam) is monkeypatched — the real LLM path isn't reproducible
in CI, so exact-value assertions are always made against a forced
deterministic path instead.
"""

from datetime import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

import geolocation_client
import llm_context_engine
import weather_client
from context_engine import get_time_bucket
from dishes import DIMENSIONS, DISHES
from matching_engine import rank_dishes

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def _fake_get_target_vector(vector=None, rationale=None, source="fallback", error="forced for test"):
    """Builds a fake replacement for llm_context_engine.get_target_vector."""
    base_vector = {dim: 5 for dim in DIMENSIONS}
    if vector:
        base_vector.update(vector)
    base_rationale = {dim: f"stub rationale for {dim}" for dim in DIMENSIONS}
    if rationale:
        base_rationale.update(rationale)

    def _fake(payload):
        return llm_context_engine.ContextResult(
            base_vector, base_rationale, source=source, error=None if source == "llm" else error
        )

    return _fake


def test_app_runs_without_raising():
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception


def test_default_state_shows_empty_state_prompt():
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert any("Find My Meal" in m.value for m in at.markdown)
    # No quiz question is pre-answered.
    assert at.radio(key="energy_level").value is None


def test_find_my_meal_with_no_selections_still_returns_five_results(monkeypatch):
    monkeypatch.setattr(llm_context_engine, "get_target_vector", _fake_get_target_vector())
    at = AppTest.from_file(APP_PATH)
    at.run()
    at.button(key="find_meal_btn").click().run()
    assert not at.exception
    assert sum(1 for m in at.markdown if m.value.startswith("### ")) == 5


def test_fallback_banner_appears_when_llm_call_fails(monkeypatch):
    monkeypatch.setattr(
        llm_context_engine,
        "get_target_vector",
        _fake_get_target_vector(source="fallback", error="simulated outage"),
    )
    at = AppTest.from_file(APP_PATH)
    at.run()
    at.button(key="find_meal_btn").click().run()

    assert not at.exception
    assert any("fallback" in w.value.lower() for w in at.warning)
    # The raw error is surfaced in the debug expander, not hidden.
    assert any("simulated outage" in c.value for c in at.code)


def test_mocked_happy_path_shows_no_fallback_banner_and_surfaces_llm_rationale(monkeypatch):
    # An all-zero vector except spice guarantees explain_match's top dimension
    # is deterministically "spice" for every result (any other dimension's
    # target*dish product is 0), so the LLM-authored rationale is guaranteed
    # to surface regardless of exactly which 5 dishes rank highest.
    vector = {dim: 0 for dim in DIMENSIONS}
    vector["spice"] = 10
    rationale = {dim: f"stub rationale for {dim}" for dim in DIMENSIONS}
    rationale["spice"] = "You wanted something bold and intense, so spice leads."

    monkeypatch.setattr(
        llm_context_engine,
        "get_target_vector",
        _fake_get_target_vector(vector=vector, rationale=rationale, source="llm"),
    )
    at = AppTest.from_file(APP_PATH)
    at.run()
    at.button(key="find_meal_btn").click().run()

    assert not at.exception
    assert not any("fallback" in w.value.lower() for w in at.warning)
    assert any("bold and intense" in m.value for m in at.info)


def test_full_scenario_matches_expected_top_result_on_the_forced_fallback_path(monkeypatch):
    """Forces the fallback path (by making the API client unreachable) so the
    expected top result can be computed independently, the same way
    test_llm_context_engine.py does — the real LLM path isn't reproducible in
    CI, so this exercises the actual fallback code path rather than a fake."""

    def _raising_get_client():
        raise RuntimeError("no network in tests")

    monkeypatch.setattr(llm_context_engine, "_get_client", _raising_get_client)

    at = AppTest.from_file(APP_PATH)
    at.run()

    at.radio(key="energy_level").set_value("High")
    at.radio(key="notable_activity").set_value("Just worked out")
    at.text_input(key="craving_input").set_value("something crunchy and tangy")
    at.button(key="find_meal_btn").click().run()

    assert not at.exception
    markdown_values = [m.value for m in at.markdown]
    signals_line = next(v for v in markdown_values if v.startswith("**Signals used:**"))
    assert "High" in signals_line
    assert "Just worked out" in signals_line
    assert "crunchy and tangy" in signals_line

    time_bucket = get_time_bucket(datetime.now())
    expected_vector, _ = llm_context_engine._fallback_vector_and_rationale(
        time_bucket,
        {"energy_level": "High", "notable_activity": "Just worked out"},
        "something crunchy and tangy",
    )
    ranked = rank_dishes(expected_vector, DISHES)
    top_entry = ranked[0]

    assert any(top_entry["dish"]["name"] in v for v in markdown_values)
    assert any(f"{top_entry['score'] * 100:.1f}% similarity" in v for v in markdown_values)


def test_results_persist_across_an_unrelated_rerun(monkeypatch):
    """Changing the craving text after clicking Find My Meal should not
    wipe the previously computed results (they live in st.session_state)."""
    monkeypatch.setattr(llm_context_engine, "get_target_vector", _fake_get_target_vector())
    at = AppTest.from_file(APP_PATH)
    at.run()

    at.radio(key="energy_level").set_value("High")
    at.button(key="find_meal_btn").click().run()
    assert any("### " in m.value for m in at.markdown)

    # Simulate the user typing in the craving box without clicking the
    # button again — a plain rerun, not a new search.
    at.text_input(key="craving_input").set_value("just browsing").run()

    assert not at.exception
    assert any("Signals used" in m.value for m in at.markdown)
    assert sum(1 for m in at.markdown if m.value.startswith("### ")) == 5


def test_different_inputs_produce_different_top_results(monkeypatch):
    def top_result_names(vector_overrides):
        monkeypatch.setattr(
            llm_context_engine,
            "get_target_vector",
            _fake_get_target_vector(vector=vector_overrides, source="llm"),
        )
        at = AppTest.from_file(APP_PATH)
        at.run()
        at.button(key="find_meal_btn").click().run()
        assert not at.exception
        return [m.value for m in at.markdown if m.value.startswith("### ")]

    spicy_results = top_result_names({"spice": 10, "crunch": 10})
    sweet_results = top_result_names({"sweetness": 10, "richness": 10})

    assert spicy_results != sweet_results


def test_geolocation_success_auto_fetches_weather_on_load(monkeypatch):
    weather_calls = []
    monkeypatch.setattr(
        geolocation_client,
        "get_browser_location",
        lambda: {"lat": 40.7128, "lon": -74.006},
    )

    def _fake_weather(lat, lon, timeout=5.0):
        weather_calls.append((lat, lon))
        return {"temperature_c": 22.5, "precipitation_mm": 0.0, "weather_code": 2, "is_day": True}

    monkeypatch.setattr(weather_client, "get_current_weather", _fake_weather)

    at = AppTest.from_file(APP_PATH)
    at.run()

    assert not at.exception
    assert at.session_state["detected_location"] == {"lat": 40.7128, "lon": -74.006}
    assert at.session_state["weather_data"]["temperature_c"] == 22.5
    assert weather_calls == [(40.7128, -74.006)]
    assert any("40.713" in c.value for c in at.caption)


def test_geolocation_failure_falls_back_to_manual_dropdown(monkeypatch):
    monkeypatch.setattr(geolocation_client, "get_browser_location", lambda: None)
    at = AppTest.from_file(APP_PATH)
    at.run()

    assert not at.exception
    assert at.session_state["detected_location"] is None
    assert at.session_state["weather_data"] is None
    assert any("Waiting for browser location permission" in c.value for c in at.caption)


def test_detected_location_and_weather_persist_across_an_unrelated_rerun(monkeypatch):
    weather_calls = []
    monkeypatch.setattr(
        geolocation_client,
        "get_browser_location",
        lambda: {"lat": 40.7128, "lon": -74.006},
    )

    def _fake_weather(lat, lon, timeout=5.0):
        weather_calls.append((lat, lon))
        return {"temperature_c": 22.5, "precipitation_mm": 0.0, "weather_code": 2, "is_day": True}

    monkeypatch.setattr(weather_client, "get_current_weather", _fake_weather)

    at = AppTest.from_file(APP_PATH)
    at.run()
    assert at.session_state["detected_location"] == {"lat": 40.7128, "lon": -74.006}

    # Toggling an unrelated widget reruns the whole script; the guard should
    # stop it from re-fetching weather for the same detected coordinates.
    at.text_input(key="craving_input").set_value("still hungry").run()

    assert not at.exception
    assert at.session_state["detected_location"] == {"lat": 40.7128, "lon": -74.006}
    assert at.session_state["weather_data"]["temperature_c"] == 22.5
    assert weather_calls == [(40.7128, -74.006)]


def test_vegetarian_preference_excludes_non_veg_dish_from_results(monkeypatch):
    # Butter Chicken is non-vegetarian. Force the target vector to exactly
    # match its flavor vector so it would rank #1 by similarity alone —
    # the hard filter must still remove it before matching ever runs.
    butter_chicken = next(d for d in DISHES if d["id"] == "butter-chicken")
    monkeypatch.setattr(
        llm_context_engine,
        "get_target_vector",
        _fake_get_target_vector(vector=dict(butter_chicken["vector"]), source="llm"),
    )

    at = AppTest.from_file(APP_PATH)
    at.run()

    # Seeding session_state before the dialog's first render is the documented
    # way to preset a widget's initial value.
    at.session_state["dietary_preference"] = "Vegetarian"
    at.button(key="edit_profile_btn").click().run()

    at.button(key="find_meal_btn").click().run()

    assert not at.exception
    markdown_values = [m.value for m in at.markdown]
    assert not any("Butter Chicken" in v for v in markdown_values)
    assert any("Excluded" in v and "not vegetarian" in v for v in (c.value for c in at.caption))


def test_smartwatch_biometrics_sourced_from_profile_page(monkeypatch):
    captured_payloads = []
    real_build_context_payload = llm_context_engine.build_context_payload

    def _spy_build_context_payload(*args, **kwargs):
        captured_payloads.append(args)
        return real_build_context_payload(*args, **kwargs)

    monkeypatch.setattr(llm_context_engine, "build_context_payload", _spy_build_context_payload)
    monkeypatch.setattr(llm_context_engine, "get_target_vector", _fake_get_target_vector())

    at = AppTest.from_file(APP_PATH)
    at.run()

    at.session_state["smartwatch_connected"] = True
    at.session_state["hrv"] = 90
    at.session_state["calories_burned"] = 500
    at.session_state["sleep_score"] = 85
    at.button(key="edit_profile_btn").click().run()

    at.button(key="find_meal_btn").click().run()

    assert not at.exception
    biometrics_arg = captured_payloads[0][2]
    assert biometrics_arg == {"hrv": 90, "calories_burned": 500, "sleep_score": 85}


def test_profile_defaults_when_never_visited(monkeypatch):
    monkeypatch.setattr(llm_context_engine, "get_target_vector", _fake_get_target_vector())
    at = AppTest.from_file(APP_PATH)
    at.run()

    at.button(key="find_meal_btn").click().run()

    assert not at.exception
    assert sum(1 for m in at.markdown if m.value.startswith("### ")) == 5
    assert not any("Excluded" in c.value for c in at.caption)


def test_edit_profile_dialog_opens_and_shows_current_values():
    at = AppTest.from_file(APP_PATH)
    at.run()

    at.button(key="edit_profile_btn").click().run()

    assert not at.exception
    assert at.radio(key="dietary_preference").value == "Non-vegetarian"
    assert at.multiselect(key="allergies").value == []
    assert at.checkbox(key="smartwatch_connected").value is False
