"""
Context Engine — time-of-day bucketing, the mood-quiz question bank, and the
small vector utilities shared with llm_context_engine.py's deterministic
fallback.

The primary context-fusion path (time + weather + biometrics + mood quiz +
free-text craving -> target flavor vector) is now handled by an LLM call in
llm_context_engine.py, not by hardcoded delta tables. TIME_DELTAS survives
here because it still does double duty: it's a labeled input sent to the
LLM, and it's the backbone of the deterministic fallback vector used when
the LLM call fails.
"""

from dishes import DIMENSIONS

TIME_DELTAS = {
    "Morning": {"freshness": 2, "crunch": 1, "richness": -1, "warmth": 1},
    "Afternoon": {"richness": 1, "umami": 1, "saltiness": 1},
    "Evening": {"warmth": 1, "crunch": 2, "aroma": 1},
    "Late Night": {"warmth": 3, "richness": 3, "sweetness": 2, "spice": -2, "freshness": -2},
}

# The mood quiz replaces the old single mood chip + activity multiselect.
# Each question is optional (a user can leave any of them unanswered); the
# "key" is the field name used in the context payload sent to the LLM and in
# the fallback delta table in llm_context_engine.py.
QUIZ_QUESTIONS = [
    {
        "key": "energy_level",
        "question": "How's your energy right now?",
        "options": ["Low", "Moderate", "High", "Wired but tired"],
    },
    {
        "key": "day_descriptor",
        "question": "How would you describe today so far?",
        "options": [
            "Calm and easy",
            "Stressful and packed",
            "Something to celebrate",
            "A slow, nostalgic kind of day",
        ],
    },
    {
        "key": "notable_activity",
        "question": "Anything physical or notable going on?",
        "options": [
            "Just worked out",
            "Long day at work",
            "Traveling",
            "Feeling under the weather",
            "Hosting guests",
            "Nothing in particular",
        ],
    },
    {
        "key": "temperature_preference",
        "question": "What sounds appealing right now?",
        "options": [
            "Something warm and comforting",
            "Something light and fresh",
            "Something bold and intense",
            "Not sure",
        ],
    },
]


def get_time_bucket(now):
    """Buckets a datetime's hour into Morning / Afternoon / Evening / Late Night."""
    hour = now.hour
    if 5 <= hour < 12:
        return "Morning"
    if 12 <= hour < 16:
        return "Afternoon"
    if 16 <= hour < 19:
        return "Evening"
    return "Late Night"


def add_delta(vector, delta):
    """Adds a (possibly None/partial) delta dict onto a vector dict, in place."""
    if not delta:
        return
    for dim, value in delta.items():
        vector[dim] += value


def clamp_vector(vector):
    """Clamps every dimension of a vector dict to the 0-10 range, in place."""
    for dim in DIMENSIONS:
        vector[dim] = min(10, max(0, vector[dim]))
