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


-- Pets v3 (PLAN.md 11h): genes are app/pet_genes.py's JSON, stored rather
-- than re-rolled. home is NULL while the pet waits in the Pet Care Center.
CREATE TABLE IF NOT EXISTS pet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    seed INTEGER NOT NULL,
    species TEXT NOT NULL,
    genes TEXT NOT NULL,
    name TEXT NOT NULL,
    growth INTEGER NOT NULL DEFAULT 0,
    last_fed TEXT,
    source TEXT NOT NULL,
    home TEXT,
    adopted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pet_learner ON pet(learner_id);

-- Pet Supplies (PLAN.md 11l): how many of each treat, toy, fish food.
CREATE TABLE IF NOT EXISTS pet_supply (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    item_id TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (learner_id, item_id)
);

-- Color potions bought (slot: which of that day's stock); used_on once used.
CREATE TABLE IF NOT EXISTS potion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    colors TEXT NOT NULL,
    tier TEXT NOT NULL,
    slot INTEGER NOT NULL,
    bought_on TEXT NOT NULL,
    used_on TEXT
);

-- Aquarium tanks (PLAN.md 11k): spot 0..9 in the Aquarium hall; the
-- background and substrate are item ids from app/aquarium.py.
CREATE TABLE IF NOT EXISTS tank (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    spot INTEGER NOT NULL,
    name TEXT NOT NULL,
    background TEXT NOT NULL,
    substrate TEXT NOT NULL,
    bought_at TEXT NOT NULL,
    PRIMARY KEY (learner_id, spot)
);

-- Plants, rocks and decorations: one row per copy bought. tank is NULL
-- while the piece waits in storage; x is its left edge, y its bottom.
CREATE TABLE IF NOT EXISTS tank_piece (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    item_id TEXT NOT NULL,
    tank INTEGER,
    x REAL NOT NULL DEFAULT 0,
    y REAL NOT NULL DEFAULT 0,
    layer TEXT NOT NULL,
    flip INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tank_piece_learner ON tank_piece(learner_id);

-- Backgrounds and substrates: bought once, used in any tank.
CREATE TABLE IF NOT EXISTS aqua_owned (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    item_id TEXT NOT NULL,
    PRIMARY KEY (learner_id, item_id)
);

-- Habitats on the Trailhead (PLAN.md 11i): spot 0..9 along the trail.
CREATE TABLE IF NOT EXISTS habitat (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    spot INTEGER NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    bought_at TEXT NOT NULL,
    PRIMARY KEY (learner_id, spot)
);

-- Pet colors a learner has unlocked (for every species they suit).
CREATE TABLE IF NOT EXISTS pet_color_unlock (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    color TEXT NOT NULL,
    unlocked_at TEXT NOT NULL,
    PRIMARY KEY (learner_id, color)
);

-- The Pet Shop's stock, one row per learner, department and slot
-- (app/pet_shop.py Slot). Dates are local calendar days.
CREATE TABLE IF NOT EXISTS shop_slot (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    dept TEXT NOT NULL,
    idx INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    species TEXT NOT NULL,
    genes TEXT NOT NULL,
    price_roll REAL NOT NULL,
    stocked_on TEXT NOT NULL,
    leaves_on TEXT NOT NULL,
    saved INTEGER NOT NULL DEFAULT 0,
    sold INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (learner_id, dept, idx)
);

-- A learner's one special order (app/pet_shop.py): its pets are shop_slot
-- rows in the "orders" department, arriving on ready_on.
CREATE TABLE IF NOT EXISTS special_order (
    learner_id INTEGER PRIMARY KEY REFERENCES learner(id),
    species TEXT NOT NULL,
    primary_color TEXT NOT NULL,
    secondary_color TEXT,
    fee INTEGER NOT NULL,
    ordered_on TEXT NOT NULL,
    ready_on TEXT NOT NULL,
    leaves_on TEXT NOT NULL
);

-- Decoratable rooms (app/room.py): surfaces (wallpaper, flooring) and
-- placed furniture, keyed by room name.
CREATE TABLE IF NOT EXISTS room_surface (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    room TEXT NOT NULL,
    kind TEXT NOT NULL,
    item_id TEXT NOT NULL,
    PRIMARY KEY (learner_id, room, kind)
);

CREATE TABLE IF NOT EXISTS room_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    room TEXT NOT NULL,
    item_id TEXT NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_room_item_learner ON room_item(learner_id, room);

-- Arcade tokens: the second currency, same append-only shape as
-- coin_ledger. Earned by the daily practice goal (app/daily.py), spent in
-- the arcade (app/arcade.py).
CREATE TABLE IF NOT EXISTS token_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    ref TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_token_ledger_learner ON token_ledger(learner_id);

-- Curriculum lessons already taught (app/lessons.py). ref is
-- "module:keys"; source is lesson (taught for real), placement (the
-- learner said they knew it), or legacy (keys unlocked before lessons
-- were tracked).
CREATE TABLE IF NOT EXISTS taught_lesson (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    ref TEXT NOT NULL,
    source TEXT NOT NULL,
    taught_at TEXT NOT NULL,
    PRIMARY KEY (learner_id, ref)
);

-- One day's chunk of practice (app/daily.py): time adds up toward the
-- goal; goal_at/full_at mark when the goal and the 1.5x bonus landed.
CREATE TABLE IF NOT EXISTS practice_chunk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    started_at TEXT NOT NULL,
    practiced_seconds REAL NOT NULL DEFAULT 0,
    learns INTEGER NOT NULL DEFAULT 0,
    goal_at TEXT,
    full_at TEXT,
    seed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_practice_chunk_learner ON practice_chunk(learner_id);

-- Seeds: the third currency (same shape as token_ledger). Earned at half
-- the daily goal, spent by planting in the garden (app/garden.py).
CREATE TABLE IF NOT EXISTS seed_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    ref TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seed_ledger_learner ON seed_ledger(learner_id);

-- Picked veggies (pet food), one ledger per kind of veggie.
CREATE TABLE IF NOT EXISTS veggie_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    kind TEXT NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_veggie_ledger_learner ON veggie_ledger(learner_id);

-- One planted seed per garden spot (app/garden.py): ripe counts how many
-- of its veggies have ripened, picked how many of those were taken.
CREATE TABLE IF NOT EXISTS garden_plot (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    slot INTEGER NOT NULL,
    kind TEXT NOT NULL,
    planted_at TEXT NOT NULL,
    watered_at TEXT NOT NULL,
    ripe INTEGER NOT NULL DEFAULT 0,
    picked INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (learner_id, slot)
);

-- Ripe veggies saved from withered plants, waiting to be collected.
CREATE TABLE IF NOT EXISTS garden_basket (
    learner_id INTEGER NOT NULL REFERENCES learner(id),
    kind TEXT NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (learner_id, kind)
);

-- Character designer choices (app/appearance.py owns the allowed values).
CREATE TABLE IF NOT EXISTS appearance (
    learner_id INTEGER PRIMARY KEY REFERENCES learner(id),
    gender TEXT NOT NULL,
    skin TEXT NOT NULL,
    hair_color TEXT NOT NULL,
    hair_style TEXT NOT NULL,
    eye_color TEXT NOT NULL DEFAULT 'brown'
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


# Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS
# won't touch an existing table, so older DBs get them via ALTER TABLE.
_ADDED_COLUMNS = [
    ("appearance", "eye_color", "TEXT NOT NULL DEFAULT 'brown'"),
    ("practice_chunk", "seed_at", "TEXT"),
    ("pet", "along", "INTEGER"),
    ("pet", "school", "INTEGER"),  # a fish copied into a school: the first fish's id
    ("tank_piece", "rot", "INTEGER NOT NULL DEFAULT 0"),  # degrees: 0, 90, 180, 270
    ("pet", "joy", "INTEGER NOT NULL DEFAULT 0"),  # hearts (app/pet_supplies.py)
    ("pet", "joy_on", "TEXT"),  # the day they were last set
]


# Tables from retired features, dropped on start (the pets before v3).
_DROPPED_TABLES = ("owned_pet",)


def init_schema(conn: sqlite3.Connection) -> None:
    for table in _DROPPED_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.executescript(SCHEMA)
    for table, column, decl in _ADDED_COLUMNS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
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


def has_coin_entry(conn: sqlite3.Connection, learner_id: int, reason: str, ref: str) -> bool:
    """Whether this learner was ever paid for `reason` + `ref` (one-time rewards)."""
    row = conn.execute(
        "SELECT 1 FROM coin_ledger WHERE learner_id = ? AND reason = ? AND ref = ?",
        (learner_id, reason, ref),
    ).fetchone()
    return row is not None


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


# --- tokens ---------------------------------------------------------------------


def add_tokens(conn: sqlite3.Connection, learner_id: int, amount: int, reason: str, ref: str | None = None) -> None:
    """Append one token ledger row. Positive earns, negative spends."""
    conn.execute(
        "INSERT INTO token_ledger (learner_id, amount, reason, ref, created_at) VALUES (?, ?, ?, ?, ?)",
        (learner_id, amount, reason, ref, _now_iso()),
    )


def has_token_entry(conn: sqlite3.Connection, learner_id: int, reason: str, ref: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM token_ledger WHERE learner_id = ? AND reason = ? AND ref = ?", (learner_id, reason, ref)
    ).fetchone()
    return row is not None


def get_token_balance(conn: sqlite3.Connection, learner_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS balance FROM token_ledger WHERE learner_id = ?", (learner_id,)
    ).fetchone()
    return row["balance"]


# --- seeds, veggies + the garden ------------------------------------------------


def add_seeds(conn: sqlite3.Connection, learner_id: int, amount: int, reason: str, ref: str | None = None) -> None:
    """Append one seed ledger row. Positive earns, negative plants."""
    conn.execute(
        "INSERT INTO seed_ledger (learner_id, amount, reason, ref, created_at) VALUES (?, ?, ?, ?, ?)",
        (learner_id, amount, reason, ref, _now_iso()),
    )


def has_seed_entry(conn: sqlite3.Connection, learner_id: int, reason: str, ref: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM seed_ledger WHERE learner_id = ? AND reason = ? AND ref = ?", (learner_id, reason, ref)
    ).fetchone()
    return row is not None


def get_seed_balance(conn: sqlite3.Connection, learner_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS balance FROM seed_ledger WHERE learner_id = ?", (learner_id,)
    ).fetchone()
    return row["balance"]


def add_veggies(conn: sqlite3.Connection, learner_id: int, kind: str, amount: int, reason: str) -> None:
    conn.execute(
        "INSERT INTO veggie_ledger (learner_id, kind, amount, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (learner_id, kind, amount, reason, _now_iso()),
    )


def get_veggies(conn: sqlite3.Connection, learner_id: int) -> dict[str, int]:
    """kind -> count, kinds with none left out."""
    rows = conn.execute(
        "SELECT kind, SUM(amount) AS n FROM veggie_ledger WHERE learner_id = ? GROUP BY kind HAVING n > 0",
        (learner_id,),
    )
    return {r["kind"]: r["n"] for r in rows}


def list_plots(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM garden_plot WHERE learner_id = ? ORDER BY slot", (learner_id,))
    return [
        {**dict(r), "planted_at": _parse_dt(r["planted_at"]), "watered_at": _parse_dt(r["watered_at"])}
        for r in rows
    ]


def plant_plot(conn: sqlite3.Connection, learner_id: int, slot: int, kind: str, when: datetime) -> None:
    conn.execute(
        "INSERT INTO garden_plot (learner_id, slot, kind, planted_at, watered_at) VALUES (?, ?, ?, ?, ?)",
        (learner_id, slot, kind, when.isoformat(), when.isoformat()),
    )


def update_plot(
    conn: sqlite3.Connection, learner_id: int, slot: int, ripe: int, picked: int, watered_at: datetime
) -> None:
    conn.execute(
        "UPDATE garden_plot SET ripe = ?, picked = ?, watered_at = ? WHERE learner_id = ? AND slot = ?",
        (ripe, picked, watered_at.isoformat(), learner_id, slot),
    )


def clear_plot(conn: sqlite3.Connection, learner_id: int, slot: int) -> None:
    conn.execute("DELETE FROM garden_plot WHERE learner_id = ? AND slot = ?", (learner_id, slot))


def add_to_basket(conn: sqlite3.Connection, learner_id: int, kind: str, count: int) -> None:
    conn.execute(
        """
        INSERT INTO garden_basket (learner_id, kind, count) VALUES (?, ?, ?)
        ON CONFLICT (learner_id, kind) DO UPDATE SET count = count + excluded.count
        """,
        (learner_id, kind, count),
    )


def get_basket(conn: sqlite3.Connection, learner_id: int) -> dict[str, int]:
    rows = conn.execute("SELECT kind, count FROM garden_basket WHERE learner_id = ? AND count > 0", (learner_id,))
    return {r["kind"]: r["count"] for r in rows}


def empty_basket(conn: sqlite3.Connection, learner_id: int) -> None:
    conn.execute("DELETE FROM garden_basket WHERE learner_id = ?", (learner_id,))


# --- taught lessons + practice chunks ------------------------------------------------


def mark_taught(conn: sqlite3.Connection, learner_id: int, ref: str, source: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO taught_lesson (learner_id, ref, source, taught_at) VALUES (?, ?, ?, ?)",
        (learner_id, ref, source, _now_iso()),
    )


def list_taught(conn: sqlite3.Connection, learner_id: int) -> dict[str, str]:
    """ref -> source."""
    rows = conn.execute("SELECT ref, source FROM taught_lesson WHERE learner_id = ?", (learner_id,))
    return {r["ref"]: r["source"] for r in rows}


def latest_chunk(conn: sqlite3.Connection, learner_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM practice_chunk WHERE learner_id = ? ORDER BY id DESC LIMIT 1", (learner_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        **dict(row),
        "started_at": _parse_dt(row["started_at"]),
        "goal_at": _parse_dt(row["goal_at"]),
        "full_at": _parse_dt(row["full_at"]),
        "seed_at": _parse_dt(row["seed_at"]),
    }


def create_chunk(conn: sqlite3.Connection, learner_id: int, started_at: datetime) -> int:
    cur = conn.execute(
        "INSERT INTO practice_chunk (learner_id, started_at) VALUES (?, ?)", (learner_id, started_at.isoformat())
    )
    return cur.lastrowid


def update_chunk(
    conn: sqlite3.Connection,
    chunk_id: int,
    practiced_seconds: float,
    learns: int,
    goal_at: datetime | None,
    full_at: datetime | None,
    seed_at: datetime | None = None,
) -> None:
    conn.execute(
        "UPDATE practice_chunk SET practiced_seconds = ?, learns = ?, goal_at = ?, full_at = ?, seed_at = ? WHERE id = ?",
        (
            practiced_seconds,
            learns,
            goal_at.isoformat() if goal_at else None,
            full_at.isoformat() if full_at else None,
            seed_at.isoformat() if seed_at else None,
            chunk_id,
        ),
    )


# --- lesson history (the brain's input) -------------------------------------------------


def recent_lesson_events(conn: sqlite3.Connection, learner_id: int, limit: int = 40) -> list[dict]:
    """The newest finished lesson rows, oldest first: phase, activity_id,
    ended_at, and the parsed summary_stats."""
    rows = conn.execute(
        """
        SELECT se.phase, se.activity_id, se.ended_at, se.summary_stats
        FROM session_event se JOIN session s ON se.session_id = s.id
        WHERE s.learner_id = ? AND se.ended_at IS NOT NULL
        ORDER BY se.id DESC LIMIT ?
        """,
        (learner_id, limit),
    ).fetchall()
    return [
        {
            "phase": r["phase"],
            "activity_id": r["activity_id"],
            "ended_at": _parse_dt(r["ended_at"]),
            "stats": json.loads(r["summary_stats"] or "{}"),
        }
        for r in reversed(rows)
    ]


def recent_keystrokes(conn: sqlite3.Connection, learner_id: int, limit: int = 8000) -> list[tuple[str, bool]]:
    """(expected_char, correct) for the learner's newest keystrokes, newest first."""
    rows = conn.execute(
        """
        SELECT k.expected_char, k.correct
        FROM keystroke_log k
        JOIN session_event se ON k.session_event_id = se.id
        JOIN session s ON se.session_id = s.id
        WHERE s.learner_id = ?
        ORDER BY k.id DESC LIMIT ?
        """,
        (learner_id, limit),
    ).fetchall()
    return [(r["expected_char"], bool(r["correct"])) for r in rows]


def latest_session(conn: sqlite3.Connection, learner_id: int) -> Session | None:
    row = conn.execute(
        "SELECT * FROM session WHERE learner_id = ? ORDER BY id DESC LIMIT 1", (learner_id,)
    ).fetchone()
    if row is None:
        return None
    return Session(row["id"], row["learner_id"], _parse_dt(row["started_at"]), _parse_dt(row["ended_at"]))


def touch_session(conn: sqlite3.Connection, session_id: int, when: datetime) -> None:
    """A sitting's ended_at moves forward with every finished lesson."""
    conn.execute("UPDATE session SET ended_at = ? WHERE id = ?", (when.isoformat(), session_id))


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
        "SELECT gender, skin, hair_color, hair_style, eye_color FROM appearance WHERE learner_id = ?",
        (learner_id,),
    ).fetchone()
    return dict(row) if row else None


def set_appearance(
    conn: sqlite3.Connection, learner_id: int, *, gender: str, skin: str, hair_color: str, hair_style: str,
    eye_color: str = "brown",
) -> None:
    conn.execute(
        """
        INSERT INTO appearance (learner_id, gender, skin, hair_color, hair_style, eye_color)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(learner_id) DO UPDATE SET
            gender = excluded.gender, skin = excluded.skin, hair_color = excluded.hair_color,
            hair_style = excluded.hair_style, eye_color = excluded.eye_color
        """,
        (learner_id, gender, skin, hair_color, hair_style, eye_color),
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


# --- rooms --------------------------------------------------------------------------


def get_room_surfaces(conn: sqlite3.Connection, learner_id: int, room: str) -> dict[str, str]:
    rows = conn.execute(
        "SELECT kind, item_id FROM room_surface WHERE learner_id = ? AND room = ?", (learner_id, room)
    ).fetchall()
    return {r["kind"]: r["item_id"] for r in rows}


def set_room_surface(conn: sqlite3.Connection, learner_id: int, room: str, kind: str, item_id: str) -> None:
    conn.execute(
        """
        INSERT INTO room_surface (learner_id, room, kind, item_id) VALUES (?, ?, ?, ?)
        ON CONFLICT(learner_id, room, kind) DO UPDATE SET item_id = excluded.item_id
        """,
        (learner_id, room, kind, item_id),
    )


def list_room_items(conn: sqlite3.Connection, learner_id: int, room: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, item_id, x, y FROM room_item WHERE learner_id = ? AND room = ? ORDER BY id",
        (learner_id, room),
    ).fetchall()
    return [dict(r) for r in rows]


def add_room_item(conn: sqlite3.Connection, learner_id: int, room: str, item_id: str, x: int, y: int) -> int:
    cur = conn.execute(
        "INSERT INTO room_item (learner_id, room, item_id, x, y) VALUES (?, ?, ?, ?, ?)",
        (learner_id, room, item_id, x, y),
    )
    return cur.lastrowid


def move_room_item(conn: sqlite3.Connection, learner_id: int, placed_id: int, x: int, y: int) -> bool:
    cur = conn.execute(
        "UPDATE room_item SET x = ?, y = ? WHERE learner_id = ? AND id = ?", (x, y, learner_id, placed_id)
    )
    return cur.rowcount == 1


def remove_room_item(conn: sqlite3.Connection, learner_id: int, placed_id: int) -> bool:
    cur = conn.execute("DELETE FROM room_item WHERE learner_id = ? AND id = ?", (learner_id, placed_id))
    return cur.rowcount == 1


# --- pets v3 and the pet shop (PLAN.md 11h) ---------------------------------------

_V3_PET_COLUMNS = "id, seed, species, genes, name, growth, last_fed, source, home, along, school, joy, joy_on, adopted_at"


def _v3_pet(row: sqlite3.Row) -> dict:
    return {**dict(row), "genes": json.loads(row["genes"])}


def add_v3_pet(
    conn: sqlite3.Connection, learner_id: int, genes: dict, name: str, source: str, school: int | None = None, growth: int = 0
) -> int:
    cur = conn.execute(
        "INSERT INTO pet (learner_id, seed, species, genes, name, source, school, growth, adopted_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (learner_id, genes["seed"], genes["species"], json.dumps(genes), name, source, school, growth, _now_iso()),
    )
    return cur.lastrowid


def list_v3_pets(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    rows = conn.execute(f"SELECT {_V3_PET_COLUMNS} FROM pet WHERE learner_id = ? ORDER BY id", (learner_id,))
    return [_v3_pet(r) for r in rows]


def get_v3_pet(conn: sqlite3.Connection, learner_id: int, pet_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT {_V3_PET_COLUMNS} FROM pet WHERE learner_id = ? AND id = ?", (learner_id, pet_id)
    ).fetchone()
    return _v3_pet(row) if row else None


_V3_PET_UPDATABLE = {"name", "growth", "last_fed", "home", "along", "joy", "joy_on"}


def update_v3_pet(conn: sqlite3.Connection, learner_id: int, pet_id: int, **fields) -> None:
    bad = set(fields) - _V3_PET_UPDATABLE
    if bad:
        raise ValueError(f"can't update {bad}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE pet SET {sets} WHERE learner_id = ? AND id = ?", (*fields.values(), learner_id, pet_id))


def update_v3_pet_genes(conn: sqlite3.Connection, learner_id: int, pet_id: int, genes_json: str) -> None:
    """A potion repaints a pet: its genes change (nothing else ever does that)."""
    conn.execute("UPDATE pet SET genes = ? WHERE learner_id = ? AND id = ?", (genes_json, learner_id, pet_id))


# --- pet supplies (PLAN.md 11l) ------------------------------------------------------------


def get_supply_counts(conn: sqlite3.Connection, learner_id: int) -> dict[str, int]:
    rows = conn.execute("SELECT item_id, count FROM pet_supply WHERE learner_id = ? AND count > 0", (learner_id,))
    return {r["item_id"]: r["count"] for r in rows}


def add_supply(conn: sqlite3.Connection, learner_id: int, item_id: str, amount: int) -> None:
    conn.execute(
        "INSERT INTO pet_supply (learner_id, item_id, count) VALUES (?, ?, ?)"
        " ON CONFLICT(learner_id, item_id) DO UPDATE SET count = count + excluded.count",
        (learner_id, item_id, amount),
    )


def list_potions(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, colors, tier, slot, bought_on, used_on FROM potion WHERE learner_id = ? ORDER BY id", (learner_id,)
    )
    return [{**dict(r), "colors": json.loads(r["colors"])} for r in rows]


def add_potion(conn: sqlite3.Connection, learner_id: int, colors: list[str], tier: str, slot: int, bought_on: str) -> int:
    cur = conn.execute(
        "INSERT INTO potion (learner_id, colors, tier, slot, bought_on) VALUES (?, ?, ?, ?, ?)",
        (learner_id, json.dumps(colors), tier, slot, bought_on),
    )
    return cur.lastrowid


def use_potion(conn: sqlite3.Connection, learner_id: int, potion_id: int, used_on: str) -> None:
    conn.execute("UPDATE potion SET used_on = ? WHERE learner_id = ? AND id = ?", (used_on, learner_id, potion_id))


def list_habitats(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT spot, kind, name, bought_at FROM habitat WHERE learner_id = ? ORDER BY spot", (learner_id,)
    )
    return [dict(r) for r in rows]


def add_habitat(conn: sqlite3.Connection, learner_id: int, spot: int, kind: str, name: str) -> None:
    conn.execute(
        "INSERT INTO habitat (learner_id, spot, kind, name, bought_at) VALUES (?, ?, ?, ?, ?)",
        (learner_id, spot, kind, name, _now_iso()),
    )


# --- aquariums (PLAN.md 11k) ------------------------------------------------------------


def list_tanks(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT spot, name, background, substrate, bought_at FROM tank WHERE learner_id = ? ORDER BY spot", (learner_id,)
    )
    return [dict(r) for r in rows]


def add_tank(conn: sqlite3.Connection, learner_id: int, spot: int, name: str, background: str, substrate: str) -> None:
    conn.execute(
        "INSERT INTO tank (learner_id, spot, name, background, substrate, bought_at) VALUES (?, ?, ?, ?, ?, ?)",
        (learner_id, spot, name, background, substrate, _now_iso()),
    )


def update_tank(conn: sqlite3.Connection, learner_id: int, spot: int, **fields) -> None:
    bad = set(fields) - {"name", "background", "substrate"}
    if bad:
        raise ValueError(f"can't update {bad}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE tank SET {sets} WHERE learner_id = ? AND spot = ?", (*fields.values(), learner_id, spot))


_PIECE_COLUMNS = "id, item_id, tank, x, y, layer, flip, rot"


def list_tank_pieces(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    rows = conn.execute(f"SELECT {_PIECE_COLUMNS} FROM tank_piece WHERE learner_id = ? ORDER BY id", (learner_id,))
    return [{**dict(r), "flip": bool(r["flip"])} for r in rows]


def add_tank_piece(conn: sqlite3.Connection, learner_id: int, item_id: str, layer: str) -> int:
    cur = conn.execute(
        "INSERT INTO tank_piece (learner_id, item_id, layer) VALUES (?, ?, ?)", (learner_id, item_id, layer)
    )
    return cur.lastrowid


def update_tank_piece(conn: sqlite3.Connection, learner_id: int, piece_id: int, **fields) -> None:
    bad = set(fields) - {"tank", "x", "y", "layer", "flip", "rot"}
    if bad:
        raise ValueError(f"can't update {bad}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE tank_piece SET {sets} WHERE learner_id = ? AND id = ?", (*fields.values(), learner_id, piece_id))


def list_aqua_owned(conn: sqlite3.Connection, learner_id: int) -> set[str]:
    return {r["item_id"] for r in conn.execute("SELECT item_id FROM aqua_owned WHERE learner_id = ?", (learner_id,))}


def add_aqua_owned(conn: sqlite3.Connection, learner_id: int, item_id: str) -> None:
    conn.execute("INSERT OR IGNORE INTO aqua_owned (learner_id, item_id) VALUES (?, ?)", (learner_id, item_id))


def list_pet_color_unlocks(conn: sqlite3.Connection, learner_id: int) -> set[str]:
    rows = conn.execute("SELECT color FROM pet_color_unlock WHERE learner_id = ?", (learner_id,))
    return {r["color"] for r in rows}


def unlock_pet_colors(conn: sqlite3.Connection, learner_id: int, colors: list[str]) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO pet_color_unlock (learner_id, color, unlocked_at) VALUES (?, ?, ?)",
        [(learner_id, c, _now_iso()) for c in colors],
    )


_SHOP_COLUMNS = "dept, idx, seed, species, genes, price_roll, stocked_on, leaves_on, saved, sold"


def _shop_row(row: sqlite3.Row) -> dict:
    return {**dict(row), "genes": json.loads(row["genes"]), "saved": bool(row["saved"]), "sold": bool(row["sold"])}


def list_shop_slots(conn: sqlite3.Connection, learner_id: int, dept: str | None = None) -> list[dict]:
    """One department's slots, or every department's (dept=None)."""
    where, args = ("AND dept = ?", (dept,)) if dept else ("", ())
    rows = conn.execute(
        f"SELECT {_SHOP_COLUMNS} FROM shop_slot WHERE learner_id = ? {where} ORDER BY dept, idx", (learner_id, *args)
    )
    return [_shop_row(r) for r in rows]


def put_shop_slot(conn: sqlite3.Connection, learner_id: int, slot: dict) -> None:
    """Insert or replace one slot (keys as list_shop_slots returns them)."""
    conn.execute(
        f"INSERT OR REPLACE INTO shop_slot (learner_id, {_SHOP_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            learner_id, slot["dept"], slot["idx"], slot["seed"], slot["species"], json.dumps(slot["genes"]),
            slot["price_roll"], slot["stocked_on"], slot["leaves_on"], int(slot["saved"]), int(slot["sold"]),
        ),
    )


def clear_shop_slots(conn: sqlite3.Connection, learner_id: int, dept: str) -> None:
    conn.execute("DELETE FROM shop_slot WHERE learner_id = ? AND dept = ?", (learner_id, dept))


_ORDER_COLUMNS = "species, primary_color, secondary_color, fee, ordered_on, ready_on, leaves_on"


def get_special_order(conn: sqlite3.Connection, learner_id: int) -> dict | None:
    row = conn.execute(f"SELECT {_ORDER_COLUMNS} FROM special_order WHERE learner_id = ?", (learner_id,)).fetchone()
    return dict(row) if row else None


def put_special_order(conn: sqlite3.Connection, learner_id: int, order: dict) -> None:
    """Replace the learner's order (keys as get_special_order returns them)."""
    conn.execute(
        f"INSERT OR REPLACE INTO special_order (learner_id, {_ORDER_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (learner_id, *(order[k] for k in _ORDER_COLUMNS.split(", "))),
    )
