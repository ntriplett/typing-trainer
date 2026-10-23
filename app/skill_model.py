"""The adaptive core: per-key confidence, accuracy, and unlock logic.

Pure functions over app.models.KeyStat — no DB, no FastAPI, no clock
side effects beyond an explicit `now` parameter. That's deliberate: the
scheduler and the API layer are the only things that touch time/DB/UI;
this module is trivially unit-testable in isolation (PLAN.md Section 8).

Design (PLAN.md Sections 2 and 5), building on the keybr reference
design but fixing its two known gaps:
  - confidence = target_ms_per_keystroke / EMA(latency of CORRECT keystrokes)
  - EMA_ALPHA weights recent performance over old
  - accuracy_rolling is an EMA over *every* attempt's correctness (so a
    fast-but-wrong key doesn't look mastered) -- the accuracy-floor fix
  - sample_count counts *every* attempt (correct + incorrect) and gates
    mastery, so a key can't "master" off one lucky keystroke -- the
    minimum-sample-count fix
  - once mastered, a key stays in the active set even if it regresses;
    regression is surfaced via `needs_review` instead, so the scheduler
    can re-surface it in warmup without un-teaching it
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.models import KeyStat

# 30 WPM end goal (PLAN.md Section 1) == 150 CPM (1 word ~= 5 chars) ==
# 400ms/keystroke. This is the asymptotic target confidence=1.0 aims at,
# not an early expectation.
TARGET_MS_PER_KEYSTROKE = 400.0

EMA_ALPHA_TIME = 0.1
EMA_ALPHA_ACCURACY = 0.15

ACCURACY_FLOOR = 0.95
MIN_SAMPLES_FOR_MASTERY = 20

# Home-row first, then top row, then bottom row, then numbers -- better
# for building finger discipline in a beginner than pure letter-frequency
# order (PLAN.md Section 2).
KEY_ORDER: tuple[str, ...] = (
    # home row
    "f", "j", "d", "k", "s", "l", "a", ";", "g", "h",
    # top row
    "r", "u", "e", "i", "w", "o", "q", "p", "t", "y",
    # bottom row
    "v", "m", "c", ",", "x", ".", "z", "/", "b", "n",
    # numbers
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
)

INITIAL_ACTIVE_KEY_COUNT = 2


def new_key_stat(learner_id: int, key: str) -> KeyStat:
    """A never-attempted key's starting state."""
    return KeyStat(
        learner_id=learner_id,
        key=key,
        ema_time_ms=None,
        confidence=0.0,
        accuracy_rolling=None,
        sample_count=0,
        unlocked_at=None,
        mastered_at=None,
    )


def _confidence(ema_time_ms: float | None) -> float:
    if ema_time_ms is None or ema_time_ms <= 0:
        return 0.0
    return TARGET_MS_PER_KEYSTROKE / ema_time_ms


def record_attempt(stat: KeyStat, *, correct: bool, latency_ms: int, now: datetime) -> KeyStat:
    """Fold one keystroke attempt into a key's stats. Returns a new KeyStat."""
    # Timing only reflects error-free keystrokes -- an error's latency
    # includes hesitation/correction time that isn't representative of
    # how fast the key is actually known.
    if correct:
        new_ema = (
            latency_ms
            if stat.ema_time_ms is None
            else EMA_ALPHA_TIME * latency_ms + (1 - EMA_ALPHA_TIME) * stat.ema_time_ms
        )
    else:
        new_ema = stat.ema_time_ms

    accuracy_sample = 1.0 if correct else 0.0
    new_accuracy = (
        accuracy_sample
        if stat.accuracy_rolling is None
        else EMA_ALPHA_ACCURACY * accuracy_sample + (1 - EMA_ALPHA_ACCURACY) * stat.accuracy_rolling
    )

    new_sample_count = stat.sample_count + 1
    new_confidence = _confidence(new_ema)

    candidate = KeyStat(
        learner_id=stat.learner_id,
        key=stat.key,
        ema_time_ms=new_ema,
        confidence=new_confidence,
        accuracy_rolling=new_accuracy,
        sample_count=new_sample_count,
        unlocked_at=stat.unlocked_at,
        mastered_at=stat.mastered_at,
    )

    if stat.mastered_at is None and is_mastered(candidate):
        candidate = KeyStat(
            learner_id=candidate.learner_id,
            key=candidate.key,
            ema_time_ms=candidate.ema_time_ms,
            confidence=candidate.confidence,
            accuracy_rolling=candidate.accuracy_rolling,
            sample_count=candidate.sample_count,
            unlocked_at=candidate.unlocked_at,
            mastered_at=now,
        )

    return candidate


def is_mastered(stat: KeyStat) -> bool:
    """A key is solid once it's fast, accurate, and backed by enough samples."""
    return (
        stat.confidence >= 1.0
        and stat.accuracy_rolling is not None
        and stat.accuracy_rolling >= ACCURACY_FLOOR
        and stat.sample_count >= MIN_SAMPLES_FOR_MASTERY
    )


def needs_review(stat: KeyStat) -> bool:
    """A previously-mastered key whose accuracy has since regressed.

    Mastered keys never lose their active-set status (see `active_keys`),
    but a regression here is a signal the scheduler should re-surface
    this key in warmup/practice.
    """
    return (
        stat.mastered_at is not None
        and stat.accuracy_rolling is not None
        and stat.accuracy_rolling < ACCURACY_FLOOR
    )


def mark_unlocked(stat: KeyStat, now: datetime) -> KeyStat:
    if stat.unlocked_at is not None:
        return stat
    return KeyStat(
        learner_id=stat.learner_id,
        key=stat.key,
        ema_time_ms=stat.ema_time_ms,
        confidence=stat.confidence,
        accuracy_rolling=stat.accuracy_rolling,
        sample_count=stat.sample_count,
        unlocked_at=now,
        mastered_at=stat.mastered_at,
    )


def active_keys(
    key_stats: dict[str, KeyStat],
    key_order: tuple[str, ...] = KEY_ORDER,
    initial_count: int = INITIAL_ACTIVE_KEY_COUNT,
) -> list[str]:
    """Which keys are currently introduced, in `key_order`.

    The first `initial_count` keys are always active. After that, a key
    becomes active once every key ahead of it (in key_order) that's
    already active has been mastered at least once -- mastery never
    revokes active status, even if the key later regresses (that's what
    `needs_review` is for).
    """
    result: list[str] = list(key_order[:initial_count])

    for key in key_order[initial_count:]:
        preceding_active = result
        all_mastered = all(
            key_stats.get(k) is not None and key_stats[k].mastered_at is not None
            for k in preceding_active
        )
        if not all_mastered:
            break
        result.append(key)

    return result


KeyState = Literal["untaught", "teaching", "learning", "learned"]

# A lighter bar than full mastery (ACCURACY_FLOOR=0.95, MIN_SAMPLES_FOR_MASTERY=20):
# this is "good enough to not be the primary focus anymore," not "fully fluent."
# Deliberately separate from is_mastered()/mastered_at, which still gates when the
# *next* key ever gets introduced (active_keys(), unchanged) -- these 4 states are
# for the lesson planner's own "what should this lesson draw from" decisions.
MIN_SAMPLES_FOR_LEARNED = 10
LEARNED_ACCURACY_THRESHOLD = 0.80


def key_state(stat: KeyStat | None) -> KeyState:
    """Where a key sits in the teach -> practice pipeline, per your spec:
      - untaught: never introduced
      - teaching: introduced, but not enough attempts yet to trust an
        accuracy reading (still the direct-instruction phase)
      - learning: enough attempts to trust it, but accuracy below the
        "learned" bar
      - learned: accuracy at or above the bar

    This is a live snapshot, not a one-way ratchet -- a "learned" key
    whose accuracy later drops is reported as "learning" again (that's
    the signal the lesson planner uses to re-focus on it), unlike
    is_mastered()/mastered_at's permanent "ever reached" bookkeeping.
    """
    if stat is None or stat.unlocked_at is None:
        return "untaught"
    if stat.accuracy_rolling is None or stat.sample_count < MIN_SAMPLES_FOR_LEARNED:
        return "teaching"
    if stat.accuracy_rolling >= LEARNED_ACCURACY_THRESHOLD:
        return "learned"
    return "learning"


def keys_in_state(
    key_stats: dict[str, KeyStat], state: KeyState, key_order: tuple[str, ...] = KEY_ORDER
) -> list[str]:
    return [k for k in key_order if key_state(key_stats.get(k)) == state]


def next_keys_to_teach(
    allowed_keys: list[str], n: int = 1, key_order: tuple[str, ...] = KEY_ORDER
) -> list[str]:
    """The next `n` keys in sequence that aren't in `allowed_keys` yet --
    what a "teach" lesson's focus should be, per your spec: "a teaching
    session should really just work on those [focus] letters," one new
    key at a time by default rather than a random pair.

    Takes the already-computed allowed/active list rather than
    re-deriving "introduced" from raw key_stats: active_keys()'s
    initial keys count as introduced from the start, even before
    mark_unlocked() has persisted an unlocked_at for them (that only
    happens once a step actually touches them) -- key_state()'s
    unlocked_at-based "untaught" check would wrongly call those keys
    untaught in the meantime.
    """
    allowed_set = set(allowed_keys)
    return [k for k in key_order if k not in allowed_set][:n]


# Per-key weakness ranking used to live here as weakest_keys(); it's now
# app.recommender's _key_weakness() instead (recommend_warmup_keys()
# does everything this did, plus finger- and bigram-level signals), so
# there was no longer a reason to keep two copies of the same scoring
# logic in two modules.
