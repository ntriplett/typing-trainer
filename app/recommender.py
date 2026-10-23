"""The recommender: the tool the scheduler calls to decide which keys
most need warmup/practice attention right now.

Combines three signals, from lowest to highest granularity:
  - per-key weakness (confidence + accuracy)
  - per-finger weakness (so a key on an overall-weak finger edges out
    an equally-weak key on a strong finger)
  - known problem letter-pairs (a key that shows up in a low-accuracy
    bigram gets bumped up in priority, since drilling it should help
    that transition too)

Pure function over already-fetched skill-model state -- no DB. Kept
separate from scheduler.py so "how do we decide what's weak" can grow
(more signals, different weighting) without touching the scheduler's
phase-sequencing logic, and separate from skill_model.py since this is
about *ranking/choosing*, not the underlying per-key/per-bigram math
(this module is the single home for that ranking logic now -- it used
to be duplicated with a skill_model.weakest_keys(), which was removed).
"""

from __future__ import annotations

from app.analytics import finger_stats
from app.finger_map import KEY_TO_FINGER
from app.models import BigramStat, KeyStat

# A bigram below this accuracy (with enough samples to trust it) marks
# both its keys as worth extra warmup attention.
WEAK_BIGRAM_ACCURACY_THRESHOLD = 0.85
WEAK_BIGRAM_MIN_SAMPLES = 3
BIGRAM_PRIORITY_BONUS = 0.15


def _key_weakness(key: str, key_stats: dict[str, KeyStat]) -> float:
    """Lower = weaker."""
    stat = key_stats.get(key)
    if stat is None:
        return 0.0
    accuracy = stat.accuracy_rolling if stat.accuracy_rolling is not None else 0.0
    return min(stat.confidence, 1.0) + accuracy


def _finger_weakness(key: str, finger_stat_map: dict) -> float:
    finger = KEY_TO_FINGER.get(key)
    stat = finger_stat_map.get(finger) if finger else None
    if stat is None or stat.accuracy is None:
        return 2.0  # neutral/unknown -- don't penalize a finger with no data yet
    return min(stat.avg_confidence or 0.0, 1.0) + stat.accuracy


def _keys_in_weak_bigrams(bigram_stats: list[BigramStat] | None) -> set[str]:
    if not bigram_stats:
        return set()
    weak_keys: set[str] = set()
    for b in bigram_stats:
        if (
            b.accuracy_rolling is not None
            and b.accuracy_rolling < WEAK_BIGRAM_ACCURACY_THRESHOLD
            and b.sample_count >= WEAK_BIGRAM_MIN_SAMPLES
        ):
            weak_keys.add(b.key1)
            weak_keys.add(b.key2)
    return weak_keys


def recommend_warmup_keys(
    key_stats: dict[str, KeyStat],
    active_keys: list[str],
    n: int = 2,
    bigram_stats: list[BigramStat] | None = None,
) -> list[str]:
    """The `n` keys (from `active_keys`) most worth warming up right now."""
    if not active_keys:
        return []

    weak_pair_keys = _keys_in_weak_bigrams(bigram_stats)
    finger_map = finger_stats(key_stats)

    def score(key: str) -> float:
        value = _key_weakness(key, key_stats) + _finger_weakness(key, finger_map)
        if key in weak_pair_keys:
            value -= BIGRAM_PRIORITY_BONUS
        return value

    return sorted(active_keys, key=score)[:n]
