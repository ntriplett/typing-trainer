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
import json
import random
import sqlite3
from dataclasses import asdict, dataclass, replace
from datetime import datetime

from app import analytics, bigram_model, brain, daily, db, garden, hint_model, hints, profiles, skill_model
from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent
from app.activities.practice_modules import PRACTICE_MODULES
from app.activities.practice_text import SkillSnapshot, snapshot_from_stats
from app.activities.teach_curriculum import INTRO_ID, PAIR_ID, known_before, lessons as curriculum_lessons
from app.activities.teach_modules import get_teach_module
from app.brain import MIN_RECENT_ATTEMPTS, BrainInput, KeyRecord, LessonPlan, LessonRecord, lesson_ref, solid_bar
from app.models import KeyStat

# Per-key windows from the keystroke log: the newest RECENT attempts, and
# the OLDER ones before those (regression = recent clearly below older).
RECENT_WINDOW = 50
OLDER_WINDOW = 100

# Three milestones for each key, each paid once: solid enough for the next new lesson
# (the same check as brain.unsolid_keys, so it follows the parent's slider), then 15
# WPM, then 30. The speed ones come late, and help with the last big buys.
KEY_BONUS = 500
KEY_SOLID = "key_solid"
KEY_HALFWAY = "key_halfway"
KEY_MASTERED = "key_mastered"
KEY_BONUS_REASONS = (KEY_SOLID, KEY_HALFWAY, KEY_MASTERED)
# None of them pay from the teach page: a key has to be typed in this many practice
# lessons first, and only practice keystrokes count toward them.
PRACTICE_LESSONS_FOR_BONUS = 2
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
    hints: dict | None = None  # hints.lesson_plan(); None for learn lessons (the teach page has its own)


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


# --- held back by a grown-up -------------------------------------------------------
# A grown-up can take a key pair out of the pool when it was learned too fast: its
# lesson is no longer taught, so practice leaves it out, and the brain teaches it again
# (the teach page, full keyboard help) once every key still in the pool is solid.
# What it opened stays open (earned_keys): the Pet Shop, reward pets, sharing.

HELD_BACK_SETTING = "held_back_lessons"


class HoldBackError(ValueError):
    pass


def held_back(conn: sqlite3.Connection, learner_id: int) -> list[str]:
    """Pair lesson refs a grown-up took out and the brain hasn't taught again yet."""
    raw = db.get_setting(conn, learner_id, HELD_BACK_SETTING)
    refs = json.loads(raw) if raw else []
    taught_now = db.list_taught(conn, learner_id)
    return [r for r in refs if r not in taught_now]


def _save_held(conn: sqlite3.Connection, learner_id: int, refs: list[str]) -> None:
    db.set_setting(conn, learner_id, HELD_BACK_SETTING, json.dumps(refs))


def _pair_ref(key: str) -> str:
    lesson = next((l for l in curriculum_lessons() if l["module"] == PAIR_ID and key in l["keys"]), None)
    if lesson is None:
        raise HoldBackError(f"{key!r} isn't a key with its own lesson.")
    return lesson_ref(PAIR_ID, lesson["keys"])


def hold_back(conn: sqlite3.Connection, learner_id: int, key: str) -> str:
    """Take `key`'s lesson (both of its keys) out of the pool. Returns the lesson's keys."""
    ref = _pair_ref(key)
    key_stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    if ref not in taught(conn, learner_id, key_stats):
        raise HoldBackError("That key isn't learned yet.")
    held = held_back(conn, learner_id)
    db.unmark_taught(conn, learner_id, ref)
    _save_held(conn, learner_id, [*held, ref])
    return ref.split(":", 1)[1]


def let_back(conn: sqlite3.Connection, learner_id: int, key: str) -> str:
    """Put a held-back lesson straight back in the pool, without teaching it again."""
    ref = _pair_ref(key)
    held = held_back(conn, learner_id)
    if ref not in held:
        raise HoldBackError("That key isn't held back.")
    db.mark_taught(conn, learner_id, ref, "grownup")
    _save_held(conn, learner_id, [r for r in held if r != ref])
    return ref.split(":", 1)[1]


def earned_keys(conn: sqlite3.Connection, learner_id: int) -> set[str]:
    """Keys learned at some point, held back or not: what opens rooms, shops and rewards."""
    return taught_keys(conn, learner_id).union(*(_lesson_keys(r) for r in held_back(conn, learner_id)))


def key_pool(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    """For the grown-ups' keyboard: each real key's state and accuracy."""
    pool, held = taught_keys(conn, learner_id), set().union(*(_lesson_keys(r) for r in held_back(conn, learner_id)))
    stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    records = key_records(conn, learner_id)
    out = []
    for key in skill_model.KEY_ORDER:
        state = "held" if key in held else "pool" if key in pool else "new"
        stat, record = stats.get(key), records.get(key)
        out.append({
            "key": key,
            "state": state,
            "pair": "" if key == " " else _pair_ref(key).split(":", 1)[1],
            "accuracy": stat.accuracy_rolling if stat else None,
            "recent_accuracy": record.recent_accuracy if record else None,
        })
    return out


def record_placement(conn: sqlite3.Connection, learner_id: int, known_keys: set[str]) -> None:
    """Placement answers count as taught lessons, so the brain starts there."""
    if not known_keys:
        return
    db.mark_taught(conn, learner_id, lesson_ref(INTRO_ID, ""), "placement")
    for l in curriculum_lessons():
        if l["module"] == PAIR_ID and set(l["keys"]) <= known_keys:
            db.mark_taught(conn, learner_id, lesson_ref(PAIR_ID, l["keys"]), "placement")


# --- the brain's input ------------------------------------------------------------


def key_records(conn: sqlite3.Connection, learner_id: int, practice_only: bool = False) -> dict[str, KeyRecord]:
    """Each attempt counts by its hint weight (hint_model.mastery_weight): typed
    with heavy help it doesn't count, with a little help it counts a little."""
    counts: dict[str, list[float]] = {}  # key -> [recent n, recent ok, older n, older ok]
    for key, correct, latency, support, solo in db.recent_keystrokes(conn, learner_id, practice_only=practice_only):
        w = hint_model.mastery_weight(hint_model.Press(key, correct, latency, support, solo))
        if w <= 0:
            continue
        c = counts.setdefault(key, [0.0, 0.0, 0.0, 0.0])
        if c[0] < RECENT_WINDOW:
            c[0] += w
            c[1] += w * correct
        elif c[2] < OLDER_WINDOW:
            c[2] += w
            c[3] += w * correct
    return {k: KeyRecord(*(round(x, 3) for x in c)) for k, c in counts.items()}


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
    content = _content(plan, snapshot, rng)
    plan_hints = None
    if plan.kind != "learn":
        plan_hints = hints.lesson_plan(
            conn, learner_id, content.prompt, comfort=plan.comfort, rng=rng,
            solo=plan.kind != "warmup",
        )
    lesson = ServedLesson(next(_ids), learner_id, plan, content, now, plan_hints)
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
        "hints": lesson.hints,
    }


# --- finishing -------------------------------------------------------------------------


def _sitting(conn: sqlite3.Connection, learner_id: int, now: datetime) -> int:
    session = db.latest_session(conn, learner_id)
    last = session and (session.ended_at or session.started_at)
    if session and last and now - last <= brain.SITTING_GAP:
        return session.id
    return db.start_session(conn, learner_id).id


def key_bonuses(
    keys: list[str], stats: dict[str, KeyStat], records: dict[str, KeyRecord], bar: float, paid: set[tuple[str, str]],
    practiced: dict[str, int],
) -> list[tuple[int, str, str]]:
    """The milestones `keys` have reached: (coins, reason, key). `records` are practice
    keystrokes only and `practiced` counts each key's practice lessons, so nothing pays
    straight after the teach page. Speed counts only after enough tries really typed:
    placement fills in a guessed speed and sample count."""
    out = []
    for key in keys:
        if key not in skill_model.KEY_ORDER:
            continue  # capitals and the like are the same fingers: only real keys count
        if practiced.get(key, 0) < PRACTICE_LESSONS_FOR_BONUS:
            continue
        record = records.get(key, KeyRecord())
        typed = record.recent_attempts >= skill_model.MIN_SAMPLES_FOR_MASTERY
        reached = {
            KEY_SOLID: record.recent_attempts >= MIN_RECENT_ATTEMPTS and record.recent_accuracy >= bar,
            KEY_HALFWAY: typed and skill_model.reaches_speed(stats.get(key), skill_model.HALFWAY_MS_PER_KEYSTROKE),
            KEY_MASTERED: typed and skill_model.reaches_speed(stats.get(key), skill_model.TARGET_MS_PER_KEYSTROKE),
        }
        out += [(KEY_BONUS, reason, key) for reason, now in reached.items() if now and (reason, key) not in paid]
    return out


def apply_skill_model(
    conn: sqlite3.Connection,
    learner_id: int,
    new_keys: list[str],
    keystrokes: list[KeystrokeEvent],
    now: datetime,
    weights: list[float] | None = None,
) -> None:
    """Fold keystrokes into each key's stats (marking new_keys unlocked) and persist.
    `weights` (one per keystroke, default 1) is how much each counts: hint_model.mastery_weight."""
    touched: dict[str, KeyStat] = {}

    def get_or_new(key: str) -> KeyStat:
        if key in touched:
            return touched[key]
        existing = db.get_key_stat(conn, learner_id, key)
        return existing if existing is not None else skill_model.new_key_stat(learner_id, key)

    for key in new_keys:
        touched[key] = skill_model.mark_unlocked(get_or_new(key), now)
    for ke, w in zip(keystrokes, weights or [1.0] * len(keystrokes)):
        touched[ke.expected_char] = skill_model.record_attempt(
            get_or_new(ke.expected_char), correct=ke.correct, latency_ms=ke.latency_ms, now=now, weight=w
        )

    for stat in touched.values():
        db.upsert_key_stat(conn, stat)


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
    lesson_presses = hints.presses(keystrokes, lesson.hints)
    for seq, (ke, hp) in enumerate(zip(keystrokes, lesson_presses)):
        db.log_keystroke(
            conn, event.id, seq, ke.expected_char, ke.typed_char, ke.correct, ke.latency_ms,
            hint_support=hp.support, hint_seen=hint_model.press_kind(hp.support, hp.latency_ms, hp.solo), solo=hp.solo,
        )
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
        hints.taught(conn, learner_id, new_keys)
    apply_skill_model(conn, learner_id, new_keys, keystrokes, now, [hint_model.mastery_weight(hp) for hp in lesson_presses])
    apply_bigram_model(conn, learner_id, keystrokes)

    earned = [_coins(conn, learner_id, lesson, result, typed_part)]
    if p.kind != "learn":
        keys = sorted({ke.expected_char for ke in keystrokes})
        earned += key_bonuses(
            keys, {s.key: s for s in db.list_key_stats(conn, learner_id)},
            key_records(conn, learner_id, practice_only=True),
            solid_bar(daily.get_settings(conn, learner_id).learn_vs_practice),
            db.coin_rows_paid(conn, learner_id, KEY_BONUS_REASONS),
            db.practice_lesson_counts(conn, learner_id, keys),
        )
        earned += hints.finish(conn, learner_id, f"lesson:{lesson_id}", lesson_presses, lesson.hints)
    coins_earned = []
    for amount, reason, ref in earned:
        if amount > 0:
            db.add_coins(conn, learner_id, amount, reason, ref=ref)
            keyed = reason in KEY_BONUS_REASONS or reason in hints.GRADUATION_REASONS
            coins_earned.append({"amount": amount, "reason": reason} | ({"key": ref} if keyed else {}))

    milestones = daily.add_practice(conn, learner_id, active_seconds, now, learned=p.kind == "learn")
    coins_earned += [{"amount": m["coins"], "reason": f"daily_{m['milestone']}"} for m in milestones if m["coins"]]
    watered = None
    if any(m["milestone"] == "seed" for m in milestones):
        watered = {"ripened": garden.water(conn, learner_id, now)}
    return {
        "result": asdict(result),
        "kind": p.kind,
        "learned": [k for k in new_keys if k in skill_model.KEY_ORDER and k != " "],
        "finished_share": finished_share,
        "active_seconds": active_seconds,
        "coins_earned": coins_earned,
        "tokens_earned": [
            {"amount": m["tokens"], "reason": f"daily_{m['milestone']}"} for m in milestones if m["tokens"]
        ],
        "seeds_earned": [{"amount": m["seeds"], "reason": f"daily_{m['milestone']}"} for m in milestones if m["seeds"]],
        "watered": watered,
        "seed_balance": db.get_seed_balance(conn, learner_id),
        "coin_balance": db.get_coin_balance(conn, learner_id),
        "token_balance": db.get_token_balance(conn, learner_id),
        "day": daily.status(conn, learner_id, now),
    }
