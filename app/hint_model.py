"""The fading keyboard hint: how much help each key gets, and how that changes.

Pure functions, like app/skill_model.py: no DB, no clock. The DB side lives
in app/hints.py.

Each key has a *support* number from 0.0 (no help) to 5.0 (today's full
hint). What the keyboard shows for it (display()):

    5.0      letters, finger and key light at once
    4 - 5    letters, finger lights after 0 -> 1.5 s, key 0.4 s later
    3 - 4    blank keys, finger after 1.5 -> 3 s, key 1 s later
    2 - 3    blank keys, finger after 3 -> 5 s, key never
    1 - 2    blank keys, hands only
    < 1      this key doesn't need the keyboard at all

Research behind it (the guidance hypothesis, progressive prompt delay):
help that is always on makes practice look good and learning poor, so
the help comes later and later as a key is learned, but it always comes
if the learner waits. Misses add help quickly; right answers take it away
slowly, aiming at about 85-90% right.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Literal

from app.finger_map import KEY_TO_FINGER

PressKind = Literal["free", "finger", "key"]

MAX_SUPPORT = 5.0
NEW_KEY_SUPPORT = 5.0  # a key just taught gets today's full hint
LETTERS_BELOW = 4.0  # the key's letter hides below this
KEY_LIGHT_BELOW = 2.0  # below this the key never lights, only the finger...
FINGER_LIGHT_BELOW = 2.0  # ...and below this not even the finger
KEYBOARD_BELOW = 1.0  # a lesson whose keys are all below this has no keyboard

# The ratchet. Time-based: a key moves LEVELS_PER_DAY x (accuracy - TARGET)
# levels over a day's worth of its own presses, however many that is, so
# 90% right is about 1 level a day, 100% about 2, 80% holds, 70% goes back
# up about 1. Per press that's a step of 1/day_presses of that:
#     right:  -LEVELS_PER_DAY * (1 - TARGET) * CREDIT[what was lit] / day_presses
#     miss:   +LEVELS_PER_DAY * TARGET / day_presses
# A right answer after a light came on takes help away a bit slower.
TARGET_ACCURACY = 0.80
LEVELS_PER_DAY = 10.0  # per unit of accuracy above the target
CREDIT = {"free": 1.0, "finger": 0.9, "key": 0.8}
DAY_PRESSES_FLOOR = 20  # a rare key doesn't jump a level on a couple of presses
DEFAULT_DAY_PRESSES = 30
LESSONS_PER_DAY_GUESS = 12  # a 10 minute day is 10-16 lessons: a key's day, before there's one to measure
MAX_DROP_PER_LESSON = 0.5
MAX_RISE_PER_LESSON = 1.5

# How much a press counts toward mastery (skill_model.record_attempt weight).
WEIGHT_FREE = 1.0
WEIGHT_FINGER = 0.3
WEIGHT_GUIDED = 0.0  # the key lit up, or its letter was showing

# More / Less help buttons: a learner-wide offset added to every key.
NUDGE_LESS = -0.5
NUDGE_MORE_MAX = 1.0
NUDGE_MORE_MIN = 0.1  # what "More" adds when the learner leans on help a lot
NUDGE_LIMIT = 2.0
NUDGE_DECAY = 0.5  # the offset halves after each lesson: the brain stays in charge

# The rescue: an offset for this lesson only, on top of every key's support,
# that follows the last RESCUE_WINDOW presses. Below RESCUE_BELOW it climbs
# each press (all the way to full help if need be); at RESCUE_EASE or better
# it eases off each right press; in between it holds. Never below zero, and
# gone when the lesson ends: only ratchet() carries over.
# practice_stage.js runs it (rescue_step() is the reference, sent as params).
RESCUE_WINDOW = 15
RESCUE_MIN_PRESSES = 5
RESCUE_BELOW = 0.75
RESCUE_EASE = 0.90
RESCUE_UP = 0.25
RESCUE_DOWN = 0.1

# Solo lines: a random line now and then with no hints at all.
SOLO_CHANCE = 0.25
SOLO_MAX_MEAN_SUPPORT = 3.0  # only once the lesson's keys are past the letters
SOLO_LINES_PLANNED = 40

# Coins
FREE_BONUS_MAX = 50  # a lesson where every press was right before any light
SOLO_BONUS = 25  # a lesson's solo presses at SOLO_BONUS_ACCURACY or better
SOLO_BONUS_ACCURACY = 0.9
SOLO_BONUS_MIN_PRESSES = 5
GRADUATION_COINS = 100
LETTERS_OFF = "hint_letters_off"  # support fell below LETTERS_BELOW
BY_HEART = "hint_by_heart"  # support fell below FINGER_LIGHT_BELOW
GRADUATIONS = ((LETTERS_OFF, LETTERS_BELOW), (BY_HEART, FINGER_LIGHT_BELOW))

OVERRIDES = ("auto", "full", "off")


@dataclass(frozen=True, slots=True)
class HintDisplay:
    letter: bool  # the key's letter shows on the keyboard
    finger_ms: int | None  # the finger lights this long after the key comes up (None: never)
    key_ms: int | None  # the key lights this long after (None: never)


@dataclass(frozen=True, slots=True)
class Press:
    """One keystroke as the hint system sees it."""

    key: str  # hint_key() of the expected character
    correct: bool
    latency_ms: int
    support: float | None  # the effective support it was typed with (None: no hint system)
    solo: bool = False


def hint_key(ch: str) -> str:
    """Capitals share their letter's support (same finger, plus Shift)."""
    return ch.lower()


def clamp(support: float) -> float:
    return max(0.0, min(MAX_SUPPORT, support))


def display(support: float) -> HintDisplay:
    s = clamp(support)
    if s >= LETTERS_BELOW:
        t = s - LETTERS_BELOW  # 0..1
        finger = round(1500 * (1 - t))
        return HintDisplay(True, finger, finger + round(400 * (1 - t)))
    if s >= 3.0:
        finger = round(3000 - 1500 * (s - 3.0))
        return HintDisplay(False, finger, finger + 1000)
    if s >= FINGER_LIGHT_BELOW:
        return HintDisplay(False, round(5000 - 2000 * (s - 2.0)), None)
    return HintDisplay(False, None, None)


def keyboard_needed(supports: Iterable[float]) -> bool:
    return any(s >= KEYBOARD_BELOW for s in supports)


def press_kind(support: float | None, latency_ms: int, solo: bool = False) -> PressKind | None:
    """What was lit when the key was pressed. None: typed without the hint system."""
    if support is None:
        return None
    if solo:
        return "free"
    d = display(support)
    if d.key_ms is not None and latency_ms >= d.key_ms:
        return "key"
    if d.finger_ms is not None and latency_ms >= d.finger_ms:
        return "finger"
    return "free"


def mastery_weight(press: Press) -> float:
    kind = press_kind(press.support, press.latency_ms, press.solo)
    if kind is None or press.solo:
        return WEIGHT_FREE
    if kind == "key" or display(press.support).letter:
        return WEIGHT_GUIDED
    return WEIGHT_FINGER if kind == "finger" else WEIGHT_FREE


def ratchet(support: float, presses: list[Press], day_presses: float = DEFAULT_DAY_PRESSES) -> float:
    """One lesson's presses of one key -> its new support. `day_presses` is
    how many times a day the learner types this key (hints.day_presses)."""
    per_press = LEVELS_PER_DAY / max(DAY_PRESSES_FLOOR, day_presses)
    delta = 0.0
    for p in presses:
        kind = press_kind(p.support, p.latency_ms, p.solo)
        if kind is None:
            continue
        delta += -per_press * (1 - TARGET_ACCURACY) * CREDIT[kind] if p.correct else per_press * TARGET_ACCURACY
    if not delta:
        return support
    return clamp(support + max(-MAX_DROP_PER_LESSON, min(MAX_RISE_PER_LESSON, delta)))


def starting_support(accuracy: float | None, mastered: bool) -> float:
    """For a key that was learned before hints faded (no key_hint row yet).
    Old accuracy may have been typed with the paid hint, so never trust it much."""
    if mastered:
        return 2.5  # finger lights after ~4 s: mastery may have been typed with the paid hint
    if accuracy is None:
        return NEW_KEY_SUPPORT
    if accuracy >= 0.97:
        return 3.0
    if accuracy >= 0.90:
        return 4.0
    return 4.5


def effective(support: float, nudge: float, override: str) -> float:
    if override == "full":
        return MAX_SUPPORT
    if override == "off":
        return 0.0
    return clamp(support + nudge)


def rescue_step(offset: float, recent: list[bool]) -> float:
    """The rescue offset after a press; `recent` is this lesson's right/wrong so far, newest last."""
    window = recent[-RESCUE_WINDOW:]
    if len(window) < RESCUE_MIN_PRESSES:
        return offset
    accuracy = sum(window) / len(window)
    if accuracy < RESCUE_BELOW:
        offset += RESCUE_UP
    elif accuracy >= RESCUE_EASE and window[-1]:
        offset -= RESCUE_DOWN
    return clamp(offset)


def rescue_params() -> dict:
    """What practice_stage.js needs to run rescue_step()."""
    return {
        "window": RESCUE_WINDOW, "min_presses": RESCUE_MIN_PRESSES, "below": RESCUE_BELOW,
        "ease": RESCUE_EASE, "up": RESCUE_UP, "down": RESCUE_DOWN, "max": MAX_SUPPORT,
    }


def _light_coming(p: Press) -> bool:
    return p.support is not None and not p.solo and display(p.support).finger_ms is not None


def reliance(presses: list[Press], more_clicks: int) -> float:
    """0..1: how much the learner leans on help: how often they wait for a
    light that was going to come, pushed up by recent More clicks."""
    pending = [p for p in presses if _light_coming(p)]
    waited = sum(press_kind(p.support, p.latency_ms) != "free" for p in pending)
    base = waited / len(pending) if pending else 0.0
    return base + (1 - base) * (1 - 0.8 ** max(0, more_clicks))


def nudge_step(direction: Literal["more", "less"], reliance_level: float) -> float:
    if direction == "less":
        return NUDGE_LESS
    r = max(0.0, min(1.0, reliance_level))
    return NUDGE_MORE_MIN + (NUDGE_MORE_MAX - NUDGE_MORE_MIN) * (1 - r) ** 2


def apply_nudge(offset: float, step: float) -> float:
    return max(-NUDGE_LIMIT, min(NUDGE_LIMIT, offset + step))


def decay_nudge(offset: float) -> float:
    out = offset * NUDGE_DECAY
    return 0.0 if abs(out) < 0.05 else out


def plan_solo_lines(rng: random.Random, supports: Iterable[float], comfort: bool) -> list[int]:
    supports = list(supports)
    if comfort or not keyboard_needed(supports) or sum(supports) / len(supports) > SOLO_MAX_MEAN_SUPPORT:
        return []
    return [i for i in range(1, SOLO_LINES_PLANNED) if rng.random() < SOLO_CHANCE]


def free_bonus(presses: list[Press]) -> int:
    counted = [p for p in presses if p.support is not None]
    if not counted:
        return 0
    good = sum(p.correct and mastery_weight(p) == WEIGHT_FREE for p in counted)
    return round(FREE_BONUS_MAX * good / len(counted))


def solo_bonus(presses: list[Press]) -> int:
    solo = [p for p in presses if p.solo and p.support is not None]
    if len(solo) < SOLO_BONUS_MIN_PRESSES:
        return 0
    return SOLO_BONUS if sum(p.correct for p in solo) / len(solo) >= SOLO_BONUS_ACCURACY else 0


def graduations(before: float, after: float) -> list[str]:
    """Milestones crossed going from `before` to `after` support."""
    return [name for name, below in GRADUATIONS if before >= below > after]


@dataclass(frozen=True, slots=True)
class KeyLift:
    aided: int = 0  # presses after a light came on
    aided_correct: int = 0
    aided_ms: float | None = None  # mean latency of the right ones
    free: int = 0  # presses before any light (or with none coming)
    free_correct: int = 0
    free_ms: float | None = None
    solo: int = 0
    solo_correct: int = 0
    early: int = 0  # right presses before a light that was going to come
    waited_for: int = 0  # presses where a light was going to come

    @property
    def lift(self) -> float | None:
        """Accuracy with a light minus accuracy without (solo lines when there are enough)."""
        if not self.aided:
            return None
        if self.solo >= 10:
            base = self.solo_correct / self.solo
        elif self.free:
            base = self.free_correct / self.free
        else:
            return None
        return self.aided_correct / self.aided - base


def lift(presses: list[Press], min_presses: int = 20) -> dict[str, KeyLift]:
    """Per key; keys with fewer than `min_presses` are pooled into their finger ("finger:left_index")."""
    counted = [p for p in presses if p.support is not None]
    per_key: dict[str, int] = {}
    for p in counted:
        per_key[p.key] = per_key.get(p.key, 0) + 1

    def group(key: str) -> str:
        if per_key[key] >= min_presses or key not in KEY_TO_FINGER:
            return key
        return f"finger:{KEY_TO_FINGER[key]}"

    acc: dict[str, dict] = {}
    for p in counted:
        a = acc.setdefault(group(p.key), {f: 0 for f in KeyLift.__slots__} | {"aided_sum": 0, "free_sum": 0})
        if p.solo:
            a["solo"] += 1
            a["solo_correct"] += p.correct
            continue
        side = "free" if press_kind(p.support, p.latency_ms) == "free" else "aided"
        a[side] += 1
        if p.correct:
            a[f"{side}_correct"] += 1
            a[f"{side}_sum"] += p.latency_ms
        if _light_coming(p):
            a["waited_for"] += 1
            a["early"] += p.correct and side == "free"

    def mean(total: int, n: int) -> float | None:
        return total / n if n else None

    return {
        k: KeyLift(
            aided=a["aided"], aided_correct=a["aided_correct"], aided_ms=mean(a["aided_sum"], a["aided_correct"]),
            free=a["free"], free_correct=a["free_correct"], free_ms=mean(a["free_sum"], a["free_correct"]),
            solo=a["solo"], solo_correct=a["solo_correct"], early=a["early"], waited_for=a["waited_for"],
        )
        for k, a in acc.items()
    }
