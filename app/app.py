"""
Neural Taste Profile — Zomato "Discovery Fatigue" prototype (Streamlit UI).

Dishes are scored on 14 flavor dimensions instead of cuisine tags (dishes.py).
Real-time context — location/weather (weather_client.py), biometrics from the
Profile dialog, a short mood quiz (context_engine.py), and a free-text
craving — is fused into a target flavor vector by a single Claude API call
(llm_context_engine.py), which also returns a per-dimension rationale so the
match is never a black box. Before ranking, dietary_filter.py hard-excludes
any dish that violates the user's stored dietary/allergy/health constraints
(set up via the Profile dialog, profile_dialog.py), then applies a soft
score penalty for risk-based health conditions within that already-safe
set. A Matching Engine ranks the remaining dishes by cosine similarity
against the target (matching_engine.py). This file only wires those pieces
to Streamlit widgets — no data, fusion, filtering, or matching logic lives
here.

The LLM's role is scoped strictly to producing the target vector + rationale
from context. Dish data, dietary filtering, cosine similarity, and ranking
remain plain deterministic code. If the LLM call fails for any reason, a
deterministic fallback vector is used instead and clearly signaled in the
UI — see llm_context_engine.get_target_vector().
"""

from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

import dietary_filter
import geolocation_client
import llm_context_engine
import weather_client
from charts import make_radar_chart
from context_engine import QUIZ_QUESTIONS, get_time_bucket
from dishes import DISHES
from matching_engine import explain_match, rank_dishes
from profile_dialog import edit_profile_dialog, profile_summary

load_dotenv()  # populates ANTHROPIC_API_KEY from app/.env before any API call is made

st.set_page_config(page_title="Neural Taste Profile", page_icon="🍽️", layout="wide")

st.title("Neural Taste Profile")
st.caption(
    "Real-time context — weather, biometrics, a mood quiz, and a free-text craving — "
    "fused by Claude into a target flavor vector, then matched against your safe dishes by cosine similarity."
)

profile_col, button_col = st.columns([4, 1])
with profile_col:
    st.caption(f"🧑‍🍳 Profile: {profile_summary()}")
with button_col:
    if st.button("Edit Profile", key="edit_profile_btn", width="stretch"):
        edit_profile_dialog()

time_bucket = get_time_bucket(datetime.now())
st.info(f"🕒 Detected context: **{time_bucket}**")

# --- Location & weather -----------------------------------------------------
st.subheader("Where are you?")

if "detected_location" not in st.session_state:
    st.session_state.detected_location = None
if "weather_data" not in st.session_state:
    st.session_state.weather_data = None
if "auto_weather_location" not in st.session_state:
    st.session_state.auto_weather_location = None

# Asked automatically on every load — the browser only prompts once per
# origin and remembers the user's answer on subsequent reruns.
detected = geolocation_client.get_browser_location()
if detected:
    st.session_state.detected_location = detected
    fetched_for = (detected["lat"], detected["lon"])
    if st.session_state.auto_weather_location != fetched_for:
        st.session_state.weather_data = weather_client.get_current_weather(detected["lat"], detected["lon"])
        st.session_state.auto_weather_location = fetched_for
        if st.session_state.weather_data is None:
            st.warning("Couldn't reach the weather service — continuing without a weather signal.")
else:
    st.caption("📍 Waiting for browser location permission (or unavailable) — pick a city below in the meantime.")

city = st.selectbox("City", list(weather_client.PRESET_CITIES.keys()), key="city_select")

if city == "Custom location":
    default_lat, default_lon = next(iter(weather_client.PRESET_CITIES.values()))
    lat = st.number_input("Latitude", value=default_lat, key="custom_lat")
    lon = st.number_input("Longitude", value=default_lon, key="custom_lon")
else:
    lat, lon = weather_client.PRESET_CITIES[city]

if st.session_state.detected_location:
    lat, lon = st.session_state.detected_location["lat"], st.session_state.detected_location["lon"]
    st.caption(f"📍 Using detected location ({lat:.3f}, {lon:.3f}) — weather auto-fetched.")

if st.button("Check Weather", key="check_weather_btn"):
    st.session_state.weather_data = weather_client.get_current_weather(lat, lon)
    if st.session_state.weather_data is None:
        st.warning("Couldn't reach the weather service — continuing without a weather signal.")

if st.session_state.weather_data:
    w = st.session_state.weather_data
    st.caption(f"🌡️ {w['temperature_c']}°C · weather code {w['weather_code']}")

# --- Biometrics (from Profile dialog) ----------------------------------------
biometrics = None
if st.session_state.get("smartwatch_connected"):
    biometrics = {
        "hrv": st.session_state.get("hrv", 60),
        "calories_burned": st.session_state.get("calories_burned", 300),
        "sleep_score": st.session_state.get("sleep_score", 70),
    }
else:
    st.caption("⌚ No smartwatch connected — set this up via Edit Profile.")

# --- Mood quiz ---------------------------------------------------------------
st.subheader("A few quick questions")
quiz_answers = {}
for q in QUIZ_QUESTIONS:
    quiz_answers[q["key"]] = st.radio(
        q["question"], q["options"], index=None, key=q["key"], horizontal=True
    )

# --- Craving -------------------------------------------------------------
st.subheader("Craving anything specific?")
craving = st.text_input(
    "Craving",
    placeholder="e.g. something crunchy and tangy",
    key="craving_input",
    label_visibility="collapsed",
)

find_meal = st.button("Find My Meal", type="primary", width="stretch", key="find_meal_btn")

if "results" not in st.session_state:
    st.session_state.results = None

if find_meal:
    with st.spinner("Reading the vibe..."):
        payload = llm_context_engine.build_context_payload(
            time_bucket, st.session_state.weather_data, biometrics, quiz_answers, craving
        )
        result = llm_context_engine.get_target_vector(payload)

    profile = {
        "dietary_preference": st.session_state.get("dietary_preference", "Non-vegetarian"),
        "allergies": st.session_state.get("allergies", []),
        "health_conditions": st.session_state.get("health_conditions", []),
    }
    # Hard constraints are enforced as a pre-filter before similarity search —
    # the vector engine never sees disallowed dishes as candidates, so no
    # similarity score can override a hard rule.
    allowed, exclusion_report = dietary_filter.apply_hard_filters(DISHES, profile)
    ranked = rank_dishes(result.vector, allowed)
    ranked = dietary_filter.apply_soft_penalties(ranked, profile)[:5]
    ranked_with_explanations = [
        {**entry, "explanation": explain_match(result.vector, entry["dish"], result.rationale)}
        for entry in ranked
    ]
    st.session_state.results = {
        "ranked": ranked_with_explanations,
        "used_fallback": result.source == "fallback",
        "fallback_error": result.error,
        "weather_used": st.session_state.weather_data is not None,
        "quiz_answers": quiz_answers,
        "craving": craving,
        "exclusion_report": exclusion_report,
    }

results = st.session_state.results

if results:
    if results["used_fallback"]:
        st.warning(
            "Using fallback — AI service unavailable. Recommendations are based on a "
            "simplified deterministic baseline, not full context fusion."
        )
        with st.expander("Why fallback?"):
            st.code(results["fallback_error"] or "Unknown error")

    signals = [time_bucket]
    if results["weather_used"]:
        signals.append("weather")
    signals.extend(a for a in results["quiz_answers"].values() if a)
    if results["craving"]:
        signals.append(f'craving: "{results["craving"]}"')
    st.markdown(f"**Signals used:** {', '.join(signals)}")

    report = results["exclusion_report"]
    if report["total_excluded"]:
        reason_bits = ", ".join(f"{count} {reason}" for reason, count in report["by_reason"].items())
        st.caption(f"🚫 Excluded {report['total_excluded']} dish(es) before matching — {reason_bits}.")

    st.divider()

    columns = st.columns(2)
    for i, entry in enumerate(results["ranked"]):
        dish = entry["dish"]
        with columns[i % 2]:
            with st.container(border=True):
                st.caption(f"#{i + 1} MATCH")
                st.markdown(f"### {dish['name']}")
                st.caption(f"{dish['cuisine']} · {dish['prep_time_minutes']} min")
                st.markdown(f":green[{entry['score'] * 100:.1f}% similarity]")
                st.plotly_chart(make_radar_chart(dish["vector"], dish["name"]), width="stretch")
                st.info(entry["explanation"])
else:
    st.markdown("_Answer a few questions and hit **Find My Meal** to see your matches._")
