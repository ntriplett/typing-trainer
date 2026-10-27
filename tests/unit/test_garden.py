"""Unit tests for the garden (app/garden.py): planting seeds, watering
ripens one veggie per plant, picking, the 36h wither and the basket."""

import random
from datetime import UTC, datetime, timedelta

import pytest

from app import db, garden

T0 = datetime(2026, 10, 1, 16, 0, tzinfo=UTC)
DAY = timedelta(hours=24)


@pytest.fixture()
def conn():
    with db.open_db(":memory:") as c:
        yield c


@pytest.fixture()
def learner_id(conn):
    return db.create_learner(conn, "Sam").id


def _seed(conn, learner_id, n=1):
    db.add_seeds(conn, learner_id, n, "test")


def test_planting_spends_a_seed_and_grows_babies(conn, learner_id):
    _seed(conn, learner_id)
    planted = garden.plant(conn, learner_id, 3, T0, rng=random.Random(1))
    assert planted["kind"] in garden.VEGGIES
    status = garden.status(conn, learner_id, T0)
    assert status["seeds"] == 0
    spot = status["spots"][3]
    assert spot["babies"] == 5 and spot["ready"] == 0
    assert status["growing"] == 1 and len(status["spots"]) == garden.SPOTS


def test_planting_needs_a_seed_and_an_empty_spot(conn, learner_id):
    with pytest.raises(garden.GardenError, match="need a seed"):
        garden.plant(conn, learner_id, 0, T0)
    _seed(conn, learner_id, 2)
    garden.plant(conn, learner_id, 0, T0)
    with pytest.raises(garden.GardenError, match="already growing"):
        garden.plant(conn, learner_id, 0, T0)
    with pytest.raises(garden.GardenError):
        garden.plant(conn, learner_id, garden.SPOTS, T0)
    assert db.get_seed_balance(conn, learner_id) == 1


def test_watering_ripens_one_veggie_on_each_plant(conn, learner_id):
    _seed(conn, learner_id, 2)
    garden.plant(conn, learner_id, 0, T0)
    garden.plant(conn, learner_id, 1, T0)
    ripened = garden.water(conn, learner_id, T0 + DAY)
    assert [r["slot"] for r in ripened] == [0, 1]
    spot = garden.status(conn, learner_id, T0 + DAY)["spots"][0]
    assert spot["babies"] == 4 and spot["ready"] == 1


def test_daily_play_ramps_up_to_five_veggies_a_day(conn, learner_id):
    """Earn a seed and plant it each day: 0, 1, 2, 3, 4, 5, 5, 5 veggies."""
    per_day = []
    for day in range(8):
        when = T0 + day * DAY
        ripened = garden.water(conn, learner_id, when)
        per_day.append(len(ripened))
        for spot in garden.status(conn, learner_id, when)["spots"]:
            if spot and spot["ready"]:
                garden.pick(conn, learner_id, spot["slot"], when)
        _seed(conn, learner_id)
        empty = garden.status(conn, learner_id, when)["spots"].index(None)
        garden.plant(conn, learner_id, empty, when)
    assert per_day == [0, 1, 2, 3, 4, 5, 5, 5]
    assert sum(db.get_veggies(conn, learner_id).values()) == sum(per_day)


def test_picking_takes_ripe_veggies_and_a_finished_plant_frees_its_spot(conn, learner_id):
    _seed(conn, learner_id)
    garden.plant(conn, learner_id, 2, T0)
    kind = garden.status(conn, learner_id, T0)["spots"][2]["kind"]
    with pytest.raises(garden.GardenError, match="Nothing is ripe"):
        garden.pick(conn, learner_id, 2, T0)
    garden.water(conn, learner_id, T0 + DAY)
    garden.water(conn, learner_id, T0 + 2 * DAY)
    assert garden.pick(conn, learner_id, 2, T0 + 2 * DAY)["count"] == 2
    assert garden.status(conn, learner_id, T0 + 2 * DAY)["spots"][2]["ready"] == 0
    for d in range(3, 6):
        garden.water(conn, learner_id, T0 + d * DAY)
    assert garden.status(conn, learner_id, T0 + 5 * DAY)["spots"][2]["babies"] == 0
    assert garden.pick(conn, learner_id, 2, T0 + 5 * DAY)["count"] == 3
    assert garden.status(conn, learner_id, T0 + 5 * DAY)["spots"][2] is None
    assert db.get_veggies(conn, learner_id) == {kind: 5}


def test_unpicked_veggies_just_wait(conn, learner_id):
    _seed(conn, learner_id)
    garden.plant(conn, learner_id, 0, T0)
    for d in range(1, 9):
        garden.water(conn, learner_id, T0 + d * DAY)
    spot = garden.status(conn, learner_id, T0 + 8 * DAY)["spots"][0]
    assert spot["ready"] == 5 and spot["babies"] == 0


def test_36_hours_without_water_withers_plants_into_the_basket(conn, learner_id):
    _seed(conn, learner_id, 2)
    garden.plant(conn, learner_id, 0, T0)
    garden.plant(conn, learner_id, 1, T0)
    garden.water(conn, learner_id, T0 + DAY)
    garden.water(conn, learner_id, T0 + 2 * DAY)
    garden.pick(conn, learner_id, 1, T0 + 2 * DAY)
    kind = garden.status(conn, learner_id, T0 + 2 * DAY)["spots"][0]["kind"]

    almost = T0 + 2 * DAY + garden.WITHER_AFTER
    assert garden.status(conn, learner_id, almost)["growing"] == 2
    late = almost + timedelta(minutes=1)
    status = garden.status(conn, learner_id, late)
    assert status["growing"] == 0
    assert status["basket"] == {kind: 2}  # spot 1's veggies were already picked


def test_watering_after_a_long_gap_withers_first(conn, learner_id):
    _seed(conn, learner_id)
    garden.plant(conn, learner_id, 0, T0)
    assert garden.water(conn, learner_id, T0 + 2 * DAY) == []
    assert garden.status(conn, learner_id, T0 + 2 * DAY)["growing"] == 0


def test_twelve_hour_rhythm_keeps_plants_alive(conn, learner_id):
    _seed(conn, learner_id)
    garden.plant(conn, learner_id, 0, T0)
    for i in range(1, 4):
        garden.water(conn, learner_id, T0 + i * timedelta(hours=30))
    assert garden.status(conn, learner_id, T0 + timedelta(hours=90))["spots"][0]["ready"] == 3


def test_collecting_the_basket(conn, learner_id):
    with pytest.raises(garden.GardenError, match="empty"):
        garden.collect_basket(conn, learner_id, T0)
    db.add_to_basket(conn, learner_id, "corn", 2)
    db.add_to_basket(conn, learner_id, "corn", 1)
    assert garden.collect_basket(conn, learner_id, T0) == {"corn": 3}
    assert db.get_veggies(conn, learner_id) == {"corn": 3}
    assert garden.status(conn, learner_id, T0)["basket"] == {}


def test_gardens_are_per_learner(conn, learner_id):
    other = db.create_learner(conn, "Ada").id
    _seed(conn, learner_id)
    garden.plant(conn, learner_id, 0, T0)
    garden.water(conn, other, T0 + DAY)
    assert garden.status(conn, other, T0)["growing"] == 0
    assert garden.status(conn, learner_id, T0 + DAY)["spots"][0]["ready"] == 0
