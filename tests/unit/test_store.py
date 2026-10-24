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
    from app.catalog import OTHER_KINDS

    for item in store.CATALOG.values():
        assert item.slot in store.SLOTS + OTHER_KINDS
        assert item.price >= 0
        assert (item.price == 0) == item.starter


def test_default_background_is_a_starter():
    assert store.CATALOG[store.DEFAULT_BACKGROUND].slot == "background"
    assert store.CATALOG[store.DEFAULT_BACKGROUND].starter


def test_there_is_something_to_buy_after_one_session():
    # ~1K coins per 15-minute session: the first purchase should be in reach
    assert _cheapest_for_sale().price <= 1000


# --- starters -----------------------------------------------------------------


def test_grant_starters_equips_default_background_and_clothes(conn, learner_id):
    avatar = store.get_avatar(conn, learner_id)
    assert {k: v for k, v in avatar.items() if k in store.SLOTS} == store.SLOT_DEFAULTS
    assert avatar["pets"] == []
    assert avatar["night"] is False
    assert avatar["appearance"]["hair_style"] == "short"


def test_every_slot_default_is_a_starter_in_that_slot():
    for slot, item_id in store.SLOT_DEFAULTS.items():
        assert store.CATALOG[item_id].starter
        assert store.CATALOG[item_id].slot == slot


def test_grant_starters_is_idempotent_and_keeps_choices(conn, learner_id):
    bg = next(i for i in store.CATALOG.values() if i.slot == "background" and not i.starter)
    db.add_coins(conn, learner_id, bg.price, "lesson")
    store.buy(conn, learner_id, bg.id)
    store.equip(conn, learner_id, bg.id)
    store.grant_starters(conn, learner_id)
    assert store.get_avatar(conn, learner_id)["background"] == bg.id


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
        store.buy(conn, learner_id, store.DEFAULT_BACKGROUND)


def test_using_a_hair_dye_recolors_hair(conn, learner_id):
    dye = store.CATALOG["dye_blue"]
    db.add_coins(conn, learner_id, dye.price, "lesson")
    store.buy(conn, learner_id, dye.id)
    store.equip(conn, learner_id, dye.id)
    assert store.get_avatar(conn, learner_id)["appearance"]["hair_color"] == "blue"


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
    assert store.get_avatar(conn, alex).get(item.slot) != item.id
    assert db.get_coin_balance(conn, alex) == 0


def test_taking_off_a_background_returns_to_the_starter(conn, learner_id):
    bg = next(i for i in store.CATALOG.values() if i.slot == "background" and not i.starter)
    db.add_coins(conn, learner_id, bg.price, "lesson")
    store.buy(conn, learner_id, bg.id)
    store.equip(conn, learner_id, bg.id)
    store.unequip(conn, learner_id, "background")
    assert store.get_avatar(conn, learner_id)["background"] == store.DEFAULT_BACKGROUND


def test_taking_off_a_shirt_puts_the_starter_tunic_back(conn, learner_id):
    shirt = next(i for i in store.CATALOG.values() if i.slot == "shirt" and not i.starter)
    db.add_coins(conn, learner_id, shirt.price, "lesson")
    store.buy(conn, learner_id, shirt.id)
    store.equip(conn, learner_id, shirt.id)
    store.unequip(conn, learner_id, "shirt")
    assert store.get_avatar(conn, learner_id)["shirt"] == store.SLOT_DEFAULTS["shirt"]



# --- places + night -------------------------------------------------------------


def test_every_place_has_a_group_with_a_night_unlock():
    from app.catalog import night_item_id, place_group

    places = [i for i in store.CATALOG.values() if i.slot == "background"]
    assert len(places) == 18
    for place in places:
        group = place_group(place.id)
        assert group == place.group
        assert store.CATALOG[night_item_id(group)].slot == "night"


def _buy_and_use(conn, learner_id, item_id):
    db.add_coins(conn, learner_id, store.CATALOG[item_id].price, "test")
    store.buy(conn, learner_id, item_id)
    store.equip(conn, learner_id, item_id)


def test_night_needs_the_unlock_for_the_current_places_group(conn, learner_id):
    with pytest.raises(store.StoreError, match="night"):
        store.set_night(conn, learner_id, True)
    _buy_and_use(conn, learner_id, "night_forests")  # meadow is a forests-group place
    assert store.get_avatar(conn, learner_id)["night"] is True


def test_night_hides_in_a_place_without_its_unlock_and_comes_back(conn, learner_id):
    _buy_and_use(conn, learner_id, "night_forests")
    _buy_and_use(conn, learner_id, "bg_beach")  # water group: no night unlock
    assert store.night_status(conn, learner_id) == {"available": False, "on": False, "group": "water"}
    store.unequip(conn, learner_id, "background")  # back to the meadow
    assert store.night_status(conn, learner_id)["on"] is True


def test_night_unlock_without_any_of_its_places_says_which_to_get(conn, learner_id):
    db.add_coins(conn, learner_id, 5000, "test")
    store.buy(conn, learner_id, "night_space")
    with pytest.raises(store.StoreError, match="Outer Space, The Moon, Mars"):
        store.equip(conn, learner_id, "night_space")


def test_night_unlock_takes_you_to_one_of_its_places(conn, learner_id):
    _buy_and_use(conn, learner_id, "bg_moon")
    store.unequip(conn, learner_id, "background")  # back in the meadow (forests group)
    _buy_and_use(conn, learner_id, "night_space")
    avatar = store.get_avatar(conn, learner_id)
    assert avatar["background"] == "bg_moon" and avatar["night"] is True


def test_turning_night_off(conn, learner_id):
    _buy_and_use(conn, learner_id, "night_forests")
    store.set_night(conn, learner_id, False)
    assert store.get_avatar(conn, learner_id)["night"] is False
