"""Unit tests for the shared activity helpers: the dual focus/allowed
pool mix, blocked-sequence generation, and the common scoring function.
"""

import random

import pytest

from app.activities.base import (
    KeystrokeEvent,
    build_blocked_sequence,
    build_mixed_sequence,
    combined_pool,
    score_attempt,
)


def test_combined_pool_dedupes_and_preserves_order():
    assert combined_pool(["f", "j"], ["j", "d"]) == ["f", "j", "d"]


def test_combined_pool_raises_when_both_empty():
    with pytest.raises(ValueError):
        combined_pool([], [])


def test_build_mixed_sequence_only_uses_the_two_given_pools():
    seq = build_mixed_sequence(["f", "j"], ["d", "k"], focus_ratio=0.5, duration_s=10, rng=random.Random(1))
    letters = set(seq.replace(" ", ""))
    assert letters <= {"f", "j", "d", "k"}


def test_build_mixed_sequence_respects_the_ratio_at_the_extremes():
    all_focus = build_mixed_sequence(["f"], ["j"], focus_ratio=1.0, duration_s=20, rng=random.Random(1))
    assert set(all_focus.replace(" ", "")) == {"f"}

    all_allowed = build_mixed_sequence(["f"], ["j"], focus_ratio=0.0, duration_s=20, rng=random.Random(1))
    assert set(all_allowed.replace(" ", "")) == {"j"}


def test_build_mixed_sequence_falls_back_to_the_nonempty_pool():
    only_focus = build_mixed_sequence(["f", "j"], [], focus_ratio=0.5, duration_s=20, rng=random.Random(1))
    assert set(only_focus.replace(" ", "")) <= {"f", "j"}

    only_allowed = build_mixed_sequence([], ["d", "k"], focus_ratio=0.5, duration_s=20, rng=random.Random(1))
    assert set(only_allowed.replace(" ", "")) <= {"d", "k"}


def test_build_mixed_sequence_raises_when_both_pools_empty():
    with pytest.raises(ValueError):
        build_mixed_sequence([], [], focus_ratio=0.5, duration_s=10, rng=random.Random(1))


def test_build_mixed_sequence_scales_with_duration():
    short = build_mixed_sequence(["f"], ["j"], 0.5, duration_s=5, rng=random.Random(1))
    long = build_mixed_sequence(["f"], ["j"], 0.5, duration_s=60, rng=random.Random(1))
    assert len(long.replace(" ", "")) > len(short.replace(" ", ""))


def test_build_blocked_sequence_groups_each_key_together():
    seq = build_blocked_sequence(["f", "j"], duration_s=3, min_repeats=3)
    assert seq == "fff jjj"


def test_build_blocked_sequence_scales_with_duration():
    short = build_blocked_sequence(["f", "j"], duration_s=4)
    long = build_blocked_sequence(["f", "j"], duration_s=60)
    assert len(long.replace(" ", "")) > len(short.replace(" ", ""))


def test_build_blocked_sequence_never_goes_below_min_repeats():
    seq = build_blocked_sequence(["f", "j"], duration_s=1, min_repeats=4)
    assert seq == "ffff jjjj"


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


def test_mixed_sequence_never_draws_space_as_a_letter():
    import random as _random

    from app.activities.base import build_mixed_sequence

    seq = build_mixed_sequence([" ", "f"], [" ", "f", "j"], 0.5, 60, _random.Random(3))
    assert "  " not in seq
    assert not seq.startswith(" ") and not seq.endswith(" ")


def test_space_focus_makes_shorter_words():
    import random as _random

    from app.activities.base import build_mixed_sequence

    with_space = build_mixed_sequence([" "], ["f", "j"], 0.5, 60, _random.Random(3))
    without = build_mixed_sequence(["f"], ["f", "j"], 0.5, 60, _random.Random(3))
    assert max(map(len, with_space.split(" "))) == 2
    assert max(map(len, without.split(" "))) == 4


def test_space_teach_alternates_letters_and_spaces():
    from app.activities.base import build_space_sequence

    seq = build_space_sequence([" ", "f", "j"], 10)
    assert seq.startswith("f j f j")
    assert all(len(word) == 1 for word in seq.split(" "))
