"""The daily practice goal and arcade tokens.

Practice time adds up in a "chunk", roughly one per day, at whatever pace
the learner likes (a few lessons, then the store, then a few more):
  - reaching the goal (a parent setting, 10 minutes by default) pays
    GOAL_TOKENS arcade tokens (and a coin bonus),
  - another half of the goal on top (1.5x) pays BONUS_TOKENS more, and
    practice rests until REST after that,
  - a chunk that reached its goal but not the bonus ends REST after the
    goal (the bonus is forfeit), and one that never reached the goal
    resets UNFINISHED_RESET after its first lesson ("reset overnight").

Per-learner settings (goal minutes, the learn-vs-practice slider) live in
learner_setting and are edited on the parent page.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from app import db

DEFAULT_GOAL_MINUTES = 10
MIN_GOAL_MINUTES = 2
MAX_GOAL_MINUTES = 60
DEFAULT_LEARN_VS_PRACTICE = 0.5

BONUS_SHARE = 1.5
GOAL_TOKENS = 2
BONUS_TOKENS = 1
GOAL_COINS = 100
REST = timedelta(hours=12)
UNFINISHED_RESET = timedelta(hours=18)
# A milestone counts within this many seconds of the line, so a lesson
# that ends 3 seconds short doesn't need a whole extra lesson.
GRACE_SECONDS = 10

SETTING_GOAL = "daily_goal_minutes"
SETTING_LEARN = "learn_vs_practice"


class PracticeResting(Exception):
    """Today's practice (with the bonus) is done; it opens again later."""


@dataclass(frozen=True, slots=True)
class Settings:
    goal_minutes: int = DEFAULT_GOAL_MINUTES
    learn_vs_practice: float = DEFAULT_LEARN_VS_PRACTICE

    @property
    def goal_seconds(self) -> int:
        return self.goal_minutes * 60


def get_settings(conn: sqlite3.Connection, learner_id: int) -> Settings:
    goal = db.get_setting(conn, learner_id, SETTING_GOAL)
    learn = db.get_setting(conn, learner_id, SETTING_LEARN)
    return Settings(
        goal_minutes=int(goal) if goal else DEFAULT_GOAL_MINUTES,
        learn_vs_practice=float(learn) if learn else DEFAULT_LEARN_VS_PRACTICE,
    )


def save_settings(conn: sqlite3.Connection, learner_id: int, settings: Settings) -> None:
    goal = max(MIN_GOAL_MINUTES, min(MAX_GOAL_MINUTES, settings.goal_minutes))
    learn = max(0.0, min(1.0, settings.learn_vs_practice))
    db.set_setting(conn, learner_id, SETTING_GOAL, str(goal))
    db.set_setting(conn, learner_id, SETTING_LEARN, str(learn))


def chunk_ends_at(chunk: dict) -> datetime:
    if chunk["full_at"]:
        return chunk["full_at"] + REST
    if chunk["goal_at"]:
        return chunk["goal_at"] + REST
    return chunk["started_at"] + UNFINISHED_RESET


def current_chunk(conn: sqlite3.Connection, learner_id: int, now: datetime) -> dict | None:
    """The chunk practice adds to right now, or None if the next lesson
    starts a fresh one."""
    chunk = db.latest_chunk(conn, learner_id)
    if chunk is None or now >= chunk_ends_at(chunk):
        return None
    return chunk


def status(conn: sqlite3.Connection, learner_id: int, now: datetime) -> dict:
    """Everything the day tracker shows."""
    settings = get_settings(conn, learner_id)
    chunk = current_chunk(conn, learner_id, now)
    goal = settings.goal_seconds
    practiced = chunk["practiced_seconds"] if chunk else 0.0
    resting = bool(chunk and chunk["full_at"])
    return {
        "goal_seconds": goal,
        "bonus_seconds": round(goal * BONUS_SHARE),
        "practiced_seconds": round(practiced),
        "goal_reached": bool(chunk and chunk["goal_at"]),
        "bonus_reached": resting,
        "resting_until": chunk_ends_at(chunk).isoformat() if resting else None,
        "goal_tokens": GOAL_TOKENS,
        "bonus_tokens": BONUS_TOKENS,
        "learns": chunk["learns"] if chunk else 0,
    }


def check_open(conn: sqlite3.Connection, learner_id: int, now: datetime) -> None:
    chunk = current_chunk(conn, learner_id, now)
    if chunk and chunk["full_at"]:
        raise PracticeResting(chunk_ends_at(chunk).isoformat())


def add_practice(
    conn: sqlite3.Connection, learner_id: int, seconds: float, now: datetime, learned: bool = False
) -> list[dict]:
    """Count one finished lesson toward today's chunk and pay any milestone
    it crossed. Returns the milestones reached: [{"milestone", "tokens", "coins"}].

    A lesson served before the chunk filled up still counts its time
    (capped at the bonus line); it just can't pay a milestone twice.
    """
    settings = get_settings(conn, learner_id)
    chunk = current_chunk(conn, learner_id, now)
    if chunk is None:
        db.create_chunk(conn, learner_id, now)
        chunk = db.latest_chunk(conn, learner_id)
    chunk_id = chunk["id"]

    goal = settings.goal_seconds
    bonus = goal * BONUS_SHARE
    practiced = min(bonus, chunk["practiced_seconds"] + max(0.0, seconds))
    goal_at, full_at = chunk["goal_at"], chunk["full_at"]
    reached = []
    if goal_at is None and practiced >= goal - GRACE_SECONDS:
        goal_at = now
        reached.append({"milestone": "goal", "tokens": GOAL_TOKENS, "coins": GOAL_COINS})
    if full_at is None and practiced >= bonus - GRACE_SECONDS:
        full_at = now
        practiced = bonus
        reached.append({"milestone": "bonus", "tokens": BONUS_TOKENS, "coins": 0})
    db.update_chunk(conn, chunk_id, practiced, chunk["learns"] + int(learned), goal_at, full_at)

    for m in reached:
        ref = f"chunk:{chunk_id}"
        reason = f"daily_{m['milestone']}"
        if not db.has_token_entry(conn, learner_id, reason, ref):
            db.add_tokens(conn, learner_id, m["tokens"], reason, ref=ref)
            if m["coins"]:
                db.add_coins(conn, learner_id, m["coins"], reason, ref=ref)
    return reached
