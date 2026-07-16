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
import location_client
from charts import make_radar_chart
from context_engine import QUIZ_QUESTIONS, get_time_bucket
from dishes import DISHES
from matching_engine import explain_match, rank_dishes
from profile_dialog import edit_profile_dialog, profile_summary

load_dotenv()  # populates ANTHROPIC_API_KEY from app/.env before any API call is made

st.set_page_config(page_title="Neural Taste Profile", page_icon="🍽️", layout="wide")

# Zomato-styled presentation layer — purely cosmetic, no effect on any
# widget's value or the recommendation logic below.
st.markdown(
    """
    <style>
    h1 {
        background: linear-gradient(90deg, #E23744, #FF7A59);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    .stButton > button {
        border-radius: 999px;
        font-weight: 600;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        box-shadow: 0 2px 8px rgba(226, 55, 68, 0.2);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(226, 55, 68, 0.35);
    }
    [class*="st-key-dish_card_"] {
        border-radius: 16px !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    [class*="st-key-dish_card_"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 24px rgba(226, 55, 68, 0.2);
    }
    [class*="st-key-section_"] {
        border: 2px solid #F1A7AC !important;
        border-radius: 20px !important;
        padding: 0.5rem 0.25rem !important;
        background-color: #FFFDFD;
        margin-bottom: 1.25rem;
    }
    .rank-badge {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        border-radius: 6px;
        background: #FFE3DE;
        color: #C22030;
        font-weight: 700;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
    }
    .score-badge {
        display: inline-block;
        padding: 0.3rem 0.85rem;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.9rem;
        color: white;
        background: linear-gradient(90deg, #E23744, #FF8A65);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Neural Taste Profile")

profile_col, button_col = st.columns([4, 1])
with profile_col:
    st.caption(f"🧑‍🍳 Profile: {profile_summary()}")
with button_col:
    if st.button("Edit Profile", key="edit_profile_btn", width="stretch"):
        edit_profile_dialog()

# --- Location & weather -----------------------------------------------------
with st.container(border=True, key="section_location"):
    st.subheader("📍 Where are you?")

    if "detected_location" not in st.session_state:
        st.session_state.detected_location = None
    if "weather_data" not in st.session_state:
        st.session_state.weather_data = None
    if "auto_weather_location" not in st.session_state:
        st.session_state.auto_weather_location = None
    if "auto_selected_city" not in st.session_state:
        st.session_state.auto_selected_city = None

    # Asked automatically on every load — the browser only prompts once per
    # origin and remembers the user's answer on subsequent reruns.
    location_status = geolocation_client.get_browser_location_status()
    if location_status["status"] == "success":
        detected = {"lat": location_status["lat"], "lon": location_status["lon"]}
        st.session_state.detected_location = detected
        st.session_state.location_details = location_client.get_location_details(
            detected["lat"],
            detected["lon"]
        )
        fetched_for = (detected["lat"], detected["lon"])
        if st.session_state.auto_weather_location != fetched_for:
            st.session_state.weather_data = weather_client.get_current_weather(detected["lat"], detected["lon"])
            st.session_state.auto_weather_location = fetched_for
            if st.session_state.weather_data is None:
                st.warning("Couldn't reach the weather service — continuing without a weather signal.")
    elif location_status["status"] == "denied":
        st.caption(
            "📍 Location permission denied — check the location icon in your browser's address bar "
            "(and your OS's location-services setting for this browser) and allow access, then reload. "
            "Picking a city below works in the meantime."
        )
    else:
        st.caption("📍 Waiting for browser location permission (or unavailable) — pick a city below in the meantime.")

    # When geolocation + reverse-geocoding succeeded, the dropdown's own preset
    # list (e.g. "Mumbai") would misrepresent where the user actually is — swap
    # in the detected city as the first, default-selected option instead.
    detected_city_label = None
    details = st.session_state.get("location_details")
    if details:
        detected_city_label = details["city"]

    city_options = list(weather_client.PRESET_CITIES.keys())
    if detected_city_label and detected_city_label not in city_options:
        city_options = [detected_city_label] + city_options

    # A widget's session_state value, once set, sticks across reruns even if the
    # options list changes underneath it — so adding "Marunji" as a new first
    # option doesn't by itself move the dropdown off a previously-stored
    # "Mumbai". Force it to the newly detected city, but only if the user hasn't
    # manually picked something else since the last time we auto-selected.
    if detected_city_label and st.session_state.auto_selected_city != detected_city_label:
        if st.session_state.get("city_select") in (None, st.session_state.auto_selected_city):
            st.session_state.city_select = detected_city_label
        st.session_state.auto_selected_city = detected_city_label

    city = st.selectbox("City", city_options, key="city_select")

    if city == "Custom location":
        default_lat, default_lon = next(iter(weather_client.PRESET_CITIES.values()))
        lat = st.number_input("Latitude", value=default_lat, key="custom_lat")
        lon = st.number_input("Longitude", value=default_lon, key="custom_lon")
    elif city == detected_city_label:
        lat = st.session_state.detected_location["lat"]
        lon = st.session_state.detected_location["lon"]
    else:
        lat, lon = weather_client.PRESET_CITIES[city]

    if city == detected_city_label and details:
        st.success(
            f"📍 {details['city']}, {details['state']}, {details['country']}"
        )
        st.caption(f"🕒 {details['time'].strftime('%I:%M %p')}")
        st.caption(f"🌍 {details['timezone']}")
    elif st.session_state.detected_location and not details:
        lat = st.session_state.detected_location["lat"]
        lon = st.session_state.detected_location["lon"]
        st.caption(f"📍 Using detected location ({lat:.3f}, {lon:.3f}) — couldn't resolve city/timezone.")
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
with st.container(border=True, key="section_quiz"):
    st.subheader("🎯 A few quick questions")
    quiz_answers = {}
    for q in QUIZ_QUESTIONS:
        quiz_answers[q["key"]] = st.radio(
            q["question"], q["options"], index=None, key=q["key"], horizontal=True
        )

# --- Craving -------------------------------------------------------------
with st.container(border=True, key="section_craving"):
    st.subheader("😋 Craving anything specific?")
    craving = st.text_input(
        "Craving",
        placeholder="e.g. something crunchy and tangy",
        key="craving_input",
        label_visibility="collapsed",
    )
if st.session_state.get("location_details"):
    time_bucket = get_time_bucket(
        st.session_state.location_details["time"]
    )
else:
    time_bucket = get_time_bucket(datetime.now())

st.markdown(
    f"""<div style="background-color:#FBE7E9;color:#C22030;padding:0.75rem 1rem;
    border-radius:0.5rem;font-size:0.95rem;margin-bottom:1rem;">
    🕒 Detected context: <strong>{time_bucket}</strong></div>""",
    unsafe_allow_html=True,
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
            with st.container(border=True, key=f"dish_card_{i}"):
                st.markdown(f'<span class="rank-badge">#{i + 1} MATCH</span>', unsafe_allow_html=True)
                st.markdown(f"### {dish['name']}")
                st.caption(f"🍽️ {dish['cuisine']} · ⏱️ {dish['prep_time_minutes']} min")
                st.markdown(
                    f'<span class="score-badge">{entry["score"] * 100:.1f}% similarity</span>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(make_radar_chart(dish["vector"], dish["name"]), width="stretch")
                st.info(entry["explanation"])
else:
    st.markdown("_Answer a few questions and hit **Find My Meal** to see your matches._")
