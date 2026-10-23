"""The module contract every teach/practice/eval/game/warmup activity
implements (PLAN.md Section 7), plus shared data shapes and scoring
helpers so each module isn't reimplementing the same arithmetic.

The scheduler (once built) only ever talks to this interface -- it
never knows which specific module it's running, so adding a new
activity later is a registration, not a scheduler change.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# Kinds match the session phases in PLAN.md Section 6.
Kind = str  # "warmup" | "teach" | "practice" | "eval" | "game"


@dataclass(frozen=True, slots=True)
class KeystrokeEvent:
    expected_char: str
    typed_char: str
    correct: bool
    latency_ms: int


@dataclass(frozen=True, slots=True)
class ActivityContent:
    activity_id: str
    kind: Kind
    keys: list[str]
    prompt: str
    instructions: str = ""


@dataclass(frozen=True, slots=True)
class ActivityResult:
    activity_id: str
    keys: list[str]
    attempts: int
    correct: int
    accuracy: float
    wpm: float
    avg_latency_ms: float
    # Generic hook for the front-end to pick a flourish (confetti, sound,
    # sprite) without the backend knowing what it looks like -- the
    # extensibility point from PLAN.md Section 11a. Values are a
    # deliberately simple v1 set; "improved" (vs. the learner's own past
    # performance) needs session-history comparison the scheduler will
    # add later, so it's not one of these yet.
    reward_signal: str  # "nailed_it" | "solid" | "struggled"


@runtime_checkable
class Activity(Protocol):
    id: str
    kind: Kind

    def is_eligible(self, active_keys: list[str]) -> bool: ...

    def generate(
        self,
        active_keys: list[str],
        duration_s: int,
        rng: random.Random | None = None,
        chars_per_second: float = 2.0,
    ) -> ActivityContent: ...

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult: ...


# --- shared helpers used by every v1 module ----------------------------------


def pick_two_keys(active_keys: list[str], rng: random.Random | None = None) -> list[str]:
    """Pick 2 distinct keys to focus an activity on.

    Falls back gracefully if fewer than 2 keys are active yet (early in
    a learner's journey) by repeating the single available key.
    """
    rng = rng or random.Random()
    if len(active_keys) >= 2:
        return rng.sample(active_keys, 2)
    if len(active_keys) == 1:
        return [active_keys[0], active_keys[0]]
    raise ValueError("Need at least 1 active key to build an activity")


def build_random_sequence(
    keys: list[str], duration_s: int, rng: random.Random | None = None, chars_per_second: float = 2.0
) -> str:
    """A simple space-separated pseudo-word sequence drawn from `keys`.

    Length scales with the time available. Real pseudo-word generation
    (pronounceable clusters, per PLAN.md Section 2) can replace this
    later without changing the module contract.
    """
    rng = rng or random.Random()
    length = max(10, int(duration_s * chars_per_second))
    chars = [rng.choice(keys) for _ in range(length)]
    # group into chunks of 4 so it reads like short "words" rather than
    # one unbroken string
    chunks = ["".join(chars[i : i + 4]) for i in range(0, len(chars), 4)]
    return " ".join(chunks)


def build_blocked_sequence(
    keys: list[str], duration_s: int, chars_per_second: float = 2.0, min_repeats: int = 4
) -> str:
    """A teaching-style sequence: each key repeated in its own block,
    e.g. ["f", "j"] -> "ffff jjjj" -- deliberately not randomized, since
    a first introduction should isolate one motion at a time.

    Scales with the time available like build_random_sequence does --
    this used to ignore duration_s entirely, which made a "teach" step
    finish almost instantly compared to every other phase (same time
    budget, wildly different amount of actual typing).
    """
    total_chars = max(min_repeats * len(keys), int(duration_s * chars_per_second))
    repeats = max(min_repeats, total_chars // len(keys))
    return " ".join(key * repeats for key in keys)


def score_attempt(
    activity_id: str, keys: list[str], keystrokes: list[KeystrokeEvent]
) -> ActivityResult:
    """Generic scoring shared by all v1 modules: accuracy, WPM, reward tier.

    WPM uses the standard 5-chars-per-word convention, over the actual
    elapsed time implied by summed keystroke latencies.
    """
    attempts = len(keystrokes)
    correct = sum(1 for k in keystrokes if k.correct)
    accuracy = correct / attempts if attempts else 0.0

    total_ms = sum(k.latency_ms for k in keystrokes)
    avg_latency_ms = total_ms / attempts if attempts else 0.0
    minutes = (total_ms / 1000) / 60 if total_ms else 0.0
    wpm = (correct / 5) / minutes if minutes > 0 else 0.0

    if accuracy >= 0.95:
        reward_signal = "nailed_it"
    elif accuracy >= 0.80:
        reward_signal = "solid"
    else:
        reward_signal = "struggled"

    return ActivityResult(
        activity_id=activity_id,
        keys=keys,
        attempts=attempts,
        correct=correct,
        accuracy=accuracy,
        wpm=wpm,
        avg_latency_ms=avg_latency_ms,
        reward_signal=reward_signal,
    )
