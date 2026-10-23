"""Integration tests for the DB-backed analytics reads: key_report,
worst_bigrams, daily_trend. Against a real (temp) SQLite file.
"""

from datetime import UTC, datetime

from app import analytics, db
from app.models import BigramStat, KeyStat
from app.skill_model import KEY_ORDER


def test_key_report_includes_every_key_even_if_never_attempted(tmp_path):
    with db.open_db(tmp_path / "t.db") as conn:
        learner = db.create_learner(conn, "Sam")
        db.upsert_key_stat(
            conn,
            KeyStat(
                learner_id=learner.id, key="f", ema_time_ms=300.0, confidence=1.3,
                accuracy_rolling=0.97, sample_count=20, unlocked_at=None, mastered_at=None,
            ),
        )
        report = analytics.key_report(conn, learner.id)

    assert len(report) == len(KEY_ORDER)
    f_entry = next(r for r in report if r["key"] == "f")
    assert f_entry["confidence"] == 1.3
    assert f_entry["finger"] == "left_index"

    never_touched = next(r for r in report if r["key"] == "z")
    assert never_touched["sample_count"] == 0
    assert never_touched["accuracy"] is None


def test_worst_bigrams_excludes_low_sample_count_and_ranks_by_accuracy(tmp_path):
    with db.open_db(tmp_path / "t.db") as conn:
        learner = db.create_learner(conn, "Sam")
        db.upsert_bigram_stat(
            conn, BigramStat(learner_id=learner.id, key1="e", key2="i", ema_time_ms=300.0, accuracy_rolling=0.5, sample_count=10)
        )
        db.upsert_bigram_stat(
            conn, BigramStat(learner_id=learner.id, key1="t", key2="h", ema_time_ms=250.0, accuracy_rolling=0.95, sample_count=10)
        )
        db.upsert_bigram_stat(
            conn, BigramStat(learner_id=learner.id, key1="q", key2="z", ema_time_ms=900.0, accuracy_rolling=0.1, sample_count=1)
        )
        worst = analytics.worst_bigrams(conn, learner.id, limit=5, min_samples=3)

    assert [(b.key1, b.key2) for b in worst] == [("e", "i"), ("t", "h")]  # low-sample pair excluded


def test_daily_trend_averages_per_calendar_day(tmp_path):
    with db.open_db(tmp_path / "t.db") as conn:
        learner = db.create_learner(conn, "Sam")
        session = db.start_session(conn, learner.id)

        event1 = db.log_session_event(conn, session.id, "practice", "practice_random_keys_v1")
        db.end_session_event(conn, event1.id, summary_stats={"wpm": 10.0, "accuracy": 0.9})

        event2 = db.log_session_event(conn, session.id, "practice", "practice_random_keys_v1")
        db.end_session_event(conn, event2.id, summary_stats={"wpm": 20.0, "accuracy": 1.0})

        trend = analytics.daily_trend(conn, learner.id)

    assert len(trend) == 1  # both events happened "today"
    assert trend[0]["avg_wpm"] == 15.0
    assert trend[0]["avg_accuracy"] == 0.95
    assert trend[0]["count"] == 2


def test_daily_trend_respects_days_cutoff(tmp_path):
    with db.open_db(tmp_path / "t.db") as conn:
        learner = db.create_learner(conn, "Sam")
        session = db.start_session(conn, learner.id)
        event = db.log_session_event(conn, session.id, "practice", "practice_random_keys_v1")
        db.end_session_event(conn, event.id, summary_stats={"wpm": 10.0, "accuracy": 0.9})

        # Backdate the event far in the past, directly in the DB.
        old_day = "2000-01-01T00:00:00+00:00"
        conn.execute("UPDATE session_event SET started_at = ? WHERE id = ?", (old_day, event.id))
        conn.commit()

        trend = analytics.daily_trend(conn, learner.id, days=7, now=datetime.now(UTC))

    assert trend == []


def test_daily_trend_skips_events_with_no_summary_stats(tmp_path):
    with db.open_db(tmp_path / "t.db") as conn:
        learner = db.create_learner(conn, "Sam")
        session = db.start_session(conn, learner.id)
        db.log_session_event(conn, session.id, "warmup", "warmup_random_keys_v1")  # never ended

        trend = analytics.daily_trend(conn, learner.id)

    assert trend == []
