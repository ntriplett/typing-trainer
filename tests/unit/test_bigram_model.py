"""Unit tests for the bigram (letter-pair) skill model: EMA math and
deriving pairs from a keystroke stream. Pure functions, no DB.
"""

import pytest

from app import bigram_model as bm
from app.activities.base import KeystrokeEvent
from app.models import BigramStat


def make_stat(**overrides) -> BigramStat:
    base = dict(learner_id=1, key1="e", key2="i", ema_time_ms=None, accuracy_rolling=None, sample_count=0)
    base.update(overrides)
    return BigramStat(**base)


def test_first_attempt_bootstraps_ema_and_accuracy():
    stat = bm.new_bigram_stat(1, "e", "i")
    updated = bm.record_bigram_attempt(stat, correct=True, latency_ms=250)
    assert updated.ema_time_ms == 250
    assert updated.accuracy_rolling == 1.0
    assert updated.sample_count == 1


def test_incorrect_pair_does_not_move_ema_but_pulls_accuracy_down():
    stat = make_stat(ema_time_ms=250.0, accuracy_rolling=1.0, sample_count=5)
    updated = bm.record_bigram_attempt(stat, correct=False, latency_ms=900)
    assert updated.ema_time_ms == 250.0
    assert updated.accuracy_rolling < 1.0
    assert updated.sample_count == 6


def test_correct_pair_moves_ema_toward_new_latency():
    stat = make_stat(ema_time_ms=300.0, accuracy_rolling=1.0, sample_count=5)
    updated = bm.record_bigram_attempt(stat, correct=True, latency_ms=100)
    expected = bm.EMA_ALPHA_TIME * 100 + (1 - bm.EMA_ALPHA_TIME) * 300.0
    assert updated.ema_time_ms == pytest.approx(expected)


def test_bigrams_from_keystrokes_pairs_consecutive_entries():
    keystrokes = [
        KeystrokeEvent("e", "e", True, 200),
        KeystrokeEvent("i", "i", True, 180),
        KeystrokeEvent("t", "x", False, 400),
    ]
    pairs = bm.bigrams_from_keystrokes(keystrokes)
    assert pairs == [
        ("e", "i", True, 180),
        ("i", "t", False, 400),  # second key of this pair was wrong
    ]


def test_bigrams_from_keystrokes_empty_for_single_or_no_keystrokes():
    assert bm.bigrams_from_keystrokes([]) == []
    assert bm.bigrams_from_keystrokes([KeystrokeEvent("e", "e", True, 200)]) == []
