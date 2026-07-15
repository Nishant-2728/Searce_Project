"""
Dietary Filter — deterministic hard safety filters and soft health-based
score penalties.

HARD constraints (dietary preference; celiac -> gluten; lactose-intolerant ->
dairy; stored allergies) are enforced as a PRE-FILTER in apply_hard_filters():
a dish that violates any hard constraint is removed from the candidate list
BEFORE matching_engine.rank_dishes() ever sees it. This is the core
guarantee — no similarity score can override a hard rule, because a
disallowed dish is never scored as a candidate in the first place.

SOFT constraints (diabetic / high cholesterol / hypertension) apply only
within the already-hard-filtered set, in apply_soft_penalties(): they scale
down an already-computed similarity score in proportion to a dish's
sugar/fat/sodium level. They never exclude a dish — they only re-rank within
the safe set.
"""

ALLERGEN_OPTIONS = ["nuts", "shellfish", "soy", "eggs", "gluten", "dairy"]

# celiac and lactose_intolerant are HARD (routed to apply_hard_filters, via
# is_gluten_free/is_dairy_free below) even though the UI groups all five
# conditions together; the hard/soft split lives here in code, not in the
# shared checkbox grouping on the Profile page.
HEALTH_CONDITIONS = [
    {"code": "diabetic", "label": "Diabetic"},
    {"code": "high_cholesterol", "label": "High cholesterol"},
    {"code": "hypertension", "label": "High blood pressure / hypertension"},
    {"code": "celiac", "label": "Gluten intolerant / celiac"},
    {"code": "lactose_intolerant", "label": "Lactose intolerant"},
]

_SOFT_PENALTY_DIMENSIONS = {
    "diabetic": "sugar_level",
    "high_cholesterol": "fat_level",
    "hypertension": "sodium_level",
}

# A single active soft condition can cut a dish's score by up to 40% at
# level=10, scaled linearly for lower levels; multiple active conditions
# compound multiplicatively.
_MAX_PENALTY_FRACTION = 0.4


def apply_hard_filters(dishes, profile):
    """
    Pre-filters `dishes` down to only those allowed by the user's hard
    dietary/allergy constraints. This must run BEFORE matching_engine.rank_dishes
    — never after — so a disallowed dish can never be a similarity candidate.

    profile = {
        "dietary_preference": "Non-vegetarian" | "Vegetarian" | "Vegan",
        "allergies": list[str],          # subset of ALLERGEN_OPTIONS
        "health_conditions": list[str],  # codes from HEALTH_CONDITIONS;
                                          # only "celiac"/"lactose_intolerant"
                                          # matter here.
    }

    Returns (allowed, exclusion_report):
      allowed: list[dict] — the subset of `dishes` violating none of the
        hard constraints, in original order.
      exclusion_report = {
          "total_excluded": int,
          "by_reason": dict[str, int],
          "excluded": list[{"dish": dict, "reasons": list[str]}],
      }
    """
    dietary_preference = profile.get("dietary_preference", "Non-vegetarian")
    allergies = set(profile.get("allergies", []))
    health_conditions = set(profile.get("health_conditions", []))

    allowed = []
    excluded = []
    by_reason = {}

    for dish in dishes:
        reasons = []

        if dietary_preference == "Vegetarian" and not dish["is_vegetarian"]:
            reasons.append("not vegetarian")
        if dietary_preference == "Vegan" and not dish["is_vegan"]:
            reasons.append("not vegan")
        if "celiac" in health_conditions and not dish["is_gluten_free"]:
            reasons.append("not gluten-free")
        if "lactose_intolerant" in health_conditions and not dish["is_dairy_free"]:
            reasons.append("not dairy-free")
        for allergen in allergies & set(dish["allergens"]):
            reasons.append(f"contains {allergen}")

        if reasons:
            excluded.append({"dish": dish, "reasons": reasons})
            for reason in reasons:
                by_reason[reason] = by_reason.get(reason, 0) + 1
        else:
            allowed.append(dish)

    exclusion_report = {
        "total_excluded": len(excluded),
        "by_reason": by_reason,
        "excluded": excluded,
    }
    return allowed, exclusion_report


def apply_soft_penalties(ranked, profile):
    """
    Re-scores an already hard-filtered, already-ranked list based on
    risk-based health conditions (diabetic/high_cholesterol/hypertension).
    Never excludes a dish and never changes which dishes are present —
    only the "allowed" set from apply_hard_filters should ever reach here.

    ranked: output of matching_engine.rank_dishes(target_vector, allowed) —
      list[{"dish": ..., "score": ...}].
    profile: {"health_conditions": list[str]} — only "diabetic",
      "high_cholesterol", "hypertension" apply; "celiac"/"lactose_intolerant"
      are ignored here since they're already fully handled as hard
      constraints upstream.

    Returns a new list, same dishes/length as `ranked`, re-sorted by the
    adjusted score descending.
    """
    active_conditions = [
        code for code in profile.get("health_conditions", []) if code in _SOFT_PENALTY_DIMENSIONS
    ]
    if not active_conditions:
        return ranked

    penalized = []
    for entry in ranked:
        dish = entry["dish"]
        multiplier = 1.0
        for code in active_conditions:
            level = dish[_SOFT_PENALTY_DIMENSIONS[code]]
            multiplier *= 1 - _MAX_PENALTY_FRACTION * level / 10
        penalized.append(
            {
                "dish": dish,
                "score": entry["score"] * multiplier,
                "original_score": entry["score"],
            }
        )

    return sorted(penalized, key=lambda entry: entry["score"], reverse=True)
