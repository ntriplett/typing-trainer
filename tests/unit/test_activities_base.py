"""Unit tests for the shared activity helpers: key picking, prompt
generation, and the common scoring function.
"""

import random

import pytest

from app.activities.base import (
    KeystrokeEvent,
    build_blocked_sequence,
    build_random_sequence,
    pick_two_keys,
    score_attempt,
)


def test_pick_two_keys_returns_two_distinct_when_available():
    chosen = pick_two_keys(["f", "j", "d"], rng=random.Random(1))
    assert len(chosen) == 2
    assert chosen[0] != chosen[1]
    assert set(chosen) <= {"f", "j", "d"}


def test_pick_two_keys_repeats_single_key_when_only_one_active():
    chosen = pick_two_keys(["f"], rng=random.Random(1))
    assert chosen == ["f", "f"]


def test_pick_two_keys_raises_when_no_active_keys():
    with pytest.raises(ValueError):
        pick_two_keys([], rng=random.Random(1))


def test_build_random_sequence_only_uses_given_keys():
    seq = build_random_sequence(["f", "j"], duration_s=5, rng=random.Random(1))
    letters = seq.replace(" ", "")
    assert set(letters) <= {"f", "j"}
    assert len(letters) > 0


def test_build_random_sequence_scales_with_duration():
    short = build_random_sequence(["f", "j"], duration_s=5, rng=random.Random(1))
    long = build_random_sequence(["f", "j"], duration_s=60, rng=random.Random(1))
    assert len(long.replace(" ", "")) > len(short.replace(" ", ""))


def test_build_blocked_sequence_groups_each_key_together():
    seq = build_blocked_sequence(["f", "j"], repeats=3)
    assert seq == "fff jjj"


def test_score_attempt_all_correct_is_nailed_it():
    keystrokes = [KeystrokeEvent("f", "f", True, 200) for _ in range(10)]
    result = score_attempt("activity_x", ["f"], keystrokes)
    assert result.accuracy == 1.0
    assert result.reward_signal == "nailed_it"
    assert result.correct == 10
    assert result.attempts == 10
    assert result.wpm > 0


def test_score_attempt_mixed_accuracy_is_solid():
    keystrokes = [KeystrokeEvent("f", "f", i % 5 != 0, 200) for i in range(20)]
    result = score_attempt("activity_x", ["f"], keystrokes)
    assert 0.80 <= result.accuracy < 0.95
    assert result.reward_signal == "solid"


def test_score_attempt_low_accuracy_is_struggled():
    keystrokes = [KeystrokeEvent("f", "x", i % 2 == 0, 200) for i in range(20)]
    result = score_attempt("activity_x", ["f"], keystrokes)
    assert result.accuracy < 0.80
    assert result.reward_signal == "struggled"


def test_score_attempt_handles_no_keystrokes():
    result = score_attempt("activity_x", ["f"], [])
    assert result.attempts == 0
    assert result.accuracy == 0.0
    assert result.wpm == 0.0
