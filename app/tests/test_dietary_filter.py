"""Tests for dietary_filter.py — pure unit tests, no Streamlit, no LLM."""

import dietary_filter
from dishes import DISHES
from matching_engine import rank_dishes

DEFAULT_PROFILE = {"dietary_preference": "Non-vegetarian", "allergies": [], "health_conditions": []}


def _dish(id_, **overrides):
    base = {
        "id": id_,
        "name": id_,
        "vector": {},
        "is_vegetarian": True,
        "is_vegan": True,
        "is_gluten_free": True,
        "is_dairy_free": True,
        "allergens": [],
        "sugar_level": 0,
        "fat_level": 0,
        "sodium_level": 0,
    }
    base.update(overrides)
    return base


def test_no_restriction_returns_everything():
    allowed, report = dietary_filter.apply_hard_filters(DISHES, DEFAULT_PROFILE)

    assert allowed == DISHES
    assert report["total_excluded"] == 0
    assert report["by_reason"] == {}


def test_vegetarian_excludes_non_veg_dishes():
    profile = {**DEFAULT_PROFILE, "dietary_preference": "Vegetarian"}
    allowed, report = dietary_filter.apply_hard_filters(DISHES, profile)

    assert all(dish["is_vegetarian"] for dish in allowed)
    expected_excluded = sum(1 for dish in DISHES if not dish["is_vegetarian"])
    assert report["by_reason"]["not vegetarian"] == expected_excluded
    assert len(allowed) + expected_excluded == len(DISHES)


def test_vegan_excludes_all_non_vegan():
    profile = {**DEFAULT_PROFILE, "dietary_preference": "Vegan"}
    allowed, report = dietary_filter.apply_hard_filters(DISHES, profile)

    assert all(dish["is_vegan"] for dish in allowed)
    expected_excluded = sum(1 for dish in DISHES if not dish["is_vegan"])
    assert report["by_reason"]["not vegan"] == expected_excluded


def test_celiac_excludes_non_gluten_free():
    profile = {**DEFAULT_PROFILE, "health_conditions": ["celiac"]}
    allowed, report = dietary_filter.apply_hard_filters(DISHES, profile)

    assert all(dish["is_gluten_free"] for dish in allowed)
    expected_excluded = sum(1 for dish in DISHES if not dish["is_gluten_free"])
    assert report["by_reason"]["not gluten-free"] == expected_excluded


def test_lactose_intolerant_excludes_non_dairy_free():
    profile = {**DEFAULT_PROFILE, "health_conditions": ["lactose_intolerant"]}
    allowed, report = dietary_filter.apply_hard_filters(DISHES, profile)

    assert all(dish["is_dairy_free"] for dish in allowed)
    expected_excluded = sum(1 for dish in DISHES if not dish["is_dairy_free"])
    assert report["by_reason"]["not dairy-free"] == expected_excluded


def test_allergy_excludes_matching_allergen_dishes():
    profile = {**DEFAULT_PROFILE, "allergies": ["nuts"]}
    allowed, report = dietary_filter.apply_hard_filters(DISHES, profile)

    assert all("nuts" not in dish["allergens"] for dish in allowed)
    expected_excluded = sum(1 for dish in DISHES if "nuts" in dish["allergens"])
    assert report["by_reason"]["contains nuts"] == expected_excluded


def test_multiple_hard_constraints_combine():
    dishes = [
        _dish("safe"),
        _dish("veg-violator", is_vegetarian=False, is_vegan=False),
        _dish("double-violator", is_vegetarian=False, is_vegan=False, is_gluten_free=False),
    ]
    profile = {"dietary_preference": "Vegetarian", "allergies": [], "health_conditions": ["celiac"]}

    allowed, report = dietary_filter.apply_hard_filters(dishes, profile)

    assert [d["id"] for d in allowed] == ["safe"]
    assert report["total_excluded"] == 2
    assert report["by_reason"]["not vegetarian"] == 2
    assert report["by_reason"]["not gluten-free"] == 1
    double_violator_entry = next(e for e in report["excluded"] if e["dish"]["id"] == "double-violator")
    assert set(double_violator_entry["reasons"]) == {"not vegetarian", "not gluten-free"}


def test_hard_filtered_dishes_never_reach_rank_dishes():
    profile = {**DEFAULT_PROFILE, "dietary_preference": "Vegetarian"}
    allowed, _ = dietary_filter.apply_hard_filters(DISHES, profile)

    target_vector = {dim: 5 for dim in allowed[0]["vector"]}
    ranked = rank_dishes(target_vector, allowed)
    ranked_ids = {entry["dish"]["id"] for entry in ranked}

    excluded_ids = {dish["id"] for dish in DISHES if not dish["is_vegetarian"]}
    assert ranked_ids.isdisjoint(excluded_ids)


def test_soft_penalty_lowers_score_proportional_to_level():
    ranked = [
        {"dish": _dish("low-sugar", sugar_level=0), "score": 0.8},
        {"dish": _dish("high-sugar", sugar_level=10), "score": 0.8},
    ]
    profile = {"health_conditions": ["diabetic"]}

    penalized = dietary_filter.apply_soft_penalties(ranked, profile)
    by_id = {entry["dish"]["id"]: entry for entry in penalized}

    assert by_id["low-sugar"]["score"] == 0.8
    assert by_id["high-sugar"]["score"] < 0.8


def test_soft_penalty_no_active_conditions_is_a_no_op():
    ranked = [{"dish": _dish("d1", sugar_level=10), "score": 0.5}]

    assert dietary_filter.apply_soft_penalties(ranked, {"health_conditions": []}) == ranked


def test_soft_penalty_never_changes_dish_membership():
    ranked = [
        {"dish": _dish("a", sugar_level=3), "score": 0.9},
        {"dish": _dish("b", sugar_level=8), "score": 0.7},
    ]
    penalized = dietary_filter.apply_soft_penalties(ranked, {"health_conditions": ["diabetic"]})

    assert {e["dish"]["id"] for e in penalized} == {"a", "b"}
    assert len(penalized) == len(ranked)


def test_soft_penalty_output_sorted_best_first():
    ranked = [
        {"dish": _dish("high-sugar-high-score", sugar_level=10), "score": 0.95},
        {"dish": _dish("low-sugar-lower-score", sugar_level=0), "score": 0.6},
    ]
    penalized = dietary_filter.apply_soft_penalties(ranked, {"health_conditions": ["diabetic"]})

    scores = [entry["score"] for entry in penalized]
    assert scores == sorted(scores, reverse=True)


def test_celiac_and_lactose_intolerant_ignored_by_soft_penalty():
    ranked = [{"dish": _dish("d1", sugar_level=10, fat_level=10, sodium_level=10), "score": 0.5}]
    profile = {"health_conditions": ["celiac", "lactose_intolerant"]}

    assert dietary_filter.apply_soft_penalties(ranked, profile) == ranked
