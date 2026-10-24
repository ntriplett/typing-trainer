"""Unit tests for the character designer rules (PLAN.md 11c-2)."""

import pytest

from app import appearance, db, store
from app.appearance import Appearance


@pytest.fixture()
def conn():
    with db.open_db(":memory:") as c:
        yield c


@pytest.fixture()
def learner_id(conn):
    return db.create_learner(conn, "Sam").id


def test_new_learner_gets_the_default_look(conn, learner_id):
    assert appearance.load(conn, learner_id) == Appearance()


def test_legacy_starter_body_converts_to_a_matching_look(conn, learner_id):
    db.set_equipped(conn, learner_id, "body", "body_ember")
    look = appearance.load(conn, learner_id)
    assert look.hair_color == "ginger"
    assert "body" not in db.get_equipped(conn, learner_id)


def test_save_round_trips(conn, learner_id):
    look = Appearance(gender="girl", skin="dark", hair_color="black", hair_style="medium")
    appearance.save(conn, learner_id, look)
    assert appearance.load(conn, learner_id) == look


@pytest.mark.parametrize("field,value", [
    ("gender", "dragon"), ("skin", "green"), ("hair_style", "mohawk"), ("hair_color", "plaid"),
    ("eye_color", "rainbow"),
])
def test_save_rejects_unknown_choices(conn, learner_id, field, value):
    with pytest.raises(appearance.AppearanceError):
        appearance.save(conn, learner_id, Appearance(**{field: value}))


def test_dye_colors_need_the_dye(conn, learner_id):
    with pytest.raises(appearance.AppearanceError, match="dye"):
        appearance.save(conn, learner_id, Appearance(hair_color="green"))
    db.add_owned_item(conn, learner_id, appearance.dye_item_id("green"))
    appearance.save(conn, learner_id, Appearance(hair_color="green"))


def test_every_dye_color_has_a_store_item():
    for color in appearance.DYE_HAIR_COLORS:
        assert store.CATALOG[appearance.dye_item_id(color)].slot == "hair_dye"


def test_appearance_never_mixes_between_learners(conn, learner_id):
    alex = db.create_learner(conn, "Alex").id
    appearance.save(conn, learner_id, Appearance(gender="girl"))
    assert appearance.load(conn, alex).gender == "boy"


def test_old_databases_get_the_eye_color_column(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(
        "CREATE TABLE learner (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT NOT NULL);"
        "CREATE TABLE appearance (learner_id INTEGER PRIMARY KEY, gender TEXT NOT NULL, skin TEXT NOT NULL,"
        " hair_color TEXT NOT NULL, hair_style TEXT NOT NULL);"
        "INSERT INTO learner (name, created_at) VALUES ('Sam', '2026-01-01');"
        "INSERT INTO appearance VALUES (1, 'girl', 'tan', 'black', 'long');"
    )
    old.commit()
    old.close()
    with db.open_db(path) as conn:
        assert appearance.load(conn, 1) == Appearance(
            gender="girl", skin="tan", hair_color="black", hair_style="long", eye_color="brown"
        )
