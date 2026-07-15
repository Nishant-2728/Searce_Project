"""
Profile dialog — the single place a user sets up dietary preference,
allergies, health conditions, and (simulated) smartwatch biometrics, instead
of re-entering them on every visit to the recommendation flow. Opened from
app.py via an "Edit Profile" button.

Dialog widgets are not page-scoped (unlike st.Page/st.navigation pages in
this Streamlit version, where a widget's session_state gets dropped the
moment you navigate away from the page that renders it) — a dialog's
page_script_hash never changes when it opens or closes, so a widget's own
`key=` behaves like any ordinary single-page widget key and persists in
st.session_state normally. Every field below is therefore read/written
directly under its widget's own key, with no shadow/copy-back indirection.

Session-level only — no database, by design (out of scope for this
prototype).
"""

import streamlit as st

import dietary_filter

DIETARY_OPTIONS = ["Non-vegetarian", "Vegetarian", "Vegan"]


def profile_summary() -> str:
    """One-line caption summarizing the current profile, shown next to the
    "Edit Profile" button so the user has visibility without opening it."""
    pref = st.session_state.get("dietary_preference", DIETARY_OPTIONS[0])
    n_allergies = len(st.session_state.get("allergies", []))
    n_conditions = len(st.session_state.get("health_conditions", []))
    bits = [pref]
    if n_allergies:
        bits.append(f"{n_allergies} allerg{'y' if n_allergies == 1 else 'ies'}")
    if n_conditions:
        bits.append(f"{n_conditions} condition{'s' if n_conditions != 1 else ''}")
    return " · ".join(bits)


@st.dialog("Edit Profile", width="large")
def edit_profile_dialog() -> None:
    st.caption(
        "Set this up once. The recommendation page reads your dietary "
        "preference, allergies, health conditions, and biometrics from here "
        "instead of asking every time."
    )

    st.subheader("Dietary preference")
    st.radio(
        "Choose your dietary preference",
        DIETARY_OPTIONS,
        index=DIETARY_OPTIONS.index(st.session_state.get("dietary_preference", DIETARY_OPTIONS[0])),
        key="dietary_preference",
        horizontal=True,
    )

    st.subheader("Allergies")
    st.multiselect(
        "Select any allergies",
        options=dietary_filter.ALLERGEN_OPTIONS,
        default=st.session_state.get("allergies", []),
        key="allergies",
    )

    st.subheader("Health conditions")
    persisted_health_conditions = st.session_state.get("health_conditions", [])
    health_conditions = []
    for condition in dietary_filter.HEALTH_CONDITIONS:
        checked = st.checkbox(
            condition["label"],
            value=condition["code"] in persisted_health_conditions,
            key=f"health_{condition['code']}",
        )
        if checked:
            health_conditions.append(condition["code"])
    st.session_state.health_conditions = health_conditions

    st.subheader("Connect smartwatch")
    smartwatch_connected = st.checkbox(
        "Connect smartwatch (simulated)",
        value=st.session_state.get("smartwatch_connected", False),
        key="smartwatch_connected",
    )

    if smartwatch_connected:
        st.slider(
            "Heart rate variability (ms)", 20, 120,
            st.session_state.get("hrv", 60), key="hrv",
        )
        st.slider(
            "Calories burned today", 0, 1500,
            st.session_state.get("calories_burned", 300), key="calories_burned",
        )
        st.slider(
            "Sleep score", 0, 100,
            st.session_state.get("sleep_score", 70), key="sleep_score",
        )
