"""Unit tests for the adaptive core: EMA confidence, accuracy floor,
minimum sample count, and the unlock/active-keys logic.

All pure-function tests -- no DB, no clock side effects (an explicit
`now` is passed in wherever the model needs a timestamp).
"""

from datetime import UTC, datetime

import pytest

from app import skill_model as sm
from app.models import KeyStat

NOW = datetime(2026, 10, 23, tzinfo=UTC)


def make_stat(**overrides) -> KeyStat:
    base = dict(
        learner_id=1,
        key="f",
        ema_time_ms=None,
        confidence=0.0,
        accuracy_rolling=None,
        sample_count=0,
        unlocked_at=None,
        mastered_at=None,
    )
    base.update(overrides)
    return KeyStat(**base)


# --- record_attempt: timing (EMA) -------------------------------------------


def test_first_correct_attempt_bootstraps_ema_to_its_own_latency():
    stat = sm.new_key_stat(learner_id=1, key="f")
    updated = sm.record_attempt(stat, correct=True, latency_ms=300, now=NOW)
    assert updated.ema_time_ms == 300
    assert updated.sample_count == 1


def test_subsequent_correct_attempt_moves_ema_toward_new_latency():
    stat = make_stat(ema_time_ms=300.0, sample_count=1, accuracy_rolling=1.0)
    updated = sm.record_attempt(stat, correct=True, latency_ms=100, now=NOW)
    expected = sm.EMA_ALPHA_TIME * 100 + (1 - sm.EMA_ALPHA_TIME) * 300.0
    assert updated.ema_time_ms == pytest.approx(expected)
    assert updated.ema_time_ms < 300.0  # moved toward the faster latency


def test_incorrect_attempt_does_not_change_ema_time():
    stat = make_stat(ema_time_ms=300.0, sample_count=1, accuracy_rolling=1.0)
    updated = sm.record_attempt(stat, correct=False, latency_ms=5000, now=NOW)
    assert updated.ema_time_ms == 300.0  # unaffected by the slow/wrong attempt


def test_confidence_is_target_over_ema():
    stat = sm.new_key_stat(learner_id=1, key="f")
    updated = sm.record_attempt(stat, correct=True, latency_ms=sm.TARGET_MS_PER_KEYSTROKE, now=NOW)
    assert updated.confidence == pytest.approx(1.0)


# --- record_attempt: accuracy -----------------------------------------------


def test_first_attempt_bootstraps_accuracy_from_its_own_correctness():
    stat = sm.new_key_stat(learner_id=1, key="f")
    correct = sm.record_attempt(stat, correct=True, latency_ms=300, now=NOW)
    assert correct.accuracy_rolling == 1.0

    stat2 = sm.new_key_stat(learner_id=1, key="f")
    wrong = sm.record_attempt(stat2, correct=False, latency_ms=300, now=NOW)
    assert wrong.accuracy_rolling == 0.0


def test_incorrect_attempt_pulls_rolling_accuracy_down():
    stat = make_stat(ema_time_ms=300.0, sample_count=10, accuracy_rolling=1.0)
    updated = sm.record_attempt(stat, correct=False, latency_ms=300, now=NOW)
    assert updated.accuracy_rolling < 1.0


def test_sample_count_increments_on_both_correct_and_incorrect():
    stat = make_stat(sample_count=5, accuracy_rolling=0.9, ema_time_ms=300.0)
    after_correct = sm.record_attempt(stat, correct=True, latency_ms=300, now=NOW)
    after_incorrect = sm.record_attempt(stat, correct=False, latency_ms=300, now=NOW)
    assert after_correct.sample_count == 6
    assert after_incorrect.sample_count == 6


# --- is_mastered / mastery gating --------------------------------------------


def test_not_mastered_when_confidence_too_low():
    stat = make_stat(
        confidence=0.5, accuracy_rolling=0.99, sample_count=sm.MIN_SAMPLES_FOR_MASTERY
    )
    assert not sm.is_mastered(stat)


def test_not_mastered_when_accuracy_below_floor():
    stat = make_stat(
        confidence=1.2, accuracy_rolling=0.80, sample_count=sm.MIN_SAMPLES_FOR_MASTERY
    )
    assert not sm.is_mastered(stat)


def test_not_mastered_when_sample_count_too_low():
    # Fast and accurate off a single lucky attempt -- the gap in the
    # keybr reference design this project explicitly fixes.
    stat = make_stat(confidence=1.5, accuracy_rolling=1.0, sample_count=1)
    assert not sm.is_mastered(stat)


def test_mastered_when_all_three_conditions_met():
    stat = make_stat(
        confidence=1.1, accuracy_rolling=0.97, sample_count=sm.MIN_SAMPLES_FOR_MASTERY
    )
    assert sm.is_mastered(stat)


def test_record_attempt_sets_mastered_at_on_first_mastery_only():
    # Build up to just-barely-mastered via repeated fast, correct attempts.
    stat = sm.new_key_stat(learner_id=1, key="f")
    for _ in range(sm.MIN_SAMPLES_FOR_MASTERY):
        stat = sm.record_attempt(
            stat, correct=True, latency_ms=sm.TARGET_MS_PER_KEYSTROKE, now=NOW
        )
    assert stat.mastered_at == NOW

    # A later attempt (even a bad one) must not overwrite the original
    # mastered_at timestamp.
    later = datetime(2026, 11, 1, tzinfo=UTC)
    stat = sm.record_attempt(stat, correct=False, latency_ms=2000, now=later)
    assert stat.mastered_at == NOW


# --- needs_review -------------------------------------------------------------


def test_needs_review_false_if_never_mastered():
    stat = make_stat(mastered_at=None, accuracy_rolling=0.5)
    assert not sm.needs_review(stat)


def test_needs_review_true_if_mastered_then_regressed():
    stat = make_stat(mastered_at=NOW, accuracy_rolling=0.80)
    assert sm.needs_review(stat)


def test_needs_review_false_if_mastered_and_still_accurate():
    stat = make_stat(mastered_at=NOW, accuracy_rolling=0.98)
    assert not sm.needs_review(stat)


# --- active_keys / unlock logic -----------------------------------------------


def test_initial_active_keys_before_any_mastery():
    keys = sm.active_keys({})
    assert keys == list(sm.KEY_ORDER[: sm.INITIAL_ACTIVE_KEY_COUNT])


def test_next_key_unlocks_once_all_active_keys_mastered():
    stats = {
        key: make_stat(key=key, mastered_at=NOW)
        for key in sm.KEY_ORDER[: sm.INITIAL_ACTIVE_KEY_COUNT]
    }
    keys = sm.active_keys(stats)
    assert keys == list(sm.KEY_ORDER[: sm.INITIAL_ACTIVE_KEY_COUNT + 1])


def test_unlock_stops_at_first_unmastered_key():
    first, second = sm.KEY_ORDER[0], sm.KEY_ORDER[1]
    stats = {
        first: make_stat(key=first, mastered_at=NOW),
        second: make_stat(key=second, mastered_at=None),  # not mastered
    }
    keys = sm.active_keys(stats)
    assert keys == list(sm.KEY_ORDER[: sm.INITIAL_ACTIVE_KEY_COUNT])


def test_mastered_key_stays_active_even_if_it_later_regresses():
    first = sm.KEY_ORDER[0]
    stats = {
        key: make_stat(key=key, mastered_at=NOW)
        for key in sm.KEY_ORDER[: sm.INITIAL_ACTIVE_KEY_COUNT]
    }
    stats[first] = make_stat(key=first, mastered_at=NOW, accuracy_rolling=0.5)  # regressed
    keys = sm.active_keys(stats)
    # Regression doesn't lock the key back out -- it's surfaced via
    # needs_review for the scheduler instead.
    assert first in keys
    assert keys == list(sm.KEY_ORDER[: sm.INITIAL_ACTIVE_KEY_COUNT + 1])


def test_mark_unlocked_sets_timestamp_only_once():
    stat = sm.new_key_stat(learner_id=1, key="f")
    unlocked = sm.mark_unlocked(stat, NOW)
    assert unlocked.unlocked_at == NOW

    later = datetime(2026, 11, 1, tzinfo=UTC)
    unchanged = sm.mark_unlocked(unlocked, later)
    assert unchanged.unlocked_at == NOW


# --- key_state / keys_in_state / next_keys_to_teach --------------------------


def test_key_state_untaught_when_never_attempted():
    assert sm.key_state(None) == "untaught"
    assert sm.key_state(make_stat(unlocked_at=None)) == "untaught"


def test_key_state_teaching_when_unlocked_but_too_few_samples():
    stat = make_stat(unlocked_at=NOW, accuracy_rolling=1.0, sample_count=sm.MIN_SAMPLES_FOR_LEARNED - 1)
    assert sm.key_state(stat) == "teaching"


def test_key_state_teaching_when_accuracy_not_yet_established():
    stat = make_stat(unlocked_at=NOW, accuracy_rolling=None, sample_count=50)
    assert sm.key_state(stat) == "teaching"


def test_key_state_learning_when_enough_samples_but_below_threshold():
    stat = make_stat(
        unlocked_at=NOW, accuracy_rolling=0.79, sample_count=sm.MIN_SAMPLES_FOR_LEARNED
    )
    assert sm.key_state(stat) == "learning"


def test_key_state_learned_at_or_above_threshold():
    stat = make_stat(
        unlocked_at=NOW, accuracy_rolling=0.80, sample_count=sm.MIN_SAMPLES_FOR_LEARNED
    )
    assert sm.key_state(stat) == "learned"


def test_key_state_can_regress_from_learned_back_to_learning():
    # Live snapshot, not a one-way ratchet -- distinct from is_mastered()/mastered_at.
    stat = make_stat(unlocked_at=NOW, accuracy_rolling=0.60, sample_count=50)
    assert sm.key_state(stat) == "learning"


def test_keys_in_state_filters_by_state():
    stats = {
        "f": make_stat(key="f", unlocked_at=NOW, accuracy_rolling=0.9, sample_count=20),  # learned
        "j": make_stat(key="j", unlocked_at=NOW, accuracy_rolling=0.5, sample_count=20),  # learning
        "d": make_stat(key="d", unlocked_at=NOW, accuracy_rolling=None, sample_count=0),  # teaching
    }
    assert sm.keys_in_state(stats, "learned", key_order=("f", "j", "d")) == ["f"]
    assert sm.keys_in_state(stats, "learning", key_order=("f", "j", "d")) == ["j"]
    assert sm.keys_in_state(stats, "teaching", key_order=("f", "j", "d")) == ["d"]
    assert sm.keys_in_state(stats, "untaught", key_order=("f", "j", "d", "k")) == ["k"]


def test_next_keys_to_teach_returns_first_not_in_allowed_in_key_order():
    allowed = [sm.KEY_ORDER[0]]
    result = sm.next_keys_to_teach(allowed, n=2)
    assert result == [sm.KEY_ORDER[1], sm.KEY_ORDER[2]]


def test_next_keys_to_teach_empty_when_everything_allowed():
    assert sm.next_keys_to_teach(list(sm.KEY_ORDER), n=1) == []


def test_space_is_the_first_key_and_active_from_the_start():
    assert sm.KEY_ORDER[0] == " "
    assert " " in sm.active_keys({})
