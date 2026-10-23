"""Integration test: a full session lifecycle against a real SQLite file on disk.

Exercises session -> session_event -> keystroke_log together, which is the
shape the skill model and analysis page will read back later.
"""

from app import db


def test_full_session_lifecycle_persists_and_reopens(tmp_path):
    db_path = tmp_path / "typing.db"

    # First "process": run a session and log some keystrokes.
    with db.open_db(db_path) as conn:
        learner = db.create_learner(conn, "Sam")
        session = db.start_session(conn, learner.id)

        event = db.log_session_event(conn, session.id, phase="practice", activity_id="home_row_v1")

        keystrokes = [
            ("f", "f", True, 180),
            ("j", "j", True, 210),
            ("d", "s", False, 340),  # a miss
            ("k", "k", True, 190),
        ]
        for seq, (expected, typed, correct, latency) in enumerate(keystrokes):
            db.log_keystroke(conn, event.id, seq, expected, typed, correct, latency)

        db.end_session_event(
            conn, event.id, summary_stats={"wpm": 12.5, "accuracy": 0.75, "errors": ["d"]}
        )
        db.end_session(conn, session.id)

    # Second "process" (simulates app restart / cache clear): reopen the same
    # file and confirm everything is still there, exactly as a fresh launch
    # of the FastAPI app would see it.
    with db.open_db(db_path) as conn:
        reloaded_learner = db.get_learner(conn, learner.id)
        assert reloaded_learner.name == "Sam"

        logged = db.list_keystrokes_for_event(conn, event.id)
        assert len(logged) == 4
        assert [k.expected_char for k in logged] == ["f", "j", "d", "k"]
        assert logged[2].correct is False
        assert logged[2].typed_char == "s"

        row = conn.execute(
            "SELECT summary_stats, ended_at FROM session_event WHERE id = ?", (event.id,)
        ).fetchone()
        assert row["ended_at"] is not None
        assert '"wpm": 12.5' in row["summary_stats"]

        session_row = conn.execute(
            "SELECT ended_at FROM session WHERE id = ?", (session.id,)
        ).fetchone()
        assert session_row["ended_at"] is not None


def test_key_stats_persist_across_reopen(tmp_path):
    from app.models import KeyStat

    db_path = tmp_path / "typing.db"

    with db.open_db(db_path) as conn:
        learner = db.create_learner(conn, "Sam")
        db.upsert_key_stat(
            conn,
            KeyStat(
                learner_id=learner.id,
                key="f",
                ema_time_ms=200.0,
                confidence=0.6,
                accuracy_rolling=0.92,
                sample_count=20,
                unlocked_at=None,
                mastered_at=None,
            ),
        )

    with db.open_db(db_path) as conn:
        stat = db.get_key_stat(conn, learner.id, "f")
        assert stat is not None
        assert stat.sample_count == 20
        assert stat.confidence == 0.6
