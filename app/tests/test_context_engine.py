"""Tests for context_engine.py — time bucketing, TIME_DELTAS, and the quiz question bank."""

from datetime import datetime

import pytest

from context_engine import QUIZ_QUESTIONS, TIME_DELTAS, get_time_bucket
from dishes import DIMENSIONS


def test_time_deltas_cover_all_four_buckets():
    assert set(TIME_DELTAS.keys()) == {"Morning", "Afternoon", "Evening", "Late Night"}


def test_time_deltas_only_target_real_dimensions():
    for source, delta in TIME_DELTAS.items():
        assert set(delta.keys()) <= set(DIMENSIONS), source


@pytest.mark.parametrize(
    "hour, expected",
    [
        (0, "Late Night"),
        (4, "Late Night"),
        (5, "Morning"),
        (11, "Morning"),
        (12, "Afternoon"),
        (15, "Afternoon"),
        (16, "Evening"),
        (18, "Evening"),
        (19, "Late Night"),
        (23, "Late Night"),
    ],
)
def test_get_time_bucket_boundaries(hour, expected):
    assert get_time_bucket(datetime(2026, 1, 1, hour, 0)) == expected


def test_quiz_questions_shape():
    assert 2 <= len(QUIZ_QUESTIONS) <= 4
    keys = [q["key"] for q in QUIZ_QUESTIONS]
    assert len(keys) == len(set(keys))  # every key is unique
    for q in QUIZ_QUESTIONS:
        assert q["question"]
        assert len(q["options"]) >= 2
