"""SQLite data layer.

Plain stdlib sqlite3 — no ORM. This module owns the schema and all
read/write access; nothing else in the app touches SQL directly. See
PLAN.md Section 4 for the schema rationale (append-only keystroke log,
derived aggregates).

All timestamps are stored as ISO-8601 UTC strings and parsed back to
``datetime`` on read, so the DB file stays human-readable with
``sqlite3`` CLI tools.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from app.models import BigramStat, KeystrokeLog, KeyStat, Learner, Session, SessionEvent, Streak

SCHEMA = """
CREATE TABLE IF NOT EXISTS learner (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS key_stat (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    key TEXT NOT NULL,
    ema_time_ms REAL,
    confidence REAL NOT NULL DEFAULT 0,
    accuracy_rolling REAL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    unlocked_at TEXT,
    mastered_at TEXT,
    PRIMARY KEY (learner_id, key)
);

CREATE TABLE IF NOT EXISTS bigram_stat (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    key1 TEXT NOT NULL,
    key2 TEXT NOT NULL,
    ema_time_ms REAL,
    accuracy_rolling REAL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (learner_id, key1, key2)
);

CREATE TABLE IF NOT EXISTS session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS session_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES session(id),
    phase TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    summary_stats TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS keystroke_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_event_id INTEGER NOT NULL REFERENCES session_event(id),
    seq INTEGER NOT NULL,
    expected_char TEXT NOT NULL,
    typed_char TEXT NOT NULL,
    correct INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_keystroke_log_event ON keystroke_log(session_event_id);

CREATE TABLE IF NOT EXISTS streak (
    learner_id INTEGER PRIMARY KEY REFERENCES learner(id),
    current_streak_days INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    last_active_date TEXT
);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with sane defaults (foreign keys on, Row factory)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def open_db(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a connection, ensure schema exists, commit once on clean exit,
    close on exit.

    Every write function below used to call conn.commit() itself. That's
    fine at one call per request, but a single step-completion request
    writes one row per keystroke (log_keystroke) plus one row per
    consecutive letter pair (upsert_bigram_stat) -- for a 180-keystroke
    step, roughly 360 individual commits, each a synchronous disk fsync.
    That's what turned "submit this step" into a multi-second request
    (confirmed by profiling: ~7s server-side for 180 keystrokes, almost
    entirely commit overhead, not application logic). Batching the
    whole request into one transaction/commit here, and dropping the
    per-call commits, doesn't change what gets persisted -- a request
    that raises skips the commit and rolls back on close() exactly as
    before -- it just stops paying the fsync cost hundreds of times
    per request.
    """
    conn = connect(db_path)
    try:
        init_schema(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- learner ---------------------------------------------------------------


def create_learner(conn: sqlite3.Connection, name: str) -> Learner:
    created_at = _now_iso()
    cur = conn.execute(
        "INSERT INTO learner (name, created_at) VALUES (?, ?)", (name, created_at)
    )
    return Learner(id=cur.lastrowid, name=name, created_at=_parse_dt(created_at))


def get_learner(conn: sqlite3.Connection, learner_id: int) -> Learner | None:
    row = conn.execute("SELECT * FROM learner WHERE id = ?", (learner_id,)).fetchone()
    if row is None:
        return None
    return Learner(id=row["id"], name=row["name"], created_at=_parse_dt(row["created_at"]))


# --- key_stat ----------------------------------------------------------------


def upsert_key_stat(conn: sqlite3.Connection, stat: KeyStat) -> None:
    conn.execute(
        """
        INSERT INTO key_stat
            (learner_id, key, ema_time_ms, confidence, accuracy_rolling,
             sample_count, unlocked_at, mastered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(learner_id, key) DO UPDATE SET
            ema_time_ms = excluded.ema_time_ms,
            confidence = excluded.confidence,
            accuracy_rolling = excluded.accuracy_rolling,
            sample_count = excluded.sample_count,
            unlocked_at = excluded.unlocked_at,
            mastered_at = excluded.mastered_at
        """,
        (
            stat.learner_id,
            stat.key,
            stat.ema_time_ms,
            stat.confidence,
            stat.accuracy_rolling,
            stat.sample_count,
            stat.unlocked_at.isoformat() if stat.unlocked_at else None,
            stat.mastered_at.isoformat() if stat.mastered_at else None,
        ),
    )


def get_key_stat(conn: sqlite3.Connection, learner_id: int, key: str) -> KeyStat | None:
    row = conn.execute(
        "SELECT * FROM key_stat WHERE learner_id = ? AND key = ?", (learner_id, key)
    ).fetchone()
    return _row_to_key_stat(row) if row else None


def list_key_stats(conn: sqlite3.Connection, learner_id: int) -> list[KeyStat]:
    rows = conn.execute(
        "SELECT * FROM key_stat WHERE learner_id = ?", (learner_id,)
    ).fetchall()
    return [_row_to_key_stat(row) for row in rows]


def _row_to_key_stat(row: sqlite3.Row) -> KeyStat:
    return KeyStat(
        learner_id=row["learner_id"],
        key=row["key"],
        ema_time_ms=row["ema_time_ms"],
        confidence=row["confidence"],
        accuracy_rolling=row["accuracy_rolling"],
        sample_count=row["sample_count"],
        unlocked_at=_parse_dt(row["unlocked_at"]),
        mastered_at=_parse_dt(row["mastered_at"]),
    )


# --- bigram_stat ---------------------------------------------------------------


def upsert_bigram_stat(conn: sqlite3.Connection, stat: BigramStat) -> None:
    conn.execute(
        """
        INSERT INTO bigram_stat (learner_id, key1, key2, ema_time_ms, accuracy_rolling, sample_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(learner_id, key1, key2) DO UPDATE SET
            ema_time_ms = excluded.ema_time_ms,
            accuracy_rolling = excluded.accuracy_rolling,
            sample_count = excluded.sample_count
        """,
        (stat.learner_id, stat.key1, stat.key2, stat.ema_time_ms, stat.accuracy_rolling, stat.sample_count),
    )


def get_bigram_stat(conn: sqlite3.Connection, learner_id: int, key1: str, key2: str) -> BigramStat | None:
    row = conn.execute(
        "SELECT * FROM bigram_stat WHERE learner_id = ? AND key1 = ? AND key2 = ?",
        (learner_id, key1, key2),
    ).fetchone()
    return _row_to_bigram_stat(row) if row else None


def list_bigram_stats(conn: sqlite3.Connection, learner_id: int) -> list[BigramStat]:
    rows = conn.execute(
        "SELECT * FROM bigram_stat WHERE learner_id = ?", (learner_id,)
    ).fetchall()
    return [_row_to_bigram_stat(row) for row in rows]


def _row_to_bigram_stat(row: sqlite3.Row) -> BigramStat:
    return BigramStat(
        learner_id=row["learner_id"],
        key1=row["key1"],
        key2=row["key2"],
        ema_time_ms=row["ema_time_ms"],
        accuracy_rolling=row["accuracy_rolling"],
        sample_count=row["sample_count"],
    )


# --- session / session_event / keystroke_log --------------------------------


def start_session(conn: sqlite3.Connection, learner_id: int) -> Session:
    started_at = _now_iso()
    cur = conn.execute(
        "INSERT INTO session (learner_id, started_at) VALUES (?, ?)",
        (learner_id, started_at),
    )
    return Session(
        id=cur.lastrowid, learner_id=learner_id, started_at=_parse_dt(started_at), ended_at=None
    )


def end_session(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute(
        "UPDATE session SET ended_at = ? WHERE id = ?", (_now_iso(), session_id)
    )


def log_session_event(
    conn: sqlite3.Connection,
    session_id: int,
    phase: str,
    activity_id: str,
    summary_stats: dict | None = None,
) -> SessionEvent:
    started_at = _now_iso()
    stats_json = json.dumps(summary_stats or {})
    cur = conn.execute(
        """
        INSERT INTO session_event (session_id, phase, activity_id, started_at, summary_stats)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, phase, activity_id, started_at, stats_json),
    )
    return SessionEvent(
        id=cur.lastrowid,
        session_id=session_id,
        phase=phase,
        activity_id=activity_id,
        started_at=_parse_dt(started_at),
        ended_at=None,
        summary_stats=summary_stats or {},
    )


def end_session_event(
    conn: sqlite3.Connection, event_id: int, summary_stats: dict | None = None
) -> None:
    if summary_stats is not None:
        conn.execute(
            "UPDATE session_event SET ended_at = ?, summary_stats = ? WHERE id = ?",
            (_now_iso(), json.dumps(summary_stats), event_id),
        )
    else:
        conn.execute(
            "UPDATE session_event SET ended_at = ? WHERE id = ?", (_now_iso(), event_id)
        )


def log_keystroke(
    conn: sqlite3.Connection,
    session_event_id: int,
    seq: int,
    expected_char: str,
    typed_char: str,
    correct: bool,
    latency_ms: int,
) -> None:
    conn.execute(
        """
        INSERT INTO keystroke_log
            (session_event_id, seq, expected_char, typed_char, correct, latency_ms, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_event_id, seq, expected_char, typed_char, int(correct), latency_ms, _now_iso()),
    )


def list_keystrokes_for_event(
    conn: sqlite3.Connection, session_event_id: int
) -> list[KeystrokeLog]:
    rows = conn.execute(
        "SELECT * FROM keystroke_log WHERE session_event_id = ? ORDER BY seq",
        (session_event_id,),
    ).fetchall()
    return [
        KeystrokeLog(
            id=row["id"],
            session_event_id=row["session_event_id"],
            seq=row["seq"],
            expected_char=row["expected_char"],
            typed_char=row["typed_char"],
            correct=bool(row["correct"]),
            latency_ms=row["latency_ms"],
            timestamp=_parse_dt(row["timestamp"]),
        )
        for row in rows
    ]


# --- streak -------------------------------------------------------------------


def get_streak(conn: sqlite3.Connection, learner_id: int) -> Streak:
    row = conn.execute(
        "SELECT * FROM streak WHERE learner_id = ?", (learner_id,)
    ).fetchone()
    if row is None:
        return Streak(
            learner_id=learner_id, current_streak_days=0, longest_streak=0, last_active_date=None
        )
    return Streak(
        learner_id=row["learner_id"],
        current_streak_days=row["current_streak_days"],
        longest_streak=row["longest_streak"],
        last_active_date=row["last_active_date"],
    )


def upsert_streak(conn: sqlite3.Connection, streak: Streak) -> None:
    conn.execute(
        """
        INSERT INTO streak (learner_id, current_streak_days, longest_streak, last_active_date)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(learner_id) DO UPDATE SET
            current_streak_days = excluded.current_streak_days,
            longest_streak = excluded.longest_streak,
            last_active_date = excluded.last_active_date
        """,
        (
            streak.learner_id,
            streak.current_streak_days,
            streak.longest_streak,
            streak.last_active_date,
        ),
    )
