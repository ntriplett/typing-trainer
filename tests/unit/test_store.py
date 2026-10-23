"""Unit tests for the store (PLAN.md Section 11c): catalog sanity,
starter grants, buying, equipping, and learner isolation.
"""

import pytest

from app import db, store


@pytest.fixture()
def conn():
    with db.open_db(":memory:") as c:
        yield c


@pytest.fixture()
def learner_id(conn):
    lid = db.create_learner(conn, "Sam").id
    store.grant_starters(conn, lid)
    return lid


def _cheapest_for_sale() -> store.StoreItem:
    return min((i for i in store.CATALOG.values() if not i.starter), key=lambda i: i.price)


# --- catalog ------------------------------------------------------------------


def test_catalog_items_use_known_slots_and_sane_prices():
    for item in store.CATALOG.values():
        assert item.slot in store.SLOTS
        assert item.price >= 0
        assert (item.price == 0) == item.starter


def test_every_starter_body_and_background_exists():
    assert store.CATALOG[store.DEFAULT_BODY].slot == "body"
    assert store.CATALOG[store.DEFAULT_BACKGROUND].slot == "background"
    assert len(store.starter_bodies()) >= 3


def test_there_is_something_to_buy_after_one_session():
    # ~1K coins per 15-minute session: the first purchase should be in reach
    assert _cheapest_for_sale().price <= 1000


# --- starters -----------------------------------------------------------------


def test_grant_starters_equips_default_body_and_background(conn, learner_id):
    assert store.get_avatar(conn, learner_id) == {
        "body": store.DEFAULT_BODY,
        "background": store.DEFAULT_BACKGROUND,
    }


def test_grant_starters_is_idempotent_and_keeps_choices(conn, learner_id):
    other_body = next(i.id for i in store.starter_bodies() if i.id != store.DEFAULT_BODY)
    store.equip(conn, learner_id, other_body)
    store.grant_starters(conn, learner_id)
    assert store.get_avatar(conn, learner_id)["body"] == other_body


def test_grant_starters_with_chosen_body(conn):
    lid = db.create_learner(conn, "Alex").id
    chosen = store.starter_bodies()[-1].id
    store.grant_starters(conn, lid, body=chosen)
    assert store.get_avatar(conn, lid)["body"] == chosen


# --- buying -------------------------------------------------------------------


def test_buy_spends_coins_and_owns_the_item(conn, learner_id):
    item = _cheapest_for_sale()
    db.add_coins(conn, learner_id, item.price + 10, "lesson")
    store.buy(conn, learner_id, item.id)
    assert db.get_coin_balance(conn, learner_id) == 10
    assert item.id in store.owned_ids(conn, learner_id)
    assert db.list_coin_history(conn, learner_id)[0].reason == "purchase"


def test_buy_without_enough_coins_fails_and_changes_nothing(conn, learner_id):
    item = _cheapest_for_sale()
    db.add_coins(conn, learner_id, item.price - 1, "lesson")
    with pytest.raises(store.StoreError, match="coins"):
        store.buy(conn, learner_id, item.id)
    assert db.get_coin_balance(conn, learner_id) == item.price - 1
    assert item.id not in store.owned_ids(conn, learner_id)


def test_buying_twice_fails(conn, learner_id):
    item = _cheapest_for_sale()
    db.add_coins(conn, learner_id, item.price * 2, "lesson")
    store.buy(conn, learner_id, item.id)
    with pytest.raises(store.StoreError, match="already"):
        store.buy(conn, learner_id, item.id)
    assert db.get_coin_balance(conn, learner_id) == item.price


def test_unknown_item_fails(conn, learner_id):
    with pytest.raises(store.StoreError, match="item"):
        store.buy(conn, learner_id, "no_such_thing")


def test_starters_are_not_for_sale(conn, learner_id):
    with pytest.raises(store.StoreError):
        store.buy(conn, learner_id, store.starter_bodies()[-1].id)


# --- equipping ----------------------------------------------------------------


def test_equip_requires_ownership(conn, learner_id):
    with pytest.raises(store.StoreError, match="own"):
        store.equip(conn, learner_id, _cheapest_for_sale().id)


def test_equip_replaces_the_item_in_that_slot(conn, learner_id):
    hats = [i for i in store.CATALOG.values() if i.slot == "hat"]
    assert len(hats) >= 2
    db.add_coins(conn, learner_id, sum(h.price for h in hats), "lesson")
    for hat in hats[:2]:
        store.buy(conn, learner_id, hat.id)
    store.equip(conn, learner_id, hats[0].id)
    store.equip(conn, learner_id, hats[1].id)
    assert store.get_avatar(conn, learner_id)["hat"] == hats[1].id


def test_unequip_clears_slot_but_body_is_required(conn, learner_id):
    hat = next(i for i in store.CATALOG.values() if i.slot == "hat")
    db.add_coins(conn, learner_id, hat.price, "lesson")
    store.buy(conn, learner_id, hat.id)
    store.equip(conn, learner_id, hat.id)
    store.unequip(conn, learner_id, "hat")
    assert "hat" not in store.get_avatar(conn, learner_id)
    with pytest.raises(store.StoreError, match="body"):
        store.unequip(conn, learner_id, "body")


# --- isolation ----------------------------------------------------------------


def test_items_never_mix_between_learners(conn, learner_id):
    alex = db.create_learner(conn, "Alex").id
    store.grant_starters(conn, alex)
    item = _cheapest_for_sale()
    db.add_coins(conn, learner_id, item.price, "lesson")
    store.buy(conn, learner_id, item.id)
    store.equip(conn, learner_id, item.id)
    assert item.id not in store.owned_ids(conn, alex)
    assert item.slot not in store.get_avatar(conn, alex)
    assert db.get_coin_balance(conn, alex) == 0


def test_taking_off_a_background_returns_to_the_starter(conn, learner_id):
    bg = next(i for i in store.CATALOG.values() if i.slot == "background" and not i.starter)
    db.add_coins(conn, learner_id, bg.price, "lesson")
    store.buy(conn, learner_id, bg.id)
    store.equip(conn, learner_id, bg.id)
    store.unequip(conn, learner_id, "background")
    assert store.get_avatar(conn, learner_id)["background"] == store.DEFAULT_BACKGROUND
