"""Unit tests for pets (PLAN.md 11c-2, phase 4): adopting, daily feeding
and growth, naming, the 2-along limit, legacy conversion, isolation."""

from datetime import date, timedelta

import pytest

from app import db, pets, store


@pytest.fixture()
def conn():
    with db.open_db(":memory:") as c:
        yield c


@pytest.fixture()
def learner_id(conn):
    lid = db.create_learner(conn, "Sam").id
    db.add_coins(conn, lid, 50_000, "test")
    return lid


def test_adopting_costs_coins_and_starts_a_baby_that_comes_along(conn, learner_id):
    pet = pets.adopt(conn, learner_id, "cat", "orange")
    assert pet["growth"] == 0 and pet["stage"] == "baby" and pet["slot"] == 1
    assert pet["name"] == "Cat"
    assert db.get_coin_balance(conn, learner_id) == 50_000 - pets.SPECIES["cat"].price


def test_only_two_come_along_and_more_wait_at_home(conn, learner_id):
    slots = [pets.adopt(conn, learner_id, "dog", "brown")["slot"] for _ in range(3)]
    assert slots == [1, 2, None]
    assert len(pets.along(conn, learner_id)) == 2


def test_unknown_species_or_color_is_refused(conn, learner_id):
    with pytest.raises(pets.PetError):
        pets.adopt(conn, learner_id, "dragon", "red")
    with pytest.raises(pets.PetError):
        pets.adopt(conn, learner_id, "cat", "plaid")


def test_adopting_without_enough_coins(conn):
    poor = db.create_learner(conn, "Poor").id
    with pytest.raises(pets.PetError, match="more coins"):
        pets.adopt(conn, poor, "llama", "white")


def test_feeding_grows_once_per_day(conn, learner_id, monkeypatch):
    pet = pets.adopt(conn, learner_id, "bunny", "white")
    fed = pets.feed(conn, learner_id, pet["id"])
    assert fed["growth"] == 1 and fed["fed_today"]
    with pytest.raises(pets.PetError, match="tomorrow"):
        pets.feed(conn, learner_id, pet["id"])

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    monkeypatch.setattr(pets, "_today", lambda: tomorrow)
    assert pets.feed(conn, learner_id, pet["id"])["growth"] == 2


def test_stages_and_full_growth(conn, learner_id):
    assert [pets.stage(g) for g in (0, 3, 4, 9, 10)] == ["baby", "baby", "young", "young", "grown"]
    pet = pets.adopt(conn, learner_id, "goat", "tan")
    db.update_pet(conn, learner_id, pet["id"], growth=pets.MAX_GROWTH)
    with pytest.raises(pets.PetError, match="grown"):
        pets.feed(conn, learner_id, pet["id"])


def test_rename(conn, learner_id):
    pet = pets.adopt(conn, learner_id, "sheep", "pink")
    assert pets.rename(conn, learner_id, pet["id"], "  Puff ")["name"] == "Puff"
    with pytest.raises(pets.PetError):
        pets.rename(conn, learner_id, pet["id"], "x" * 40)


def test_bringing_a_pet_along_sends_the_slots_previous_pet_home(conn, learner_id):
    a = pets.adopt(conn, learner_id, "cat", "gray")
    b = pets.adopt(conn, learner_id, "cat", "black")
    c = pets.adopt(conn, learner_id, "cat", "white")
    pets.set_along(conn, learner_id, c["id"], 1)
    slots = {p["id"]: p["slot"] for p in pets.list_pets(conn, learner_id)}
    assert slots == {a["id"]: None, b["id"]: 2, c["id"]: 1}
    pets.set_along(conn, learner_id, b["id"], None)
    assert [p["id"] for p in pets.along(conn, learner_id)] == [c["id"]]


def test_pets_never_mix_between_learners(conn, learner_id):
    alex = db.create_learner(conn, "Alex").id
    pet = pets.adopt(conn, learner_id, "fox", "red")
    assert pets.list_pets(conn, alex) == []
    with pytest.raises(pets.PetError, match="isn't yours"):
        pets.feed(conn, alex, pet["id"])


def test_legacy_pet_items_become_grown_pets(conn, learner_id):
    db.add_owned_item(conn, learner_id, "pet_fox")
    db.add_owned_item(conn, learner_id, "pet_hedgehog")
    db.set_equipped(conn, learner_id, "pet", "pet_fox")
    avatar = store.get_avatar(conn, learner_id)
    assert [(p["species"], p["stage"], p["slot"]) for p in avatar["pets"]] == [("fox", "grown", 1)]
    assert {p["species"] for p in pets.list_pets(conn, learner_id)} == {"fox", "hedgehog"}
    store.get_avatar(conn, learner_id)  # idempotent
    assert len(pets.list_pets(conn, learner_id)) == 2
