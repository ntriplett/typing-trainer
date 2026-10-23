"""Unit tests for the pure part of analytics: finger_stats(), which
aggregates already-fetched key_stat rows -- no DB involved.
"""

from app.analytics import finger_stats
from app.models import KeyStat


def stat(key, confidence=0.0, accuracy=None, sample_count=0) -> KeyStat:
    return KeyStat(
        learner_id=1,
        key=key,
        ema_time_ms=None,
        confidence=confidence,
        accuracy_rolling=accuracy,
        sample_count=sample_count,
        unlocked_at=None,
        mastered_at=None,
    )


def test_finger_with_no_attempts_has_none_accuracy_and_zero_samples():
    result = finger_stats({})
    left_pinky = result["left_pinky"]
    assert left_pinky.accuracy is None
    assert left_pinky.sample_count == 0
    assert "a" in left_pinky.keys  # 'a' is a left-pinky key


def test_finger_aggregates_across_its_keys_weighted_by_samples():
    # 'f' and 'g' are both left_index.
    key_stats = {
        "f": stat("f", confidence=1.0, accuracy=1.0, sample_count=10),
        "g": stat("g", confidence=0.5, accuracy=0.5, sample_count=10),
    }
    result = finger_stats(key_stats)
    left_index = result["left_index"]
    assert left_index.accuracy == 0.75  # equal-weighted average of 1.0 and 0.5
    assert left_index.sample_count == 20


def test_keys_with_zero_samples_do_not_drag_down_the_average():
    key_stats = {
        "f": stat("f", confidence=1.0, accuracy=1.0, sample_count=10),
        # "g" never attempted -- absent from key_stats entirely.
    }
    result = finger_stats(key_stats)
    left_index = result["left_index"]
    assert left_index.accuracy == 1.0
    assert left_index.sample_count == 10


def test_every_finger_is_present_in_the_result():
    from app.finger_map import ALL_FINGERS

    result = finger_stats({})
    assert set(result.keys()) == set(ALL_FINGERS)
