"""King Crow can't be farmed: one visit per 12 hours, one token per visit (app/crow_king.py)."""

from datetime import UTC, datetime, timedelta

import pytest

from app import crow_king as king
from app import db, daily

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


@pytest.fixture()
def conn(tmp_path):
    with db.open_db(tmp_path / "t.db") as c:
        db.create_learner(c, "T")
        yield c


LEARNER = 1


def tokens(conn):
    return db.get_token_balance(conn, LEARNER)


def test_he_is_ready_until_he_appears(conn):
    assert king.ready(conn, LEARNER, NOW)
    assert king.appear(conn, LEARNER, NOW)
    assert not king.ready(conn, LEARNER, NOW)
    assert not king.appear(conn, LEARNER, NOW + timedelta(hours=1))  # another game today: no king


def test_he_counts_when_he_appears_even_if_he_gets_away(conn):
    king.appear(conn, LEARNER, NOW)
    assert not king.ready(conn, LEARNER, NOW + daily.REST - timedelta(minutes=1))
    assert king.ready(conn, LEARNER, NOW + daily.REST)


def test_catching_him_pays_one_token_once(conn):
    assert king.caught(conn, LEARNER, NOW) is None  # he hasn't come
    king.appear(conn, LEARNER, NOW)
    assert king.caught(conn, LEARNER, NOW) == 1
    assert king.caught(conn, LEARNER, NOW) is None  # no second token
    assert tokens(conn) == 1


def test_a_new_visit_pays_again_but_an_old_one_doesnt(conn):
    king.appear(conn, LEARNER, NOW)
    assert king.caught(conn, LEARNER, NOW + daily.REST) is None  # too late: he's long gone
    later = NOW + daily.REST
    assert king.appear(conn, LEARNER, later)
    assert king.caught(conn, LEARNER, later) == 1
