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
    # Structured multi-part lesson (show / type pages, per teach_steps.py),
    # for teach modules that are more than "type this string." A flat list of plain dicts rather
    # than a nested dataclass, so new experimental shapes don't need a
    # schema change here -- the front-end renders generically on `kind`.
    # None for every existing (flat-prompt) activity; unused fields cost
    # nothing since this is just a JSON response, not a DB column.
    micro_steps: list[dict] | None = None


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

    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool: ...

    def generate(
        self,
        focus_keys: list[str],
        allowed_keys: list[str],
        duration_s: int,
        rng: random.Random | None = None,
        chars_per_second: float = 2.0,
    ) -> ActivityContent: ...

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult: ...

    def coins(self, content: ActivityContent, result: ActivityResult) -> int: ...


# --- shared helpers used by every v1 module ----------------------------------
#
# Every lesson gets two key pools, not one (your call): `focus_keys` are
# what this lesson should actively work on (new/weak keys), `allowed_keys`
# are everything that's been introduced and is safe filler -- "it
# shouldn't use any letters in other lessons that weren't taught yet."
# Each activity kind picks its own focus_ratio (how much of its content
# draws from focus vs. allowed) when calling build_mixed_sequence.


def combined_pool(focus_keys: list[str], allowed_keys: list[str]) -> list[str]:
    """Fallback when one pool is empty -- never produce content from
    nothing when the other pool has something to offer.
    """
    pool = list(dict.fromkeys(focus_keys + allowed_keys))  # dedup, keep order
    if not pool:
        raise ValueError("Need at least 1 focus or allowed key to build an activity")
    return pool


def build_mixed_sequence(
    focus_keys: list[str],
    allowed_keys: list[str],
    focus_ratio: float,
    duration_s: int,
    rng: random.Random | None = None,
    chars_per_second: float = 2.0,
) -> str:
    """A space-separated pseudo-word sequence mixing two pools: each
    character is drawn from `focus_keys` with probability `focus_ratio`,
    otherwise from `allowed_keys` -- e.g. warmup's 75% focus / 25%
    allowed. Falls back to whichever pool is non-empty if the other is.
    """
    rng = rng or random.Random()
    # Space is a real key, but it's practiced as the gap between "words",
    # never drawn as a random character (that would make double spaces).
    # When it's a focus key, words get shorter so it comes up more often.
    space_focus = " " in focus_keys
    letters_focus = [k for k in focus_keys if k != " "]
    letters_allowed = [k for k in allowed_keys if k != " "]
    focus_pool = letters_focus or letters_allowed
    allowed_pool = letters_allowed or letters_focus
    if not focus_pool and not allowed_pool:
        raise ValueError("Need at least 1 focus or allowed letter to build an activity")

    length = max(10, int(duration_s * chars_per_second))
    chars = [
        rng.choice(focus_pool if rng.random() < focus_ratio else allowed_pool)
        for _ in range(length)
    ]
    # group into short "words" rather than one unbroken string
    word_len = 2 if space_focus else 4
    chunks = ["".join(chars[i : i + word_len]) for i in range(0, len(chars), word_len)]
    return " ".join(chunks)


def build_blocked_sequence(
    keys: list[str], duration_s: int, chars_per_second: float = 2.0, min_repeats: int = 4
) -> str:
    """A teaching-style sequence: each key repeated in its own block,
    e.g. ["f", "j"] -> "ffff jjjj" -- deliberately not randomized, since
    a first introduction should isolate one motion at a time.

    Scales with the time available like build_mixed_sequence does --
    this used to ignore duration_s entirely, which made a "teach" step
    finish almost instantly compared to every other phase (same time
    budget, wildly different amount of actual typing).
    """
    total_chars = max(min_repeats * len(keys), int(duration_s * chars_per_second))
    repeats = max(min_repeats, total_chars // len(keys))
    return " ".join(key * repeats for key in keys)


def build_space_sequence(
    allowed_keys: list[str], duration_s: int, chars_per_second: float = 2.0
) -> str:
    """Teaching the space bar: single known letters with a space after
    each ("f j f j"), so every other keystroke is a thumb press. Uses
    f/j when no letters are known yet -- they're always introduced
    alongside space (skill_model.INITIAL_ACTIVE_KEY_COUNT).
    """
    letters = [k for k in allowed_keys if k != " "] or ["f", "j"]
    count = max(6, int(duration_s * chars_per_second) // 2)
    return " ".join(letters[i % len(letters)] for i in range(count))


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


def default_coins(content: ActivityContent, result: ActivityResult) -> int:
    """The default coin rule (PLAN.md Section 11c): accuracy as a percent,
    scaled by how much of the prompt was actually typed -- 85% on a
    finished step pays 85, but ending a step halfway pays half. Modules
    with their own economics (e.g. a game) define coins() differently.

    Wrong keystrokes still advance the cursor (session.js), so attempts
    is a fair proxy for how far through the prompt the learner got.
    """
    completion = min(1.0, result.attempts / len(content.prompt)) if content.prompt else 1.0
    return round(result.accuracy * 100 * completion)
