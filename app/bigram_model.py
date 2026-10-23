"""The bigram (letter-pair) skill model: same EMA approach as
app.skill_model, scoped to 2-key transitions instead of single keys.

Deliberately simpler than KeyStat -- no confidence/unlock/mastery
concept, since bigrams don't gate the scheduler's active-key set. This
is detail-level data: how fast and accurately a specific transition
(e.g. "e" -> "i") goes, for the analysis page and as a secondary signal
for the recommender (PLAN.md's "maybe letter pairs as a detail").

Folded in once per activity step at completion time, not per keystroke
-- the step's keystrokes are already a batch by the time scoring runs
(see app/main.py), so this reuses that batch rather than adding a
write per keystroke.
"""

from __future__ import annotations

from datetime import datetime

from app.activities.base import KeystrokeEvent
from app.models import BigramStat

EMA_ALPHA_TIME = 0.1
EMA_ALPHA_ACCURACY = 0.15


def new_bigram_stat(learner_id: int, key1: str, key2: str) -> BigramStat:
    return BigramStat(
        learner_id=learner_id, key1=key1, key2=key2, ema_time_ms=None, accuracy_rolling=None, sample_count=0
    )


def record_bigram_attempt(stat: BigramStat, *, correct: bool, latency_ms: int) -> BigramStat:
    """Fold one observed transition into a bigram's running stats.

    `latency_ms` is the time to type the *second* key given the first
    (i.e. the second keystroke's own latency) -- the standard digraph
    timing measure. `correct` means both keys of the pair were typed
    correctly; a pair with either key wrong doesn't count toward timing
    (same "only time error-free attempts" rule as the per-key model).
    """
    new_ema = (
        latency_ms
        if stat.ema_time_ms is None
        else EMA_ALPHA_TIME * latency_ms + (1 - EMA_ALPHA_TIME) * stat.ema_time_ms
    ) if correct else stat.ema_time_ms

    accuracy_sample = 1.0 if correct else 0.0
    new_accuracy = (
        accuracy_sample
        if stat.accuracy_rolling is None
        else EMA_ALPHA_ACCURACY * accuracy_sample + (1 - EMA_ALPHA_ACCURACY) * stat.accuracy_rolling
    )

    return BigramStat(
        learner_id=stat.learner_id,
        key1=stat.key1,
        key2=stat.key2,
        ema_time_ms=new_ema,
        accuracy_rolling=new_accuracy,
        sample_count=stat.sample_count + 1,
    )


def bigrams_from_keystrokes(keystrokes: list[KeystrokeEvent]) -> list[tuple[str, str, bool, int]]:
    """Derive consecutive (key1, key2, pair_correct, latency_ms) tuples
    from an ordered list of keystrokes in one activity step.
    """
    pairs = []
    for first, second in zip(keystrokes, keystrokes[1:]):
        pair_correct = first.correct and second.correct
        pairs.append((first.expected_char, second.expected_char, pair_correct, second.latency_ms))
    return pairs
