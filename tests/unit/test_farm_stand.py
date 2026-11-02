"""Unit tests for the Farm Stand's rules (app/farm_stand.py): the save, the
upgrade shop, stars, checking and applying a day, the veggie reward,
customers, and the pacing that keeps the farm growing past 50 days."""

import random

import pytest

from app import db, farm_stand as f
from app import pet_shop


@pytest.fixture()
def conn():
    with db.open_db(":memory:") as c:
        yield c


@pytest.fixture()
def learner_id(conn):
    return db.create_learner(conn, "Sam").id


def test_a_new_farm_starts_small():
    s = f.new_save()
    assert s["money"] == f.START_MONEY and s["day"] == 0
    st = f.state(s)
    assert st["plots"] == 4 and st["shelf"] == 8
    assert {c["id"] for c in st["crops"]} == {"radish", "peas", "carrot"}
    assert st["next_crop"]["id"] == "tomato"


def test_every_crop_is_a_garden_veggie_and_opens_in_order():
    from app import garden

    assert set(f.CROPS) <= set(garden.VEGGIES)
    reps = [c.rep for c in f.CROPS.values()]
    assert reps == sorted(reps)


def test_buying_spends_money_and_levels_up():
    s = {**f.new_save(), "money": 100}
    s = f.apply_buy(s, "plots")
    assert f.value(s, "plots") == 5 and s["money"] == 100 - f.UPGRADES["plots"].costs[0]


@pytest.mark.parametrize(
    ("save", "upgrade", "message"),
    [
        ({"money": 0}, "plots", "costs"),
        ({"money": 999}, "bell", "reputation"),
        ({"money": 999}, "nope", "no upgrade"),
        ({"money": 9999, "reputation": 999, "upgrades": {"compost": 2}}, "compost", "as big"),
    ],
)
def test_buying_refuses_kindly(save, upgrade, message):
    with pytest.raises(f.FarmError, match=message):
        f.apply_buy({**f.new_save(), **save}, upgrade)


def test_shop_says_what_is_locked_and_affordable():
    shop = {u["id"]: u for u in f.shop({**f.new_save(), "money": 50})}
    assert shop["plots"]["can_buy"] and shop["plots"]["next_value"] == 5
    assert not shop["bell"]["can_buy"] and shop["bell"]["needs_rep"] == f.UPGRADES["bell"].rep[0]
    assert shop["flowers"]["needs_rep"] and f.UPGRADES["flowers"].decor


@pytest.mark.parametrize(
    ("served", "missed", "stars"),
    [(0, 0, 0), (0, 5, 0), (1, 9, 1), (5, 5, 2), (8, 2, 3), (3, 0, 2), (6, 1, 3)],
)
def test_stars(served, missed, stars):
    assert f.stars_for(served, missed) == stars


def test_check_day_catches_impossible_days():
    s = f.new_save()
    f.check_day(s, 3, 1, {"radish": 4}, 12, 4)
    with pytest.raises(f.FarmError, match="isn't open"):
        f.check_day(s, 1, 0, {"pumpkin": 1}, 16, 0)
    with pytest.raises(f.FarmError, match="can grow"):
        f.check_day(s, 1, 0, {"radish": f.max_sold(s) + 1}, 0, 0)
    with pytest.raises(f.FarmError, match="worth"):
        f.check_day(s, 1, 0, {"radish": 2}, 100, 0)
    with pytest.raises(f.FarmError, match="at least one"):
        f.check_day(s, 5, 0, {"radish": 2}, 4, 0)
    with pytest.raises(f.FarmError, match="less than nothing"):
        f.check_day(s, 1, 0, {"radish": 2}, -1, 0)


def test_apply_day_adds_money_reputation_and_opens_crops():
    s = {**f.new_save(), "reputation": 5}
    new, tally = f.apply_day(s, 9, 1, {"radish": 12}, 30, 6)
    assert tally["stars"] == 3 and tally["profit"] == 24
    assert new["money"] == f.START_MONEY + 24 and new["reputation"] == 8 and new["day"] == 1
    assert tally["new_crops"] == ["tomato"]
    assert new["great_days"] == 1 and new["best_day"] == 24


def test_money_never_saves_below_zero():
    new, _ = f.apply_day(f.new_save(), 0, 3, {}, 0, 50)
    assert new["money"] == 0


def test_lab_days_change_nothing(conn, learner_id):
    out = f.finish_day(conn, learner_id, 9, 1, {"radish": 12}, 30, 6)
    assert not out["counted"] and out["veggie"] is None and out["stars"] == 3
    assert f.load(conn, learner_id)["day"] == 0
    assert db.get_veggies(conn, learner_id) == {}


def test_an_arcade_day_saves_once_and_great_days_give_a_veggie(conn, learner_id):
    f.open_day(conn, learner_id)
    out = f.finish_day(conn, learner_id, 9, 1, {"radish": 10, "peas": 2}, 30, 6, rng=random.Random(1))
    assert out["counted"] and out["veggie"] in ("radish", "peas")
    assert db.get_veggies(conn, learner_id) == {out["veggie"]: 1}
    save = f.load(conn, learner_id)
    assert save["day"] == 1 and not save["open_day"]
    again = f.finish_day(conn, learner_id, 9, 1, {"radish": 12}, 30, 6)  # no new token: not saved
    assert not again["counted"] and f.load(conn, learner_id)["day"] == 1


def test_an_ok_day_gives_no_veggie(conn, learner_id):
    f.open_day(conn, learner_id)
    out = f.finish_day(conn, learner_id, 5, 5, {"radish": 6}, 18, 3)
    assert out["stars"] == 2 and out["veggie"] is None and db.get_veggies(conn, learner_id) == {}


def test_buy_saves(conn, learner_id):
    db.save_farm(conn, learner_id, {**f.new_save(), "money": 100})
    f.buy(conn, learner_id, "plots")
    assert f.value(f.load(conn, learner_id), "plots") == 5


def test_customers_are_grown_land_animals_with_favorites():
    land = {sp for d in ("household", "farm", "reptiles") for sp in pet_shop.DEPARTMENTS[d].species}
    mythical = {*pet_shop.DEPARTMENTS["mythical"].species, "flower_fairy"}
    people = f.customers(set(), random.Random(3), count=40)
    assert len(people) == 40
    assert all(p["growth"] == f.CUSTOMER_GROWTH and p["genes"]["hex"][0] for p in people)
    assert {p["species"] for p in people} <= land | mythical
    assert len({p["species"] for p in people}) > 4
    assert all(p["favorite"] == p["genes"]["personality"]["favorite"] for p in people)


def _simulate(days: int, stars=(3, 2, 2, 3, 1, 2)):
    """A player who earns typical_day_profit and buys the cheapest thing they
    can, with about 2 stars a day. Returns the days something new opened."""
    s = f.new_save()
    news = []
    for day in range(1, days + 1):
        st = stars[day % len(stars)]
        served, missed = {3: (9, 1), 2: (6, 4), 1: (2, 8)}[st]
        profit = f.typical_day_profit(s)
        s, tally = f.apply_day(s, served, missed, {}, 0, 0)
        s["money"] += profit
        bought = False
        while opts := [u for u in f.shop(s) if u["can_buy"]]:
            s = f.apply_buy(s, min(opts, key=lambda u: u["cost"])["id"])
            bought = True
        if bought or tally["new_crops"]:
            news.append(day)
    return news, s


def test_the_farm_keeps_growing_past_50_days():
    news, s = _simulate(50)
    gaps = [b - a for a, b in zip([0, *news], news)]
    assert max(gaps) <= 5, gaps
    assert news[-1] >= 48
    assert any(u["level"] < u["max_level"] for u in f.shop(s)), "everything bought by day 50"


def test_profit_grows_but_not_wildly():
    first = f.typical_day_profit(f.new_save())
    _, late = _simulate(50)
    assert 20 <= first <= 80
    assert first * 3 <= f.typical_day_profit(late) <= first * 20


def _people(n=12):
    return [{"favorite": "carrot"}] * n


def test_deliveries_come_from_open_crops_with_deadlines():
    s = f.new_save()
    out = f.deliveries(s, _people(), random.Random(2))
    assert len(out) == 2
    for d in out:
        assert 0 <= d["customer"] < 12 and 2 <= d["due"] <= f.HOURS
        assert set(d["order"]) <= {"radish", "peas", "carrot"}
        assert len(d["order"]) == 1 and 3 <= sum(d["order"].values()) <= 5
        assert d["pay"] == round(sum(f.CROPS[k].price * n for k, n in d["order"].items()) * f.DELIVERY_BONUS)
    assert [d["due"] for d in out] == sorted(d["due"] for d in out)


def test_a_known_farm_gets_more_and_mixed_deliveries():
    s = {**f.new_save(), "reputation": 30}
    assert len(f.deliveries(s, _people(), random.Random(5))) == 2  # more come with the wagon
    assert any(len(d["order"]) == 2 for d in f.deliveries(s, _people(), random.Random(9)))


def test_a_pet_carried_delivery_fits_the_day_check():
    s = f.new_save()
    f.check_day(s, 1, 0, {"radish": 4}, int(4 * 2 * f.DELIVERY_BONUS * (1 + f.PET_TIP)), 0)


def test_upgrades_change_what_the_farm_sends():
    s = {**f.new_save(), "upgrades": {"catalog": 2, "sprinkler": 3, "prices": 3, "pet_plots": 1, "robot": 2, "alarm": 1}}
    st = f.state(s)
    radish = next(c for c in st["crops"] if c["id"] == "radish")
    carrot = next(c for c in st["crops"] if c["id"] == "carrot")
    assert carrot["seed_cost"] == 2 and radish["seed_cost"] == 1  # half price, never free
    assert radish["grow"] == round(20 / 1.5) and radish["price"] == 2.6
    assert st["pet_plots"] == 2 and st["robot_plots"] == 2 and st["alarm"] is True
    assert f.all_plots(s) == 4 + 2 + 2


def test_plots_go_up_to_24():
    assert f.UPGRADES["plots"].values[-1] == f.MAX_PLOTS == 24


def test_fancy_customers_and_tips_raise_what_a_day_may_earn():
    plain = f.new_save()
    rich = {**plain, "upgrades": {"fancy": 1, "tips": 2, "prices": 3}}
    assert f.max_pay(rich) == pytest.approx(1.3 * 2 * 2)
    f.check_day(rich, 1, 0, {"radish": 2}, int(2 * 2 * f.max_pay(rich)), 0)
    with pytest.raises(f.FarmError):
        f.check_day(plain, 1, 0, {"radish": 2}, int(2 * 2 * f.max_pay(rich)), 0)


def test_the_wagon_brings_more_deliveries():
    s = {**f.new_save(), "upgrades": {"wagon": 2}}
    assert len(f.deliveries(s, _people(), random.Random(1))) == 4


def test_every_upgrade_opens_in_order_and_costs_more_each_level():
    for u in f.UPGRADES.values():
        assert len(u.values) == len(u.costs) + 1 == len(u.rep) + 1, u.id
        assert list(u.costs) == sorted(u.costs) and list(u.rep) == sorted(u.rep), u.id


def test_fairies_can_visit_the_stall_but_mermaids_cant():
    people = f.customers(set(), random.Random(3), count=3000)
    kinds = {p["species"] for p in people}
    assert "flower_fairy" in kinds and "mermaid" not in kinds
