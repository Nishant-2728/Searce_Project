"""
Neural Taste Profile — Zomato "Discovery Fatigue" prototype (Streamlit UI).

Dishes are scored on 14 flavor dimensions instead of cuisine tags (dishes.py),
a rule-based Context Engine turns time/mood/activity/free-text into a target
flavor vector (context_engine.py), and a Matching Engine ranks dishes by
cosine similarity against that target (matching_engine.py). This file only
wires those pieces to Streamlit widgets — no data or matching logic lives
here.

Hard constraint (unchanged from the spec): fully deterministic, no LLM/AI
API calls anywhere. Free-text parsing is plain keyword substring matching
against a hardcoded lookup table.
"""

from datetime import datetime

import streamlit as st

from charts import make_radar_chart
from context_engine import ACTIVITIES, MOODS, compute_target_vector, get_time_bucket
from dishes import DISHES
from matching_engine import explain_match, rank_dishes

st.set_page_config(page_title="Neural Taste Profile", page_icon="🍽️", layout="wide")

st.title("Neural Taste Profile")
st.caption("Flavor-vector matching, not cuisine labels — a deterministic proof-of-concept for Discovery Fatigue.")

time_bucket = get_time_bucket(datetime.now())
st.info(f"🕒 Detected context: **{time_bucket}**")

st.subheader("How are you feeling?")
mood = st.radio("Mood", MOODS, index=None, horizontal=True, label_visibility="collapsed")

st.subheader("What's going on? (pick any)")
activities = st.multiselect("Activities", ACTIVITIES, label_visibility="collapsed")

st.subheader("Craving anything specific?")
craving = st.text_input("Craving", placeholder="e.g. something crunchy and tangy", label_visibility="collapsed")

find_meal = st.button("Find My Meal", type="primary", width="stretch")

if "results" not in st.session_state:
    st.session_state.results = None

if find_meal:
    target_vector, contributions, matched_keywords = compute_target_vector(time_bucket, mood, activities, craving)
    ranked = rank_dishes(target_vector, DISHES)[:5]
    ranked_with_explanations = [
        {**entry, "explanation": explain_match(target_vector, entry["dish"], contributions)} for entry in ranked
    ]
    st.session_state.results = {
        "matched_keywords": matched_keywords,
        "ranked": ranked_with_explanations,
        "mood": mood,
        "activities": activities,
    }

results = st.session_state.results

if results:
    signals = [time_bucket]
    if results["mood"]:
        signals.append(results["mood"])
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
                        "toImageButtonOptions": {"format": "png"}
                    }
                )
                st.info(entry["explanation"])
else:
    st.markdown("_Pick a mood, add any activities, and hit **Find My Meal** to see your matches._")
