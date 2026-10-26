"""Running brain-picked lessons: gather the brain's input from the DB,
serve the lesson it picks, and score/record it when it's done.

One lesson at a time, so the day can be free-form: practice a bit, visit
the store, practice more. Lessons in a row (no break of brain.SITTING_GAP)
share one `session` row, a "sitting"; each finished lesson is one
session_event whose summary_stats carry the plan too (kind, focus,
difficulty...), which is what the brain reads back as history.

A served-but-unfinished lesson lives in memory (_LESSONS) only: a server
restart just means asking for a new one.
"""

from __future__ import annotations

import itertools
import random
import sqlite3
from dataclasses import asdict, dataclass, replace
from datetime import datetime

from app import analytics, bigram_model, brain, daily, db, profiles, skill_model
from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent
from app.activities.practice_modules import PRACTICE_MODULES
from app.activities.practice_text import SkillSnapshot, snapshot_from_stats
from app.activities.teach_curriculum import INTRO_ID, PAIR_ID, known_before, lessons as curriculum_lessons
from app.activities.teach_modules import get_teach_module
from app.brain import BrainInput, KeyRecord, LessonPlan, LessonRecord, lesson_ref
from app.models import KeyStat

# Per-key windows from the keystroke log: the newest RECENT attempts, and
# the OLDER ones before those (regression = recent clearly below older).
RECENT_WINDOW = 50
OLDER_WINDOW = 100

KEY_MASTERED_BONUS = 50
# A lesson's active time can't be more than its wall-clock time (plus a
# little slack for clocks), or than this.
MAX_LESSON_SECONDS = 600

PRACTICE_BY_ID = {m.id: m for m in PRACTICE_MODULES}
_ids = itertools.count(1)


class LessonError(Exception):
    pass


@dataclass
class ServedLesson:
    id: int
    learner_id: int
    plan: LessonPlan
    content: ActivityContent
    served_at: datetime


_LESSONS: dict[int, ServedLesson] = {}


# --- what's been taught ---------------------------------------------------------


def _lesson_keys(ref: str) -> set[str]:
    module, keys = ref.split(":", 1)
    if module == INTRO_ID:
        return {" "}
    if module == PAIR_ID:
        return set(keys)
    return set()


def taught(conn: sqlite3.Connection, learner_id: int, key_stats: dict[str, KeyStat]) -> dict[str, str]:
    """ref -> source. Learners from before lessons were tracked get their
    unlocked keys' lessons filled in once ("legacy")."""
    refs = db.list_taught(conn, learner_id)
    if refs:
        return refs
    unlocked = {k for k, s in key_stats.items() if s.unlocked_at is not None}
    pairs = [l for l in curriculum_lessons() if l["module"] == PAIR_ID and set(l["keys"]) <= unlocked]
    if not pairs:
        return {}
    for ref in [lesson_ref(INTRO_ID, "")] + [lesson_ref(PAIR_ID, l["keys"]) for l in pairs]:
        db.mark_taught(conn, learner_id, ref, "legacy")
    return db.list_taught(conn, learner_id)


def taught_keys(conn: sqlite3.Connection, learner_id: int) -> set[str]:
    key_stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    return set().union(*(_lesson_keys(r) for r in taught(conn, learner_id, key_stats)))


def record_placement(conn: sqlite3.Connection, learner_id: int, known_keys: set[str]) -> None:
    """Placement answers count as taught lessons, so the brain starts there."""
    if not known_keys:
        return
    db.mark_taught(conn, learner_id, lesson_ref(INTRO_ID, ""), "placement")
    for l in curriculum_lessons():
        if l["module"] == PAIR_ID and set(l["keys"]) <= known_keys:
            db.mark_taught(conn, learner_id, lesson_ref(PAIR_ID, l["keys"]), "placement")


# --- the brain's input ------------------------------------------------------------


def key_records(conn: sqlite3.Connection, learner_id: int) -> dict[str, KeyRecord]:
    counts: dict[str, list[int]] = {}  # key -> [recent n, recent ok, older n, older ok]
    for key, correct in db.recent_keystrokes(conn, learner_id):
        c = counts.setdefault(key, [0, 0, 0, 0])
        if c[0] < RECENT_WINDOW:
            c[0] += 1
            c[1] += correct
        elif c[2] < OLDER_WINDOW:
            c[2] += 1
            c[3] += correct
    return {k: KeyRecord(*c) for k, c in counts.items()}


def _kind(phase: str) -> str | None:
    return {"teach": "learn", "learn": "learn", "warmup": "warmup", "practice": "practice"}.get(phase)


def history(conn: sqlite3.Connection, learner_id: int) -> list[LessonRecord]:
    out = []
    for e in db.recent_lesson_events(conn, learner_id):
        kind, stats = _kind(e["phase"]), e["stats"]
        if kind is None or "accuracy" not in stats:
            continue
        out.append(
            LessonRecord(
                kind=kind,
                activity_id=e["activity_id"],
                finished_at=e["ended_at"],
                accuracy=stats["accuracy"],
                wpm=stats.get("wpm", 0.0),
                finished_share=stats.get("finished_share", 1.0),
                difficulty=stats.get("difficulty"),
                predicted_wpm=stats.get("predicted_wpm"),
                focus_keys=tuple(stats.get("focus_keys", ())),
            )
        )
    return out


def brain_input(conn: sqlite3.Connection, learner_id: int, now: datetime) -> BrainInput:
    key_stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    refs = taught(conn, learner_id, key_stats)
    taught_keys = set().union(*(_lesson_keys(r) for r in refs)) if refs else set()
    placement = set().union(*(_lesson_keys(r) for r, src in refs.items() if src == "placement")) if refs else set()
    order = [lesson_ref(l["module"], l["keys"]) for l in curriculum_lessons()]
    newest = max((r for r, src in refs.items() if src == "lesson" and r.startswith(PAIR_ID)), key=order.index, default="")
    settings = daily.get_settings(conn, learner_id)
    day = daily.status(conn, learner_id, now)
    fallback = profiles.placement_wpm(conn, learner_id) or analytics.DEFAULT_STARTING_WPM
    return BrainInput(
        now=now,
        taught_lessons=frozenset(refs),
        taught_keys=frozenset(taught_keys),
        placement_keys=frozenset(placement),
        keys=key_records(conn, learner_id),
        bigrams=db.list_bigram_stats(conn, learner_id),
        history=history(conn, learner_id),
        learn_vs_practice=settings.learn_vs_practice,
        goal_seconds=settings.goal_seconds,
        practiced_seconds=day["practiced_seconds"],
        learns_today=day["learns"],
        fallback_wpm=analytics.estimate_starting_wpm(conn, learner_id, default=fallback) or fallback,
        newest_keys=tuple(sorted(_lesson_keys(newest))) if newest else (),
    )


# --- serving -------------------------------------------------------------------------


def _content(plan: LessonPlan, snapshot: SkillSnapshot, rng: random.Random) -> ActivityContent:
    if plan.kind == "learn":
        module = get_teach_module(plan.activity_id)
        focus = list(plan.teach_keys)
        known = known_before(focus) if plan.activity_id == PAIR_ID else []
        return module.generate(focus, known, duration_s=plan.duration_s, rng=rng)
    module = PRACTICE_BY_ID[plan.activity_id]
    content = module.generate(
        list(plan.focus_keys),
        list(plan.allowed_keys),
        plan.duration_s,
        rng,
        chars_per_second=brain.chars_per_second_for_wpm(plan.predicted_wpm),
        difficulty=plan.difficulty,
        skill=replace(snapshot, focus_bigrams=plan.focus_bigrams),
    )
    if plan.comfort:
        content = replace(content, instructions=f"{module.blurb} Nice and easy this time!")
    elif plan.kind == "warmup":
        content = replace(content, instructions=f"{module.blurb} A quick warmup to start.")
    return content


def serve_next(
    conn: sqlite3.Connection, learner_id: int, now: datetime, rng: random.Random | None = None
) -> ServedLesson:
    """Plan and generate the next lesson. Raises daily.PracticeResting when
    today's practice is all done."""
    daily.check_open(conn, learner_id, now)
    rng = rng or random.Random()
    inp = brain_input(conn, learner_id, now)
    plan = brain.plan_next_lesson(inp, rng)
    key_stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    snapshot = snapshot_from_stats(key_stats, inp.bigrams)
    lesson = ServedLesson(next(_ids), learner_id, plan, _content(plan, snapshot, rng), now)
    # One unfinished lesson per learner is plenty.
    for old in [k for k, v in _LESSONS.items() if v.learner_id == learner_id]:
        del _LESSONS[old]
    _LESSONS[lesson.id] = lesson
    return lesson


def get_served(lesson_id: int, learner_id: int) -> ServedLesson:
    lesson = _LESSONS.get(lesson_id)
    if lesson is None or lesson.learner_id != learner_id:
        raise LessonError("That lesson is over. Let's get a new one!")
    return lesson


def describe(lesson: ServedLesson) -> dict:
    p = lesson.plan
    title = next(
        (l["title"] for l in curriculum_lessons() if p.kind == "learn" and l["module"] == p.activity_id and l["keys"] == p.teach_keys),
        lesson.content.title,
    )
    return {
        "lesson_id": lesson.id,
        "kind": p.kind,
        "title": title,
        "activity_id": p.activity_id,
        "teach_keys": p.teach_keys,
        "focus_keys": list(p.focus_keys),
        "focus_bigrams": list(p.focus_bigrams),
        "difficulty": p.difficulty,
        "duration_s": p.duration_s,
        "predicted_wpm": round(p.predicted_wpm, 1),
        "comfort": p.comfort,
        "reasons": list(p.reasons),
    }


# --- finishing -------------------------------------------------------------------------


def _sitting(conn: sqlite3.Connection, learner_id: int, now: datetime) -> int:
    session = db.latest_session(conn, learner_id)
    last = session and (session.ended_at or session.started_at)
    if session and last and now - last <= brain.SITTING_GAP:
        return session.id
    return db.start_session(conn, learner_id).id


def apply_skill_model(
    conn: sqlite3.Connection, learner_id: int, new_keys: list[str], keystrokes: list[KeystrokeEvent], now: datetime
) -> list[str]:
    """Fold keystrokes into each key's stats (marking new_keys unlocked) and
    persist. Returns the keys mastered for the first time."""
    touched: dict[str, KeyStat] = {}

    def get_or_new(key: str) -> KeyStat:
        if key in touched:
            return touched[key]
        existing = db.get_key_stat(conn, learner_id, key)
        return existing if existing is not None else skill_model.new_key_stat(learner_id, key)

    for key in new_keys:
        touched[key] = skill_model.mark_unlocked(get_or_new(key), now)
    for ke in keystrokes:
        touched[ke.expected_char] = skill_model.record_attempt(
            get_or_new(ke.expected_char), correct=ke.correct, latency_ms=ke.latency_ms, now=now
        )

    newly_mastered = []
    for stat in touched.values():
        before = db.get_key_stat(conn, learner_id, stat.key)
        if stat.mastered_at is not None and (before is None or before.mastered_at is None):
            newly_mastered.append(stat.key)
        db.upsert_key_stat(conn, stat)
    return newly_mastered


def apply_bigram_model(conn: sqlite3.Connection, learner_id: int, keystrokes: list[KeystrokeEvent]) -> None:
    for key1, key2, correct, latency_ms in bigram_model.bigrams_from_keystrokes(keystrokes):
        existing = db.get_bigram_stat(conn, learner_id, key1, key2)
        stat = existing if existing is not None else bigram_model.new_bigram_stat(learner_id, key1, key2)
        db.upsert_bigram_stat(conn, bigram_model.record_bigram_attempt(stat, correct=correct, latency_ms=latency_ms))


def _coins(conn, learner_id: int, lesson: ServedLesson, result: ActivityResult, typed_part: ActivityContent):
    p = lesson.plan
    if p.kind == "learn":
        module = get_teach_module(p.activity_id)
        ref = lesson_ref(p.activity_id, p.teach_keys)
        first = getattr(module, "first_finish_coins", 0)
        if first and not db.has_coin_entry(conn, learner_id, "teach_first", ref):
            return first, "teach_first", ref
        return module.coins(replace(typed_part, prompt=""), result), "teach", ref
    module = PRACTICE_BY_ID[p.activity_id]
    return module.coins(typed_part, result), "lesson", f"lesson:{p.kind}:{p.activity_id}"


def complete(
    conn: sqlite3.Connection,
    learner_id: int,
    lesson_id: int,
    keystrokes: list[KeystrokeEvent],
    active_ms: int,
    skipped_chars: int,
    now: datetime,
) -> dict:
    lesson = get_served(lesson_id, learner_id)
    del _LESSONS[lesson_id]
    p = lesson.plan
    module = get_teach_module(p.activity_id) if p.kind == "learn" else PRACTICE_BY_ID[p.activity_id]
    result = module.score(lesson.content, keystrokes)

    typed_len = max(0, len(lesson.content.prompt) - skipped_chars)
    typed_part = replace(lesson.content, prompt=lesson.content.prompt[:typed_len])
    finished_share = 1.0 if p.kind == "learn" or not typed_len else min(1.0, result.attempts / typed_len)
    wall = (now - lesson.served_at).total_seconds() + 2
    active_seconds = max(0.0, min(active_ms / 1000, wall, MAX_LESSON_SECONDS))

    session_id = _sitting(conn, learner_id, now)
    event = db.log_session_event(conn, session_id, p.kind, p.activity_id)
    for seq, ke in enumerate(keystrokes):
        db.log_keystroke(conn, event.id, seq, ke.expected_char, ke.typed_char, ke.correct, ke.latency_ms)
    summary = asdict(result) | {
        "kind": p.kind,
        "finished_share": round(finished_share, 3),
        "active_seconds": round(active_seconds, 1),
        "difficulty": p.difficulty if p.kind != "learn" else None,
        "predicted_wpm": round(p.predicted_wpm, 2),
        "focus_keys": list(p.focus_keys),
        "focus_bigrams": list(p.focus_bigrams),
        "teach_keys": p.teach_keys,
        "comfort": p.comfort,
        "reasons": list(p.reasons),
    }
    db.end_session_event(conn, event.id, summary_stats=summary)
    db.touch_session(conn, session_id, now)

    new_keys = []
    if p.kind == "learn":
        new_keys = sorted(_lesson_keys(lesson_ref(p.activity_id, p.teach_keys)))
        db.mark_taught(conn, learner_id, lesson_ref(p.activity_id, p.teach_keys), "lesson")
    newly_mastered = apply_skill_model(conn, learner_id, new_keys, keystrokes, now)
    apply_bigram_model(conn, learner_id, keystrokes)

    earned = [_coins(conn, learner_id, lesson, result, typed_part)]
    earned += [(KEY_MASTERED_BONUS, "key_mastered", key) for key in newly_mastered]
    coins_earned = []
    for amount, reason, ref in earned:
        if amount > 0:
            db.add_coins(conn, learner_id, amount, reason, ref=ref)
            coins_earned.append({"amount": amount, "reason": reason})

    milestones = daily.add_practice(conn, learner_id, active_seconds, now, learned=p.kind == "learn")
    coins_earned += [{"amount": m["coins"], "reason": f"daily_{m['milestone']}"} for m in milestones if m["coins"]]
    return {
        "result": asdict(result),
        "kind": p.kind,
        "finished_share": finished_share,
        "active_seconds": active_seconds,
        "coins_earned": coins_earned,
        "tokens_earned": [{"amount": m["tokens"], "reason": f"daily_{m['milestone']}"} for m in milestones],
        "coin_balance": db.get_coin_balance(conn, learner_id),
        "token_balance": db.get_token_balance(conn, learner_id),
        "day": daily.status(conn, learner_id, now),
    }
