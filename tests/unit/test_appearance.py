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
