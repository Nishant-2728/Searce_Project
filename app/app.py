"""
Neural Taste Profile — Zomato "Discovery Fatigue" prototype (Streamlit UI).

Dishes are scored on 14 flavor dimensions instead of cuisine tags (dishes.py),
a rule-based Context Engine turns time/mood/activity/free-text/weather into a target
flavor vector (context_engine.py), and a Matching Engine ranks dishes by
cosine similarity against that target (matching_engine.py). This file only
wires those pieces to Streamlit widgets — no data or matching logic lives
here.

Weather is fetched from Open-Meteo API (free, no auth required) based on user
location (lat/lon or city name).
"""

from datetime import datetime

import streamlit as st

from charts import make_radar_chart
from context_engine import ACTIVITIES, MOODS, WEATHER_CONDITIONS, KEYWORD_DELTAS, compute_target_vector, get_time_bucket
from dishes import DISHES
from matching_engine import explain_match, rank_dishes
from weather_api import get_weather_by_coords, get_weather_by_city

st.set_page_config(page_title="Neural Taste Profile", page_icon="🍽️", layout="wide")

# Customize Plotly chart toolbar
st.markdown(
    """
    <style>
    [data-testid="stPlotlyChart"] > div > div > svg [data-title="Zoom"] { display: none !important; }
    [data-testid="stPlotlyChart"] > div > div > svg [data-title="Pan"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Neural Taste Profile")
st.caption("Flavor-vector matching, not cuisine labels — a deterministic proof-of-concept for Discovery Fatigue.")

time_bucket = get_time_bucket(datetime.now())
st.info(f"🕒 Detected context: **{time_bucket}**")

# Weather Section
st.subheader("Where are you? (optional)")
weather_mode = st.radio("Weather input", ["Manual", "Auto-detect by coords", "Auto-detect by city"], horizontal=True, label_visibility="collapsed")

weather = None
weather_info = None

if weather_mode == "Manual":
    weather = st.radio("Weather", WEATHER_CONDITIONS, index=None, horizontal=True, label_visibility="collapsed")

elif weather_mode == "Auto-detect by coords":
    col1, col2 = st.columns(2)
    with col1:
        lat = st.text_input("Latitude (e.g., 28.6139)", value="")
    with col2:
        lon = st.text_input("Longitude (e.g., 77.2090)", value="")
    
    if st.button("Fetch Weather by Coordinates"):
        if lat and lon:
            try:
                weather, weather_info = get_weather_by_coords(float(lat), float(lon))
                if weather:
                    st.success(f"✅ Weather detected: **{weather}**")
                    if weather_info:
                        st.caption(f"Temp: {weather_info.get('temperature')}°C, Humidity: {weather_info.get('humidity')}%")
                else:
                    st.warning("❌ Could not determine weather from coordinates. Please try manual selection.")
            except ValueError:
                st.error("❌ Please enter valid latitude and longitude numbers.")
        else:
            st.error("❌ Please enter both latitude and longitude.")

elif weather_mode == "Auto-detect by city":
    city = st.text_input("City name (e.g., Delhi, New York)", placeholder="Enter your city...")
    
    if st.button("Fetch Weather by City"):
        if city:
            weather, weather_info = get_weather_by_city(city)
            if weather:
                st.success(f"✅ Weather detected: **{weather}**")
                if weather_info:
                    st.caption(f"{weather_info.get('city_display')} | Temp: {weather_info.get('temperature')}°C")
            else:
                st.warning(f"❌ Could not fetch weather for '{city}'. Please try another city or use manual selection.")
        else:
            st.error("❌ Please enter a city name.")

st.subheader("How are you feeling?")
mood = st.radio("Mood", MOODS, index=None, horizontal=True, label_visibility="collapsed")

st.subheader("What's going on? (pick any)")
activities = st.multiselect("Activities", ACTIVITIES, label_visibility="collapsed")

st.subheader("Craving anything specific?")
craving_keywords = st.multiselect(
    "Craving",
    sorted(KEYWORD_DELTAS.keys()),
    label_visibility="collapsed",
    placeholder="e.g. spicy, tangy, fresh, crunchy..."
)
# Convert list of keywords back to space-separated string for the engine
craving = " ".join(craving_keywords)

find_meal = st.button("Find My Meal", type="primary", use_container_width=True)

if "results" not in st.session_state:
    st.session_state.results = None

if find_meal:
    target_vector, contributions, matched_keywords = compute_target_vector(time_bucket, mood, activities, craving, weather=weather)
    ranked = rank_dishes(target_vector, DISHES)[:5]
    ranked_with_explanations = [
        {**entry, "explanation": explain_match(target_vector, entry["dish"], contributions)} for entry in ranked
    ]
    st.session_state.results = {
        "matched_keywords": matched_keywords,
        "ranked": ranked_with_explanations,
        "mood": mood,
        "activities": activities,
        "weather": weather,
    }

results = st.session_state.results

if results:
    signals = [time_bucket]
    if results["mood"]:
        signals.append(results["mood"])
    if results["weather"]:
        signals.append(results["weather"])
    signals.extend(results["activities"])
    signal_line = ", ".join(signals)
    if results["matched_keywords"]:
        signal_line += f", keywords: {', '.join(repr(k) for k in results['matched_keywords'])}"
    st.markdown(f"**Signals used:** {signal_line}")

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
                st.plotly_chart(
                    make_radar_chart(dish["vector"], dish["name"]),
                    use_container_width=True,
                    config={
                        "displayModeBar": True,
                        "modeBarButtonsToRemove": ["zoom2d", "pan2d", "lasso2d"],
                        "toImageButtonOptions": {"format": "png"},
                        "displaylogo": False
                    }
                )
                st.info(entry["explanation"])
else:
    st.markdown("_Enter your location (optional), pick a mood, add any activities, select cravings, and hit **Find My Meal** to see your matches._")
