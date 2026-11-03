"""King Crow: Crow Patrol's rare last-round guest, who pays an arcade token instead
of coins. He comes once per REST (the daily goal's 12-hour rhythm), counted when he
shows up, caught or not, so tokens can't be farmed by playing again. The server
keeps this: the game page only asks.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from app import daily, db

SETTING_SEEN = "king_crow_seen_at"
SETTING_PAID = "king_crow_paid_for"  # the visit (its seen_at) already paid
TOKENS = 1


def _seen(conn: sqlite3.Connection, learner_id: int) -> datetime | None:
    value = db.get_setting(conn, learner_id, SETTING_SEEN)
    return datetime.fromisoformat(value) if value else None


def ready(conn: sqlite3.Connection, learner_id: int, now: datetime) -> bool:
    seen = _seen(conn, learner_id)
    return seen is None or now - seen >= daily.REST


def appear(conn: sqlite3.Connection, learner_id: int, now: datetime) -> bool:
    """He's flying in, if he may: that's today's visit used."""
    if not ready(conn, learner_id, now):
        return False
    db.set_setting(conn, learner_id, SETTING_SEEN, now.isoformat())
    return True


def caught(conn: sqlite3.Connection, learner_id: int, now: datetime) -> int | None:
    """Shooed him: the token, once a visit. The new balance, or None if there's nothing to pay."""
    seen = _seen(conn, learner_id)
    if seen is None or now - seen >= daily.REST or db.get_setting(conn, learner_id, SETTING_PAID) == seen.isoformat():
        return None
    db.set_setting(conn, learner_id, SETTING_PAID, seen.isoformat())
    db.add_tokens(conn, learner_id, TOKENS, "king_crow")
    return db.get_token_balance(conn, learner_id)
