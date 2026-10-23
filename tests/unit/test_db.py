"""Unit tests for the data layer: schema creation and CRUD round-trips.

Uses an in-memory SQLite DB so these run fast with no filesystem I/O.
"""

from datetime import UTC, datetime

import pytest

from app import db
from app.models import BigramStat, KeyStat, Streak


@pytest.fixture()
def conn():
    with db.open_db(":memory:") as c:
        yield c


def test_schema_creates_all_tables(conn):
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {
        "learner", "key_stat", "bigram_stat", "session", "session_event",
        "keystroke_log", "streak", "coin_ledger", "owned_item", "equipped_item",
    } <= tables


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


def test_bigram_stat_upsert_then_update(conn):
    learner = db.create_learner(conn, "Sam")
    stat = BigramStat(
        learner_id=learner.id, key1="e", key2="i", ema_time_ms=300.0, accuracy_rolling=0.9, sample_count=5
    )
    db.upsert_bigram_stat(conn, stat)

    fetched = db.get_bigram_stat(conn, learner.id, "e", "i")
    assert fetched.ema_time_ms == 300.0
    assert fetched.sample_count == 5

    updated = BigramStat(
        learner_id=learner.id, key1="e", key2="i", ema_time_ms=220.0, accuracy_rolling=0.95, sample_count=12
    )
    db.upsert_bigram_stat(conn, updated)
    fetched_again = db.get_bigram_stat(conn, learner.id, "e", "i")
    assert fetched_again.ema_time_ms == 220.0
    assert fetched_again.sample_count == 12


def test_bigram_stat_is_directional():
    with db.open_db(":memory:") as conn:
        learner = db.create_learner(conn, "Sam")
        db.upsert_bigram_stat(
            conn, BigramStat(learner_id=learner.id, key1="e", key2="i", ema_time_ms=200.0, accuracy_rolling=1.0, sample_count=1)
        )
        assert db.get_bigram_stat(conn, learner.id, "i", "e") is None
        assert db.get_bigram_stat(conn, learner.id, "e", "i") is not None


def test_list_bigram_stats_returns_all_pairs_for_learner(conn):
    learner = db.create_learner(conn, "Sam")
    for k1, k2 in (("e", "i"), ("t", "h"), ("a", "n")):
        db.upsert_bigram_stat(
            conn, BigramStat(learner_id=learner.id, key1=k1, key2=k2, ema_time_ms=300.0, accuracy_rolling=0.9, sample_count=3)
        )
    pairs = {(s.key1, s.key2) for s in db.list_bigram_stats(conn, learner.id)}
    assert pairs == {("e", "i"), ("t", "h"), ("a", "n")}


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


def test_connection_is_usable_from_a_different_thread(tmp_path):
    """Regression for PLAN.md 11b: FastAPI may open a request's
    connection on one threadpool worker and use/commit/close it on
    another. That used to raise sqlite3.ProgrammingError at random.
    """
    import threading

    db_path = tmp_path / "t.db"
    ctx = db.open_db(db_path)
    conn = ctx.__enter__()
    errors = []

    def use_then_close():
        try:
            db.create_learner(conn, "Sam")
            ctx.__exit__(None, None, None)
        except Exception as exc:  # noqa: BLE001 -- surfaced via assert below
            errors.append(exc)

    worker = threading.Thread(target=use_then_close)
    worker.start()
    worker.join()

    assert errors == []
    with db.open_db(db_path) as check:
        assert db.get_learner(check, 1).name == "Sam"


# --- coin ledger -------------------------------------------------------------


def test_coin_balance_starts_at_zero(conn):
    learner = db.create_learner(conn, "Sam")
    assert db.get_coin_balance(conn, learner.id) == 0


def test_coin_balance_sums_earns_and_spends(conn):
    learner = db.create_learner(conn, "Sam")
    db.add_coins(conn, learner.id, 85, "lesson", ref="event:1")
    db.add_coins(conn, learner.id, 50, "mastered_key", ref="d")
    db.add_coins(conn, learner.id, -100, "purchase", ref="straw_hat")
    assert db.get_coin_balance(conn, learner.id) == 35


def test_coin_history_is_newest_first(conn):
    learner = db.create_learner(conn, "Sam")
    db.add_coins(conn, learner.id, 85, "lesson")
    db.add_coins(conn, learner.id, -20, "purchase", ref="apple")
    history = db.list_coin_history(conn, learner.id)
    assert [(e.amount, e.reason, e.ref) for e in history] == [(-20, "purchase", "apple"), (85, "lesson", None)]


def test_coins_never_mix_between_learners(conn):
    sam = db.create_learner(conn, "Sam")
    alex = db.create_learner(conn, "Alex")
    db.add_coins(conn, sam.id, 100, "lesson")
    db.add_coins(conn, alex.id, 7, "lesson")
    assert db.get_coin_balance(conn, sam.id) == 100
    assert db.get_coin_balance(conn, alex.id) == 7
    assert [e.amount for e in db.list_coin_history(conn, alex.id)] == [7]
