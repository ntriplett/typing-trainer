"""The arcade: games cost arcade tokens (earned by the daily practice goal,
app/daily.py). One play is one whole game, every level; rounds inside it
still pay coins like before (/api/game/.../round). Buying a play gives a pass for
that many rounds, so the page can't be opened or paid without one: refreshing or
replaying can't pay more rounds than were bought.
"""

from __future__ import annotations

import sqlite3

from app import db, farm_stand, lessons
from app.activities.game_modules import GAME_MODULES
from app.wanderpaw import save as wander

WANDERPAW = "wanderpaw"
WANDERPAW_LETTERS = 6  # a whole adventure wants more words than the other games
PRICES = {"game_crow_patrol_v1": 1, farm_stand.GAME_ID: 1, WANDERPAW: 2}
REPLACED = "game_pet_battle_v1"  # Wanderpaw took its place (it's still in the game lab)


class ArcadeError(ValueError):
    """Kid-readable, like StoreError."""


def _ready(conn: sqlite3.Connection, learner_id: int, game) -> bool:
    """Games need a few letters to make words from."""
    letters = [k for k in lessons.taught_keys(conn, learner_id) if k != " "]
    return game.is_eligible([], [" ", *letters])


def _letters_short(conn: sqlite3.Connection, learner_id: int) -> int:
    """How many more letters it takes to play Wanderpaw."""
    letters = [k for k in lessons.taught_keys(conn, learner_id) if k.isalpha()]
    return max(0, WANDERPAW_LETTERS - len(letters))


def _wanderpaw(conn: sqlite3.Connection, learner_id: int, tokens: int) -> dict:
    """Not one of the game modules: it's its own page, and a play buys a day. A day
    you've paid for or left unfinished is yours to go back to for free."""
    save = wander.load(conn, learner_id)
    price = PRICES[WANDERPAW]
    short = _letters_short(conn, learner_id)
    return {
        "id": WANDERPAW,
        "title": "Wanderpaw",
        "blurb": "Explore the lands with your pets, and carry the letters home. Each play is a new day at full energy.",
        "game": WANDERPAW,
        "price": price,
        "ready": not short,
        "locked_note": f"Learn {short} more letter{'s' if short > 1 else ''} to unlock this game!" if short else None,
        "affordable": price <= tokens,
        "url": "/wanderpaw",
        "paid": wander.has_paid(save),
        "unfinished": bool(save["trip"]),
    }


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
        if g.id != REPLACED
    ] + [_wanderpaw(conn, learner_id, tokens)]


def _play_wanderpaw(conn: sqlite3.Connection, learner_id: int) -> int:
    if _letters_short(conn, learner_id):
        raise ArcadeError(f"Learn a few more letters first! Wanderpaw needs at least {WANDERPAW_LETTERS}.")
    if wander.has_paid(wander.load(conn, learner_id)):
        return db.get_token_balance(conn, learner_id)  # already paid for: never twice
    price = PRICES[WANDERPAW]
    if db.get_token_balance(conn, learner_id) < price:
        raise ArcadeError(f"Wanderpaw needs {price} tokens. Practice to earn more!")
    db.add_tokens(conn, learner_id, -price, "arcade", ref=WANDERPAW)
    wander.day_bought(conn, learner_id)
    return db.get_token_balance(conn, learner_id)


def _pass_key(game_id: str) -> str:
    return f"arcade_rounds_left:{game_id}"


def rounds_left(conn: sqlite3.Connection, learner_id: int, game_id: str) -> int:
    return int(db.get_setting(conn, learner_id, _pass_key(game_id)) or 0)


def spend_round(conn: sqlite3.Connection, learner_id: int, game_id: str) -> bool:
    """A round finished: True if a bought play covers it."""
    left = rounds_left(conn, learner_id, game_id)
    if left <= 0:
        return False
    db.set_setting(conn, learner_id, _pass_key(game_id), str(left - 1))
    return True


def play(conn: sqlite3.Connection, learner_id: int, game_id: str) -> int:
    """Spend the tokens for one play. Returns the new token balance."""
    if game_id == WANDERPAW:
        return _play_wanderpaw(conn, learner_id)
    game = next((g for g in GAME_MODULES if g.id == game_id and g.id != REPLACED), None)
    if game is None:
        raise ArcadeError("There's no game like that.")
    if not _ready(conn, learner_id, game):
        raise ArcadeError("Learn a few more letters first! Games need at least 4.")
    price = PRICES.get(game_id, 1)
    if db.get_token_balance(conn, learner_id) < price:
        raise ArcadeError(f"That game needs {price} token{'s' if price > 1 else ''}. Practice to earn more!")
    db.add_tokens(conn, learner_id, -price, "arcade", ref=game_id)
    db.set_setting(conn, learner_id, _pass_key(game_id), str(len(game.levels)))
    if game_id == farm_stand.GAME_ID:
        farm_stand.open_day(conn, learner_id)  # this play's day gets saved
    return db.get_token_balance(conn, learner_id)
