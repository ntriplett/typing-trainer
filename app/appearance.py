"""The character designer (PLAN.md Section 11c-2): boy/girl, skin tone,
hair color, and hair length. Appearance is learner data, not store items,
so changing it is free -- except fancy hair dyes, which are store items
(catalog slot "hair_dye") that unlock extra colors here.

The ids here are drawing keys: web/static/js/sprites.js maps each to its
colors/pixels, so the two lists must stay in sync (test_appearance checks
the Python side; the sprite sheet's dev guard checks the JS side).
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass

from app import db

GENDERS = ("boy", "girl")
SKIN_TONES = ("light", "fair", "tan", "brown", "dark")
HAIR_STYLES = ("short", "medium", "long")
EYE_COLORS = ("brown", "blue", "green", "hazel", "gray")
NATURAL_HAIR_COLORS = ("brown", "black", "blonde", "ginger", "sandy")
# Unlocked by buying the matching "dye_<color>" store item.
DYE_HAIR_COLORS = ("blue", "green", "pink", "purple", "silver", "cherry")


@dataclass(frozen=True, slots=True)
class Appearance:
    gender: str = "boy"
    skin: str = "light"
    hair_color: str = "brown"
    hair_style: str = "short"
    eye_color: str = "brown"


# Learners created before the designer had one of three starter "body"
# items equipped; keep their look when converting.
_LEGACY_BODIES = {
    "body_sprout": Appearance(hair_color="brown", skin="light"),
    "body_ember": Appearance(hair_color="ginger", skin="fair"),
    "body_moss": Appearance(hair_color="black", skin="brown"),
}


class AppearanceError(ValueError):
    """Kid-readable, like StoreError."""


def dye_item_id(color: str) -> str:
    return f"dye_{color}"


def unlocked_hair_colors(owned_item_ids: set[str]) -> list[str]:
    return list(NATURAL_HAIR_COLORS) + [
        c for c in DYE_HAIR_COLORS if dye_item_id(c) in owned_item_ids
    ]


def load(conn: sqlite3.Connection, learner_id: int) -> Appearance:
    """The learner's appearance, creating it on first use (converting a
    legacy starter body if there is one)."""
    row = db.get_appearance(conn, learner_id)
    if row is not None:
        return Appearance(**row)
    legacy_body = db.get_equipped(conn, learner_id).get("body")
    appearance = _LEGACY_BODIES.get(legacy_body, Appearance())
    db.set_appearance(conn, learner_id, **asdict(appearance))
    db.clear_equipped(conn, learner_id, "body")
    return appearance


def save(conn: sqlite3.Connection, learner_id: int, appearance: Appearance) -> Appearance:
    owned = db.list_owned_item_ids(conn, learner_id)
    checks = [
        (appearance.gender, GENDERS, "look"),
        (appearance.skin, SKIN_TONES, "skin tone"),
        (appearance.hair_style, HAIR_STYLES, "hair length"),
        (appearance.eye_color, EYE_COLORS, "eye color"),
    ]
    for value, allowed, label in checks:
        if value not in allowed:
            raise AppearanceError(f"{value!r} isn't a {label} you can pick.")
    if appearance.hair_color not in NATURAL_HAIR_COLORS + DYE_HAIR_COLORS:
        raise AppearanceError(f"{appearance.hair_color!r} isn't a hair color.")
    if appearance.hair_color not in unlocked_hair_colors(owned):
        raise AppearanceError("Buy that hair dye in the store first!")
    db.set_appearance(conn, learner_id, **asdict(appearance))
    return appearance


def options(conn: sqlite3.Connection, learner_id: int) -> dict:
    """Everything the designer page offers, with dye colors marked
    locked/unlocked."""
    unlocked = set(unlocked_hair_colors(db.list_owned_item_ids(conn, learner_id)))
    return {
        "gender": list(GENDERS),
        "skin": list(SKIN_TONES),
        "hair_style": list(HAIR_STYLES),
        "eye_color": list(EYE_COLORS),
        "hair_color": [
            {"id": c, "unlocked": c in unlocked, "dye": c in DYE_HAIR_COLORS}
            for c in NATURAL_HAIR_COLORS + DYE_HAIR_COLORS
        ],
    }
