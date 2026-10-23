"""Unit tests for the data layer: schema creation and CRUD round-trips.

Uses an in-memory SQLite DB so these run fast with no filesystem I/O.
"""

from datetime import UTC, datetime

import pytest

from app import db
from app.models import KeyStat, Streak


@pytest.fixture()
def conn():
    with db.open_db(":memory:") as c:
        yield c


def test_schema_creates_all_tables(conn):
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"learner", "key_stat", "session", "session_event", "keystroke_log", "streak"} <= tables


def test_create_and_get_learner(conn):
    learner = db.create_learner(conn, "Sam")
    assert learner.id is not None
    assert learner.name == "Sam"

    fetched = db.get_learner(conn, learner.id)
    assert fetched == learner


def test_get_learner_missing_returns_none(conn):
    assert db.get_learner(conn, 999) is None


def test_key_stat_upsert_then_update(conn):
    learner = db.create_learner(conn, "Sam")
    stat = KeyStat(
        learner_id=learner.id,
        key="f",
        ema_time_ms=250.0,
        confidence=0.4,
        accuracy_rolling=0.9,
        sample_count=10,
        unlocked_at=datetime.now(UTC),
        mastered_at=None,
    )
    db.upsert_key_stat(conn, stat)

    fetched = db.get_key_stat(conn, learner.id, "f")
    assert fetched.confidence == 0.4
    assert fetched.sample_count == 10
    assert fetched.mastered_at is None

    updated = KeyStat(
        learner_id=learner.id,
        key="f",
        ema_time_ms=180.0,
        confidence=1.0,
        accuracy_rolling=0.97,
        sample_count=40,
        unlocked_at=stat.unlocked_at,
        mastered_at=datetime.now(UTC),
    )
    db.upsert_key_stat(conn, updated)

    fetched_again = db.get_key_stat(conn, learner.id, "f")
    assert fetched_again.confidence == 1.0
    assert fetched_again.sample_count == 40
    assert fetched_again.mastered_at is not None


def test_list_key_stats_returns_all_keys_for_learner(conn):
    learner = db.create_learner(conn, "Sam")
    for key in ("f", "j", "d"):
        db.upsert_key_stat(
            conn,
            KeyStat(
                learner_id=learner.id,
                key=key,
                ema_time_ms=200.0,
                confidence=0.5,
                accuracy_rolling=0.9,
                sample_count=5,
                unlocked_at=None,
                mastered_at=None,
            ),
        )
    stats = db.list_key_stats(conn, learner.id)
    assert {s.key for s in stats} == {"f", "j", "d"}


def test_streak_defaults_to_zero_when_absent(conn):
    learner = db.create_learner(conn, "Sam")
    streak = db.get_streak(conn, learner.id)
    assert streak == Streak(
        learner_id=learner.id, current_streak_days=0, longest_streak=0, last_active_date=None
    )


def test_streak_upsert_round_trips(conn):
    learner = db.create_learner(conn, "Sam")
    db.upsert_streak(
        conn,
        Streak(
            learner_id=learner.id,
            current_streak_days=3,
            longest_streak=5,
            last_active_date="2026-10-23",
        ),
    )
    fetched = db.get_streak(conn, learner.id)
    assert fetched.current_streak_days == 3
    assert fetched.longest_streak == 5
    assert fetched.last_active_date == "2026-10-23"
