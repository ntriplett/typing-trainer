"""Unit tests for the recommender: the tool the scheduler calls to
rank which keys most need warmup/practice attention. Pure, no DB.
"""

from app.models import BigramStat, KeyStat
from app.recommender import recommend_warmup_keys


def stat(key, confidence=0.0, accuracy=None, sample_count=0) -> KeyStat:
    return KeyStat(
        learner_id=1, key=key, ema_time_ms=None, confidence=confidence,
        accuracy_rolling=accuracy, sample_count=sample_count, unlocked_at=None, mastered_at=None,
    )


def test_returns_empty_for_no_active_keys():
    assert recommend_warmup_keys({}, [], n=2) == []


def test_never_attempted_key_ranks_weakest():
    key_stats = {"f": stat("f", confidence=1.0, accuracy=1.0, sample_count=20)}
    result = recommend_warmup_keys(key_stats, ["f", "j"], n=1)
    assert result == ["j"]  # "j" has no stats at all yet


def test_lower_accuracy_key_ranks_weaker_than_higher_accuracy_key():
    key_stats = {
        "f": stat("f", confidence=1.0, accuracy=0.98, sample_count=20),
        "j": stat("j", confidence=0.3, accuracy=0.6, sample_count=10),
    }
    result = recommend_warmup_keys(key_stats, ["f", "j"], n=1)
    assert result == ["j"]


def test_respects_n():
    key_stats = {
        k: stat(k, confidence=0.5, accuracy=0.8, sample_count=5) for k in ["a", "s", "d", "f"]
    }
    result = recommend_warmup_keys(key_stats, ["a", "s", "d", "f"], n=2)
    assert len(result) == 2


def test_key_in_a_known_weak_bigram_is_prioritized_over_an_otherwise_equal_key():
    # "f" and "j" are tied on key-level stats (and conveniently on
    # different fingers with no finger history either), but "f"
    # participates in a weak, well-sampled bigram.
    key_stats = {
        "f": stat("f", confidence=0.7, accuracy=0.9, sample_count=10),
        "j": stat("j", confidence=0.7, accuracy=0.9, sample_count=10),
    }
    weak_bigrams = [
        BigramStat(learner_id=1, key1="f", key2="d", ema_time_ms=900.0, accuracy_rolling=0.5, sample_count=10)
    ]
    result = recommend_warmup_keys(key_stats, ["f", "j"], n=1, bigram_stats=weak_bigrams)
    assert result == ["f"]


def test_low_sample_bigram_does_not_influence_ranking():
    key_stats = {
        "f": stat("f", confidence=0.7, accuracy=0.9, sample_count=10),
        "j": stat("j", confidence=0.7, accuracy=0.9, sample_count=10),
    }
    # Only 1 sample -- below the trust threshold, should be ignored.
    weak_bigrams = [
        BigramStat(learner_id=1, key1="f", key2="d", ema_time_ms=900.0, accuracy_rolling=0.1, sample_count=1)
    ]
    result_with = recommend_warmup_keys(key_stats, ["f", "j"], n=2, bigram_stats=weak_bigrams)
    result_without = recommend_warmup_keys(key_stats, ["f", "j"], n=2, bigram_stats=None)
    assert result_with == result_without
