"""The arcade: games cost arcade tokens (earned by the daily practice goal,
app/daily.py). One play is one whole game, every level; rounds inside it
still pay coins like before (/api/game/.../round).
"""

from __future__ import annotations

import sqlite3

from app import db, farm_stand, lessons
from app.activities.game_modules import GAME_MODULES

PRICES = {"game_crow_patrol_v1": 1, "game_pet_battle_v1": 2, farm_stand.GAME_ID: 1}


class ArcadeError(ValueError):
    """Kid-readable, like StoreError."""


def _ready(conn: sqlite3.Connection, learner_id: int, game) -> bool:
    """Games need a few letters to make words from."""
    letters = [k for k in lessons.taught_keys(conn, learner_id) if k != " "]
    return game.is_eligible([], [" ", *letters])


def games(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    tokens = db.get_token_balance(conn, learner_id)
    return [
        {
            "id": g.id,
            "title": g.title,
            "blurb": g.blurb,
            "game": g.game,
            "price": PRICES.get(g.id, 1),
            "ready": _ready(conn, learner_id, g),
            "affordable": PRICES.get(g.id, 1) <= tokens,
        }
        for g in GAME_MODULES
    ]


def play(conn: sqlite3.Connection, learner_id: int, game_id: str) -> int:
    """Spend the tokens for one play. Returns the new token balance."""
    game = next((g for g in GAME_MODULES if g.id == game_id), None)
    if game is None:
        raise ArcadeError("There's no game like that.")
    if not _ready(conn, learner_id, game):
        raise ArcadeError("Learn a few more letters first! Games need at least 4.")
    price = PRICES.get(game_id, 1)
    if db.get_token_balance(conn, learner_id) < price:
        raise ArcadeError(f"That game needs {price} token{'s' if price > 1 else ''}. Practice to earn more!")
    db.add_tokens(conn, learner_id, -price, "arcade", ref=game_id)
    if game_id == farm_stand.GAME_ID:
        farm_stand.open_day(conn, learner_id)  # this play's day gets saved
    return db.get_token_balance(conn, learner_id)
