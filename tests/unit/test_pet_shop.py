"""Unit tests for the Pet Shop rules (app/pet_shop.py) over a fake calendar:
departments, stock that comes and goes, Save for me, buying, prices."""

import random
import statistics
from datetime import date, timedelta

import pytest

from app import pet_genes as g
from app import pet_shop as shop

DAY0 = date(2026, 11, 1)


def days(n):
    return DAY0 + timedelta(days=n)


def test_departments_match_the_plan():
    expect = {
        "fish": (24, 100, {"fish"}),
        "household": (16, 800, {"dog", "cat", "bunny"}),
        "farm": (12, 2000, {"goat", "sheep", "llama", "fox"}),
        "reptiles": (8, 3000, {"turtle", "lizard", "snake"}),
        "mythical": (2, 10000, {"dragon", "unicorn", "phoenix"}),
    }
    for dept_id, (slots, base, species) in expect.items():
        d = shop.DEPARTMENTS[dept_id]
        assert (d.slots, d.base_price, set(d.species)) == (slots, base, species)
    assert set(shop.STOCKED) == set(expect)
    assert set(shop.BASE_PRICE) == set(g.SPECIES_COLORS) - g.NOT_SOLD_YET  # every finished species is sold somewhere


def test_departments_open_as_rows_are_learned():
    taught = set()
    opened = lambda: {d.id for d in shop.DEPARTMENTS.values() if shop.is_open(d, taught)}  # noqa: E731
    assert opened() == {"fish", "habitats", "aqua", "supplies"}
    assert shop.missing_keys(shop.DEPARTMENTS["household"], set("asdf")) == "ghjkl;"
    taught |= set(shop.HOME_ROW)
    assert opened() == {"fish", "habitats", "aqua", "supplies", "household", "orders"}
    taught |= set(shop.TOP_ROW) | set(shop.BOTTOM_ROW)
    assert opened() == {"fish", "habitats", "aqua", "supplies", "household", "orders", "farm", "reptiles"}
    taught |= set(shop.NUMBERS)
    assert "mythical" in opened()


def test_a_new_shop_fills_every_slot_with_its_species():
    rng = random.Random(1)
    for dept_id in shop.STOCKED:
        stock = shop.refresh(dept_id, [], DAY0, set(), rng)
        dept = shop.DEPARTMENTS[dept_id]
        assert [s.index for s in stock] == list(range(dept.slots))
        assert all(s.species in dept.species and s.genes["species"] == s.species for s in stock)
        assert all(2 <= (s.leaves_on - s.stocked_on).days <= 5 for s in stock)
    household = shop.refresh("household", [], DAY0, set(), rng)
    assert len({s.species for s in household}) == 3  # a mix, not all one kind


def test_pets_stay_2_to_5_days_and_the_shop_changes_a_little_each_day():
    rng = random.Random(2)
    stock = shop.refresh("household", [], DAY0, set(), rng)
    arrived = {s.seed: DAY0 for s in stock}
    changes = []
    for n in range(1, 60):
        today = days(n)
        new = shop.refresh("household", stock, today, set(), rng)
        left = [old for old, now in zip(stock, new) if old.seed != now.seed]
        for old in left:
            assert old.leaves_on == today
            assert 2 <= (today - arrived[old.seed]).days <= 5
        for s in new:
            arrived.setdefault(s.seed, today)
        changes.append(len(left))
        stock = new
    assert max(changes) < 16 and min(changes) < 8
    assert 3 <= statistics.mean(changes) <= 6  # 16 slots / ~3.5 days


def test_the_last_day_banner_shows_the_day_before_a_pet_leaves():
    slot = shop.stock_slot("fish", 0, DAY0, set(), random.Random(3))
    for n in range((slot.leaves_on - DAY0).days):
        assert shop.last_day(slot, days(n)) == (days(n + 1) == slot.leaves_on)
    assert not shop.last_day(shop.save(slot, None), slot.leaves_on - timedelta(days=1))


def test_a_saved_pet_never_leaves_and_only_one_can_be_saved():
    rng = random.Random(4)
    stock = shop.refresh("fish", [], DAY0, set(), rng)
    stock[3] = shop.save(stock[3], None)
    keep = stock[3].seed
    for n in range(1, 30):
        stock = shop.refresh("fish", stock, days(n), set(), rng)
    assert stock[3].seed == keep and stock[3].saved
    assert shop.save(stock[3], stock[3]).saved  # saving it again is fine
    with pytest.raises(shop.ShopError, match="already saving"):
        shop.save(stock[4], stock[3])


def test_letting_a_saved_pet_go_gives_it_one_last_day():
    rng = random.Random(5)
    stock = shop.refresh("fish", [], DAY0, set(), rng)
    stock[0] = shop.save(stock[0], None)
    late = days(20)
    stock[0] = shop.unsave(stock[0], late)
    assert shop.last_day(stock[0], late)
    assert shop.refresh("fish", stock, late, set(), rng)[0].seed == stock[0].seed
    assert shop.refresh("fish", stock, late + timedelta(days=1), set(), rng)[0].seed != stock[0].seed


def test_a_bought_pets_spot_stays_empty_until_tomorrow():
    rng = random.Random(6)
    stock = shop.refresh("fish", [], DAY0, set(), rng)
    stock[2] = shop.sell(shop.save(stock[2], None), DAY0)
    assert stock[2].sold and not stock[2].saved
    with pytest.raises(shop.ShopError):
        shop.sell(stock[2], DAY0)
    assert shop.refresh("fish", stock, DAY0, set(), rng)[2].sold
    assert shop.view(stock[2], DAY0, set()) == {"dept": "fish", "index": 2, "sold": True}
    assert not shop.refresh("fish", stock, days(1), set(), rng)[2].sold


def test_price_rolls_are_a_bell_curve_around_0_75():
    rng = random.Random(7)
    rolls = [shop.roll_price_factor(rng) for _ in range(5000)]
    assert min(rolls) >= 0.25 and max(rolls) <= 1.5
    assert 0.72 <= statistics.mean(rolls) <= 0.80
    assert sum(0.5 <= r <= 1.0 for r in rolls) / len(rolls) > 0.6  # bunched in the middle


def test_prices_follow_base_rarity_new_colors_and_the_roll():
    genes = g.roll("cat", "orange", "lilac", 11, unlocked={"orange", "lilac"})
    rare = g.rarity(genes)
    new_price = shop.price(genes, set(), 1.0)
    known_price = shop.price(genes, {"lilac"} | set(c for c in genes["coat"]["colors"] if c), 1.0)
    assert known_price == shop.nice_price(800 * rare)
    assert new_price == shop.nice_price(800 * rare * 1.5)
    assert shop.price(genes, {"lilac"}, 0.5) < shop.price(genes, {"lilac"}, 1.0)


def test_nice_prices():
    assert [shop.nice_price(x) for x in (1, 73, 1234, 4321, 12345)] == [5, 75, 1230, 4300, 12300]


def test_the_view_has_what_the_shop_page_draws():
    slot = shop.stock_slot("household", 5, DAY0, set(), random.Random(8))
    v = shop.view(slot, DAY0, set())
    assert v["species"] == slot.species and v["genes"]["hex"][0].startswith("#")
    assert v["price"] > 0 and isinstance(v["rare"], dict) and not v["saved"]


# --- special orders ---------------------------------------------------------------


def test_the_order_fee_is_half_the_species_base():
    assert [shop.order_fee(s) for s in ("fish", "cat", "goat", "snake", "dragon")] == [50, 400, 1000, 1500, 5000]


def test_an_order_brings_4_pets_in_the_asked_colors_tomorrow_for_3_days():
    slots = shop.order_slots("cat", "black", None, DAY0, set(), random.Random(1))
    assert len(slots) == shop.ORDER_PETS == 4
    assert {s.dept for s in slots} == {"orders"} and [s.index for s in slots] == [0, 1, 2, 3]
    assert all(s.genes["coat"]["colors"][0] == "black" and s.species == "cat" for s in slots)
    assert {(s.stocked_on, s.leaves_on) for s in slots} == {(days(1), days(4))}
    assert len({s.seed for s in slots}) == 4  # four different pets


def test_an_orders_status_by_day():
    ready, leaves = days(1), days(4)
    assert [shop.order_status(ready, leaves, days(n)) for n in range(6)] == [
        "waiting", "ready", "ready", "ready", None, None,
    ]
