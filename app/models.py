"""Typed row shapes for the SQLite tables defined in app/db.py.

These are plain dataclasses, not an ORM — they exist so the rest of the
app (skill model, scheduler, API) talks to structured objects instead of
raw sqlite3.Row / dict soup. See PLAN.md Section 4 for the schema design.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Learner:
    id: int
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class KeyStat:
    learner_id: int
    key: str
    ema_time_ms: float | None
    confidence: float
    accuracy_rolling: float | None
    sample_count: int
    unlocked_at: datetime | None
    mastered_at: datetime | None


@dataclass(frozen=True, slots=True)
class BigramStat:
    """Detail-level stat for a 2-key transition (e.g. typing 'e' then 'i').

    Unlike KeyStat, this doesn't gate anything (no unlocked_at/mastered_at)
    -- it's purely descriptive, for the analysis page and as a secondary
    signal for the recommender. Updated in a batch at the end of each
    activity step, not per keystroke (see app/bigram_model.py).
    """

    learner_id: int
    key1: str
    key2: str
    ema_time_ms: float | None
    accuracy_rolling: float | None
    sample_count: int


@dataclass(frozen=True, slots=True)
class Session:
    id: int
    learner_id: int
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True, slots=True)
class SessionEvent:
    id: int
    session_id: int
    phase: str  # "warmup" | "teach" | "practice" | "eval" | "game"
    activity_id: str
    started_at: datetime
    ended_at: datetime | None
    summary_stats: dict


@dataclass(frozen=True, slots=True)
class KeystrokeLog:
    id: int
    session_event_id: int
    seq: int
    expected_char: str
    typed_char: str
    correct: bool
    latency_ms: int
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class Streak:
    learner_id: int
    current_streak_days: int
    longest_streak: int
    last_active_date: str | None  # ISO date (YYYY-MM-DD)


@dataclass(frozen=True, slots=True)
class CoinEntry:
    """One row of the coin ledger: +amount earned or -amount spent.
    The balance is never stored -- it's the SUM over these rows.
    """

    id: int
    learner_id: int
    amount: int
    reason: str  # e.g. "lesson", "mastered_key", "purchase"
    ref: str | None  # what it was for: a session event, a key, an item id
    created_at: datetime
