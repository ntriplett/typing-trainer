"""The fading keyboard hint, DB side: each key's support, the learner's
More/Less offset and grown-up override, a lesson's hint plan, and folding a
finished lesson back in. The rules themselves are app/hint_model.py.

Settings (learner_setting):
    hint_override     "auto" (the brain decides) | "full" | "off"
    hint_nudge        the More/Less offset added to every key (decays each lesson)
    hint_more_clicks  recent More clicks, a reliance signal (decays each lesson)
"""

from __future__ import annotations

import random
import sqlite3
from typing import Iterable, Literal

from app import db, hint_model as hm
from app.activities.base import KeystrokeEvent
from app.activities.teach_curriculum import INTRO_ID, PAIR_ID

OVERRIDE = "hint_override"
NUDGE = "hint_nudge"
MORE_CLICKS = "hint_more_clicks"
RELIANCE_WINDOW = 400
REPORT_MIN_PRESSES = 20  # the grown-ups' report shows a key's lift from this many presses
PLACEMENT_SUPPORT = 3.0  # a key the learner said at placement they knew: blank, lights come late  # newest hint-system keystrokes looked at for reliance

FREE_REASON = "hint_free"
SOLO_REASON = "hint_solo"
GRADUATION_REASONS = tuple(name for name, _ in hm.GRADUATIONS)


# --- settings ----------------------------------------------------------------------


def override(conn: sqlite3.Connection, learner_id: int) -> str:
    value = db.get_setting(conn, learner_id, OVERRIDE)
    return value if value in hm.OVERRIDES else "auto"


def set_override(conn: sqlite3.Connection, learner_id: int, value: str) -> None:
    if value not in hm.OVERRIDES:
        raise ValueError(f"Unknown hint override {value!r}")
    db.set_setting(conn, learner_id, OVERRIDE, value)


def _float_setting(conn: sqlite3.Connection, learner_id: int, key: str) -> float:
    try:
        return float(db.get_setting(conn, learner_id, key) or 0)
    except ValueError:
        return 0.0


def nudge_offset(conn: sqlite3.Connection, learner_id: int) -> float:
    return _float_setting(conn, learner_id, NUDGE)


# --- supports ----------------------------------------------------------------------


def lesson_keys(text: str) -> list[str]:
    """The hint keys a prompt uses, in first-seen order."""
    return list(dict.fromkeys(hm.hint_key(c) for c in text))


def placement_keys(conn: sqlite3.Connection, learner_id: int) -> set[str]:
    """Keys the learner said at placement they already knew."""
    out: set[str] = set()
    for ref, source in db.list_taught(conn, learner_id).items():
        module, keys = ref.split(":", 1)
        if source == "placement":
            out |= {" "} if module == INTRO_ID else set(keys) if module == PAIR_ID else set()
    return out


def supports(conn: sqlite3.Connection, learner_id: int, keys: Iterable[str]) -> dict[str, float]:
    """Each key's stored support. A key with none yet gets a starting one,
    saved so it stays put: from its old stats, or PLACEMENT_SUPPORT for a key
    the learner said at placement they already knew."""
    stored = db.get_key_hints(conn, learner_id)
    keys = list(keys)
    placement = placement_keys(conn, learner_id) if any(k not in stored for k in keys) else set()
    out = {}
    for key in keys:
        if key not in stored:
            stat = db.get_key_stat(conn, learner_id, key)
            if key in placement:  # placement fills in guessed stats: don't trust them
                start = PLACEMENT_SUPPORT
            elif stat is None or stat.sample_count == 0:
                start = hm.NEW_KEY_SUPPORT
            else:
                start = hm.starting_support(stat.accuracy_rolling, stat.mastered_at is not None)
            db.set_key_hint(conn, learner_id, key, start)
            stored[key] = start
        out[key] = stored[key]
    return out


def taught(conn: sqlite3.Connection, learner_id: int, keys: Iterable[str]) -> None:
    """Keys just taught start at full help."""
    for key in keys:
        db.set_key_hint(conn, learner_id, hm.hint_key(key), hm.NEW_KEY_SUPPORT)


def _effective(conn: sqlite3.Connection, learner_id: int, base: dict[str, float]) -> dict[str, float]:
    mode, offset = override(conn, learner_id), nudge_offset(conn, learner_id)
    return {k: round(hm.effective(s, offset, mode), 3) for k, s in base.items()}


def lesson_plan(
    conn: sqlite3.Connection,
    learner_id: int,
    text: str,
    *,
    comfort: bool = False,
    rng: random.Random | None = None,
    solo: bool = True,
) -> dict:
    """The hints a lesson's page runs with (practice_stage.js)."""
    mode = override(conn, learner_id)
    keys = _effective(conn, learner_id, supports(conn, learner_id, lesson_keys(text)))
    auto = mode == "auto"
    return {
        "mode": mode,
        "keys": keys,
        "keyboard": hm.keyboard_needed(keys.values()),
        "solo_lines": hm.plan_solo_lines(rng or random.Random(), keys.values(), comfort) if auto and solo else [],
        "rescue": hm.rescue_params() if auto else None,
    }


# --- More / Less ---------------------------------------------------------------------


def _recent_presses(conn: sqlite3.Connection, learner_id: int) -> list[hm.Press]:
    out = []
    for key, correct, latency, support, solo in db.recent_keystrokes(conn, learner_id, limit=RELIANCE_WINDOW * 4):
        if support is not None:
            out.append(hm.Press(hm.hint_key(key), correct, latency, support, solo))
            if len(out) >= RELIANCE_WINDOW:
                break
    return out


def nudge(
    conn: sqlite3.Connection, learner_id: int, direction: Literal["more", "less"], keys: Iterable[str]
) -> dict:
    """A More/Less click: move the learner-wide offset, by less for a learner
    who leans on help. Returns the new effective supports for `keys`."""
    clicks = _float_setting(conn, learner_id, MORE_CLICKS)
    level = hm.reliance(_recent_presses(conn, learner_id), round(clicks))
    step = hm.nudge_step(direction, level)
    offset = hm.apply_nudge(nudge_offset(conn, learner_id), step)
    db.set_setting(conn, learner_id, NUDGE, f"{offset:.3f}")
    if direction == "more":
        db.set_setting(conn, learner_id, MORE_CLICKS, f"{clicks + 1:.3f}")
    keys = [hm.hint_key(k) for k in keys]
    return {
        "nudge": offset,
        "step": round(step, 3),
        "reliance": round(level, 3),
        "keys": _effective(conn, learner_id, supports(conn, learner_id, keys)),
    }


# --- a finished lesson ------------------------------------------------------------------


def hint_seen(ke: KeystrokeEvent) -> str | None:
    return hm.press_kind(ke.hint_support, ke.latency_ms, ke.solo)


def presses(keystrokes: list[KeystrokeEvent], plan: dict | None) -> list[hm.Press]:
    """The lesson's keystrokes as the hint model sees them. Solo only counts
    when the lesson had solo lines; no plan means no hint system at all."""
    solo_ok = bool(plan and plan.get("solo_lines"))
    out = []
    for ke in keystrokes:
        support = None if plan is None or ke.hint_support is None else hm.clamp(ke.hint_support)
        out.append(hm.Press(hm.hint_key(ke.expected_char), ke.correct, ke.latency_ms, support, ke.solo and solo_ok))
    return out


def finish(
    conn: sqlite3.Connection, learner_id: int, lesson_ref: str, lesson_presses: list[hm.Press], plan: dict | None
) -> list[tuple[int, str, str]]:
    """Ratchet each key's support, let the More/Less offset fade, and work out
    the coins: (amount, reason, ref). Only "auto" lessons move or pay anything."""
    for key in (NUDGE, MORE_CLICKS):
        value = _float_setting(conn, learner_id, key)
        if value:
            db.set_setting(conn, learner_id, key, f"{hm.decay_nudge(value):.3f}")
    counted = [p for p in lesson_presses if p.support is not None]
    if plan is None or plan.get("mode") != "auto" or not counted:
        return []

    by_key: dict[str, list[hm.Press]] = {}
    for p in counted:
        by_key.setdefault(p.key, []).append(p)
    base = supports(conn, learner_id, by_key)
    per_day = db.key_day_presses(conn, learner_id)
    coins = []
    for key, key_presses in by_key.items():
        # No finished day with this key yet (a new learner, a new letter): guess from this lesson.
        day = per_day.get(key) or len(key_presses) * hm.LESSONS_PER_DAY_GUESS
        after = hm.ratchet(base[key], key_presses, day)
        db.set_key_hint(conn, learner_id, key, after)
        for reason in hm.graduations(base[key], after):
            if not db.has_coin_entry(conn, learner_id, reason, key):
                coins.append((hm.GRADUATION_COINS, reason, key))
    coins.append((hm.free_bonus(counted), FREE_REASON, lesson_ref))
    coins.append((hm.solo_bonus(counted), SOLO_REASON, lesson_ref))
    return [c for c in coins if c[0] > 0]


# --- for grown-ups ------------------------------------------------------------------------


def report(conn: sqlite3.Connection, learner_id: int, limit: int = 8000) -> dict:
    """Per key: support now and the measured lift."""
    rows = [
        hm.Press(hm.hint_key(key), correct, latency, support, solo)
        for key, correct, latency, support, solo in db.recent_keystrokes(conn, learner_id, limit=limit, practice_only=True)
        if support is not None
    ]
    lifts = hm.lift(rows, min_presses=0)  # every key its own row; the page marks thin ones
    for key in db.get_key_hints(conn, learner_id):
        lifts.setdefault(key, hm.KeyLift())
    return {
        "min_presses": REPORT_MIN_PRESSES,
        "mode": override(conn, learner_id),
        "nudge": nudge_offset(conn, learner_id),
        "supports": db.get_key_hints(conn, learner_id),
        "keys": {
            k: {
                "aided": v.aided, "aided_correct": v.aided_correct, "aided_ms": v.aided_ms,
                "free": v.free, "free_correct": v.free_correct, "free_ms": v.free_ms,
                "solo": v.solo, "solo_correct": v.solo_correct,
                "early": v.early, "waited_for": v.waited_for, "lift": v.lift,
            }
            for k, v in lifts.items()
        },
    }
