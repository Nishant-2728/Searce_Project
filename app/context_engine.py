"""
Context Engine — fully rule-based delta tables (no ML, no hidden logic) plus
the functions that turn a time bucket / mood / activities / free-text craving
into a single Target Flavor Vector.

Every delta table below is an explicit, flat dict mapping one input signal to
a fixed delta across (a subset of) the 14 dimensions. This is the
"auditability" story for the RFP: every number here is a rule you can point
to and defend by itself, with no derived or hidden logic.
"""

from dishes import DIMENSIONS

MOODS = ["Stressed", "Relaxed", "Tired", "Energized", "Anxious", "Celebratory", "Nostalgic", "Bored"]

ACTIVITIES = ["Just worked out", "Long day at work", "Lazy Sunday", "Traveling", "Sick / unwell", "Hosting guests"]

WEATHER_CONDITIONS = ["Sunny", "Cloudy", "Rainy", "Hot", "Cold"]

TIME_DELTAS = {
    "Morning": {"freshness": 2, "crunch": 1, "richness": -1, "warmth": 1},
    "Afternoon": {"richness": 1, "umami": 1, "saltiness": 1},
    "Evening": {"warmth": 1, "crunch": 2, "aroma": 1},
    "Late Night": {"warmth": 3, "richness": 3, "sweetness": 2, "spice": -2, "freshness": -2},
}

MOOD_DELTAS = {
    "Stressed": {"warmth": 3, "richness": 3, "sweetness": 2, "spice": -2, "freshness": -1},
    "Relaxed": {"freshness": 2, "moisture": 1, "spice": -1},
    "Tired": {"sweetness": 2, "warmth": 2, "moisture": 2, "chewiness": -1},
    "Energized": {"spice": 2, "crunch": 2, "freshness": 2, "richness": -2},
    "Anxious": {"warmth": 2, "sweetness": 2, "acidity": -2, "spice": -2},
    "Celebratory": {"richness": 3, "sweetness": 2, "aroma": 2, "umami": 2},
    "Nostalgic": {"warmth": 2, "umami": 2, "aroma": 2, "sweetness": 1},
    "Bored": {"spice": 2, "crunch": 2, "acidity": 2},
}

ACTIVITY_DELTAS = {
    "Just worked out": {"freshness": 2, "moisture": 2, "richness": -2, "umami": 2},
    "Long day at work": {"warmth": 2, "richness": 2, "sweetness": 1, "crunch": -1},
    "Lazy Sunday": {"richness": 2, "warmth": 1, "chewiness": 1},
    "Traveling": {"saltiness": 2, "crunch": 2, "moisture": -1},
    "Sick / unwell": {"warmth": 3, "moisture": 3, "spice": -3, "crunch": -2},
    "Hosting guests": {"aroma": 2, "umami": 2, "richness": 1},
}

WEATHER_DELTAS = {
    "Sunny": {"freshness": 2, "crunch": 1, "richness": -1},
    "Cloudy": {"warmth": 1, "richness": 1},
    "Rainy": {"warmth": 3, "richness": 2, "moisture": 1, "freshness": -2},
    "Hot": {"freshness": 2, "moisture": 2, "richness": -1, "spice": -1},
    "Cold": {"warmth": 3, "richness": 2, "spice": 1, "freshness": -2},
}

# Free-text craving box: rule-based keyword -> flavor-delta lookup. No model.
KEYWORD_DELTAS = {
    "spicy": {"spice": 3},
    "hot": {"spice": 2},
    "fiery": {"spice": 3},
    "tangy": {"acidity": 3},
    "sour": {"acidity": 3},
    "acidic": {"acidity": 2},
    "rich": {"richness": 3},
    "creamy": {"richness": 2, "moisture": 1},
    "buttery": {"richness": 3},
    "comfort": {"warmth": 2, "richness": 2},
    "cozy": {"warmth": 2, "richness": 1},
    "crunchy": {"crunch": 3},
    "crispy": {"crunch": 3},
    "savory": {"umami": 2},
    "umami": {"umami": 3},
    "sweet": {"sweetness": 3},
    "sugary": {"sweetness": 2},
    "bitter": {"bitterness": 3},
    "burnt": {"bitterness": 2},
    "salty": {"saltiness": 3},
    "salted": {"saltiness": 2},
    "fresh": {"freshness": 3, "richness": -1},
    "light": {"freshness": 2, "richness": -2},
    "juicy": {"moisture": 3},
    "moist": {"moisture": 2},
    "fragrant": {"aroma": 3},
    "aromatic": {"aroma": 3},
    "chewy": {"chewiness": 3},
    "dense": {"chewiness": 2, "richness": 1},
    "contrast": {"temp_contrast": 3},
    "sizzling": {"temp_contrast": 2, "warmth": 2},
}


def get_time_bucket(now):
    """Buckets a datetime's hour into Morning / Afternoon / Evening / Late Night."""
    hour = now.hour
    if 5 <= hour < 12:
        return "Morning"
    if 12 <= hour < 17:
        return "Afternoon"
    if 17 <= hour < 21:
        return "Evening"
    return "Late Night"


def _add_delta(vector, delta):
    """Adds a (possibly None/partial) delta dict onto a vector dict, in place."""
    if not delta:
        return
    for dim, value in delta.items():
        vector[dim] += value


def _clamp_vector(vector):
    """Clamps every dimension of a vector dict to the 0-10 range, in place."""
    for dim in DIMENSIONS:
        vector[dim] = min(10, max(0, vector[dim]))


def compute_target_vector(time_bucket, mood, activities, free_text, weather=None):
    """
    Builds the Target Flavor Vector for the current context.

    Starts every dimension at a neutral baseline of 5, then sums in the fixed
    delta for the time bucket, the selected mood (if any), each selected
    activity, weather (if provided), and every keyword matched (via plain 
    substring search) in the free-text craving box. Result is clamped back to 0-10.

    Args:
        time_bucket: one of Morning/Afternoon/Evening/Late Night
        mood: selected mood or None
        activities: list of selected activities
        free_text: free-form craving text
        weather: weather condition (e.g., "Sunny", "Rainy", "Hot", "Cold") or None

    Returns (vector, contributions, matched_keywords):
      - vector: the final 14-dim target flavor vector (dict).
      - contributions: a list of {"source": <label>, "delta": <dict>} entries,
        one per input signal that fired — used by explain_match() to trace a
        result's top dimensions back to the inputs that drove them.
      - matched_keywords: list of craving keywords that matched, for display.
    """
    vector = {dim: 5 for dim in DIMENSIONS}
    contributions = []

    time_delta = TIME_DELTAS[time_bucket]
    contributions.append({"source": time_bucket, "delta": time_delta})
    _add_delta(vector, time_delta)

    if mood:
        mood_delta = MOOD_DELTAS[mood]
        contributions.append({"source": mood, "delta": mood_delta})
        _add_delta(vector, mood_delta)

    for activity in activities:
        activity_delta = ACTIVITY_DELTAS[activity]
        contributions.append({"source": activity, "delta": activity_delta})
        _add_delta(vector, activity_delta)

    if weather and weather in WEATHER_DELTAS:
        weather_delta = WEATHER_DELTAS[weather]
        contributions.append({"source": weather, "delta": weather_delta})
        _add_delta(vector, weather_delta)

    matched_keywords = []
    lower_craving = free_text.lower()
    for keyword, delta in KEYWORD_DELTAS.items():
        if keyword in lower_craving:
            matched_keywords.append(keyword)
            contributions.append({"source": f'"{keyword}"', "delta": delta})
            _add_delta(vector, delta)

    _clamp_vector(vector)

    return vector, contributions, matched_keywords
