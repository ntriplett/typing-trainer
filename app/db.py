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

from app.models import BigramStat, CoinEntry, KeystrokeLog, KeyStat, Learner, Session, SessionEvent, Streak

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

-- Append-only: +earn / -spend rows, balance = SUM(amount) (PLAN.md 11c).
CREATE TABLE IF NOT EXISTS coin_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    ref TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_coin_ledger_learner ON coin_ledger(learner_id);

-- Store items (catalog itself lives in app/store.py, not the DB).
CREATE TABLE IF NOT EXISTS owned_item (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    item_id TEXT NOT NULL,
    purchased_at TEXT NOT NULL,
    PRIMARY KEY (learner_id, item_id)
);

CREATE TABLE IF NOT EXISTS equipped_item (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    slot TEXT NOT NULL,
    item_id TEXT NOT NULL,
    PRIMARY KEY (learner_id, slot)
);

-- Small per-learner preferences (e.g. night mode on/off).
CREATE TABLE IF NOT EXISTS learner_setting (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (learner_id, key)
);

-- Pets are individuals (app/pets.py): a learner can own several of the
-- same species. slot is 1/2 while the pet comes along on the avatar.
CREATE TABLE IF NOT EXISTS owned_pet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    species TEXT NOT NULL,
    color TEXT NOT NULL,
    name TEXT NOT NULL,
    growth INTEGER NOT NULL DEFAULT 0,
    last_fed TEXT,
    slot INTEGER,
    adopted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_owned_pet_learner ON owned_pet(learner_id);

-- Character designer choices (app/appearance.py owns the allowed values).
CREATE TABLE IF NOT EXISTS appearance (
    learner_id INTEGER PRIMARY KEY REFERENCES learner(id),
    gender TEXT NOT NULL,
    skin TEXT NOT NULL,
    hair_color TEXT NOT NULL,
    hair_style TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with sane defaults (foreign keys on, Row factory).

    check_same_thread=False: FastAPI runs a sync generator dependency
    (main.get_db) on threadpool workers, so a request's connect, endpoint
    body, and commit/close can each land on a *different* thread. With
    sqlite3's default thread check that raised ProgrammingError at random
    under concurrent requests -- the root cause of the intermittent blank
    analysis page (its 4 parallel fetches) and of silently failed commits.
    Safe here because each connection belongs to exactly one request and
    is never used by two threads at once.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
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


def rename_learner(conn: sqlite3.Connection, learner_id: int, name: str) -> None:
    conn.execute("UPDATE learner SET name = ? WHERE id = ?", (name, learner_id))


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


# --- coins --------------------------------------------------------------------


def add_coins(
    conn: sqlite3.Connection, learner_id: int, amount: int, reason: str, ref: str | None = None
) -> CoinEntry:
    """Append one ledger row. Positive earns, negative spends."""
    created_at = _now_iso()
    cur = conn.execute(
        "INSERT INTO coin_ledger (learner_id, amount, reason, ref, created_at) VALUES (?, ?, ?, ?, ?)",
        (learner_id, amount, reason, ref, created_at),
    )
    return CoinEntry(
        id=cur.lastrowid,
        learner_id=learner_id,
        amount=amount,
        reason=reason,
        ref=ref,
        created_at=_parse_dt(created_at),
    )


def get_coin_balance(conn: sqlite3.Connection, learner_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS balance FROM coin_ledger WHERE learner_id = ?",
        (learner_id,),
    ).fetchone()
    return row["balance"]


def list_coin_history(
    conn: sqlite3.Connection, learner_id: int, limit: int = 50
) -> list[CoinEntry]:
    """Newest first. Ordered by id, not created_at, so rows written in
    the same instant keep their insertion order."""
    rows = conn.execute(
        "SELECT * FROM coin_ledger WHERE learner_id = ? ORDER BY id DESC LIMIT ?",
        (learner_id, limit),
    ).fetchall()
    return [
        CoinEntry(
            id=row["id"],
            learner_id=row["learner_id"],
            amount=row["amount"],
            reason=row["reason"],
            ref=row["ref"],
            created_at=_parse_dt(row["created_at"]),
        )
        for row in rows
    ]


# --- store items --------------------------------------------------------------
#
# Thin storage only; the rules (prices, starters, "must own to equip")
# live in app/store.py.


def add_owned_item(conn: sqlite3.Connection, learner_id: int, item_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO owned_item (learner_id, item_id, purchased_at) VALUES (?, ?, ?)",
        (learner_id, item_id, _now_iso()),
    )


def remove_owned_item(conn: sqlite3.Connection, learner_id: int, item_id: str) -> None:
    conn.execute("DELETE FROM owned_item WHERE learner_id = ? AND item_id = ?", (learner_id, item_id))


def list_owned_item_ids(conn: sqlite3.Connection, learner_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT item_id FROM owned_item WHERE learner_id = ?", (learner_id,)
    ).fetchall()
    return {row["item_id"] for row in rows}


def set_equipped(conn: sqlite3.Connection, learner_id: int, slot: str, item_id: str) -> None:
    conn.execute(
        """
        INSERT INTO equipped_item (learner_id, slot, item_id) VALUES (?, ?, ?)
        ON CONFLICT(learner_id, slot) DO UPDATE SET item_id = excluded.item_id
        """,
        (learner_id, slot, item_id),
    )


def clear_equipped(conn: sqlite3.Connection, learner_id: int, slot: str) -> None:
    conn.execute(
        "DELETE FROM equipped_item WHERE learner_id = ? AND slot = ?", (learner_id, slot)
    )


def get_equipped(conn: sqlite3.Connection, learner_id: int) -> dict[str, str]:
    """slot -> item_id for everything this learner has equipped."""
    rows = conn.execute(
        "SELECT slot, item_id FROM equipped_item WHERE learner_id = ?", (learner_id,)
    ).fetchall()
    return {row["slot"]: row["item_id"] for row in rows}


# --- appearance ---------------------------------------------------------------


def get_appearance(conn: sqlite3.Connection, learner_id: int) -> dict | None:
    row = conn.execute(
        "SELECT gender, skin, hair_color, hair_style FROM appearance WHERE learner_id = ?",
        (learner_id,),
    ).fetchone()
    return dict(row) if row else None


def set_appearance(
    conn: sqlite3.Connection, learner_id: int, *, gender: str, skin: str, hair_color: str, hair_style: str
) -> None:
    conn.execute(
        """
        INSERT INTO appearance (learner_id, gender, skin, hair_color, hair_style) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(learner_id) DO UPDATE SET
            gender = excluded.gender, skin = excluded.skin,
            hair_color = excluded.hair_color, hair_style = excluded.hair_style
        """,
        (learner_id, gender, skin, hair_color, hair_style),
    )


# --- profile stats ----------------------------------------------------------------


def profile_stats(conn: sqlite3.Connection, learner_id: int) -> dict:
    """Headline numbers for the profile page."""
    one = lambda sql: conn.execute(sql, (learner_id,)).fetchone()[0]  # noqa: E731
    return {
        "coins_earned_total": one(
            "SELECT COALESCE(SUM(amount), 0) FROM coin_ledger WHERE learner_id = ? AND amount > 0"
        ),
        "sessions_completed": one(
            "SELECT COUNT(*) FROM session WHERE learner_id = ? AND ended_at IS NOT NULL"
        ),
        "keys_mastered": one(
            "SELECT COUNT(*) FROM key_stat WHERE learner_id = ? AND mastered_at IS NOT NULL"
        ),
        "items_owned": one("SELECT COUNT(*) FROM owned_item WHERE learner_id = ?"),
    }


# --- settings -------------------------------------------------------------------


def get_setting(conn: sqlite3.Connection, learner_id: int, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM learner_setting WHERE learner_id = ? AND key = ?", (learner_id, key)
    ).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, learner_id: int, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO learner_setting (learner_id, key, value) VALUES (?, ?, ?)
        ON CONFLICT(learner_id, key) DO UPDATE SET value = excluded.value
        """,
        (learner_id, key, value),
    )


# --- pets -------------------------------------------------------------------------

_PET_COLUMNS = "id, species, color, name, growth, last_fed, slot, adopted_at"


def add_pet(
    conn: sqlite3.Connection, learner_id: int, species: str, color: str, name: str,
    growth: int = 0, slot: int | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO owned_pet (learner_id, species, color, name, growth, slot, adopted_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (learner_id, species, color, name, growth, slot, _now_iso()),
    )
    return cur.lastrowid


def list_pets(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    rows = conn.execute(
        f"SELECT {_PET_COLUMNS} FROM owned_pet WHERE learner_id = ? ORDER BY id", (learner_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_pet(conn: sqlite3.Connection, learner_id: int, pet_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT {_PET_COLUMNS} FROM owned_pet WHERE learner_id = ? AND id = ?", (learner_id, pet_id)
    ).fetchone()
    return dict(row) if row else None


_PET_UPDATABLE = {"name", "growth", "last_fed", "slot"}


def update_pet(conn: sqlite3.Connection, learner_id: int, pet_id: int, **fields) -> None:
    unknown = set(fields) - _PET_UPDATABLE
    if unknown:
        raise ValueError(f"can't update pet fields {unknown}")
    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE owned_pet SET {assignments} WHERE learner_id = ? AND id = ?",
        (*fields.values(), learner_id, pet_id),
    )
