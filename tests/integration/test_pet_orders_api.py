"""Integration tests for Special Orders (app/pet_shop.py, PLAN.md 11h): pay
half the species' base price, four pets in your colors arrive tomorrow and
wait three days; a new order sends any waiting ones home."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main
from app.activities.teach_curriculum import CAPS_GROUPS, CAPS_ID, PAIR_ID
from app.brain import lesson_ref

client = TestClient(main.app)
HOME_PAIRS = ("fj", "dk", "sl", "a;", "gh")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    lessons._LESSONS.clear()
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    yield


@pytest.fixture
def clock(monkeypatch):
    state = {"days": 0}
    base = datetime(2026, 11, 2, 12, 0).astimezone()
    monkeypatch.setattr(main, "now", lambda: (base + timedelta(days=state["days"])).astimezone(UTC))
    return state


def teach_refs(*refs):
    with db.open_db(main.DB_PATH) as conn:
        for ref in refs:
            db.mark_taught(conn, 1, ref, "lesson")


def home_row():
    teach_refs(*(lesson_ref(PAIR_ID, p) for p in HOME_PAIRS))


def give_coins(n):
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, n, "test")


def orders():
    return client.get("/api/pets/shop/orders").json()


def order(**body):
    return client.post("/api/pets/shop/orders", json=body)


def test_special_orders_open_with_the_home_row(clock):
    assert client.get("/api/pets/shop/orders").status_code == 403
    assert order(species="fish", primary="orange").status_code == 403
    home_row()
    data = orders()
    assert data["order"] is None and data["slots"] == [] and not data["pick_secondary"]
    choices = {c["species"]: c for c in data["choices"]}
    assert set(choices) == {"fish", "dog", "cat", "bunny"}  # open departments only
    assert choices["cat"]["fee"] == 400
    assert {c["id"] for c in choices["cat"]["primaries"]} == {"orange", "ash", "black"}  # starters to begin with


def test_an_order_costs_half_the_base_and_its_pets_arrive_tomorrow(clock):
    home_row()
    poor = order(species="cat", primary="black")
    assert poor.status_code == 400 and "more coins" in poor.json()["detail"]
    give_coins(1000)
    data = order(species="cat", primary="black").json()
    assert data["coins"] == 600
    assert data["order"]["status"] == "waiting" and data["slots"] == []
    clock["days"] = 1
    data = orders()
    assert data["order"]["status"] == "ready" and data["order"]["days_left"] == 3
    assert len(data["slots"]) == 4
    assert all(s["species"] == "cat" and s["genes"]["coat"]["colors"][0] == "black" for s in data["slots"])
    clock["days"] = 3
    assert all(s["last_day"] for s in orders()["slots"])
    clock["days"] = 4
    assert orders()["order"] is None and orders()["slots"] == []


def test_buy_any_number_of_an_orders_pets(clock):
    home_row()
    give_coins(20000)
    order(species="dog", primary="golden")
    clock["days"] = 1
    for i in (0, 2):
        data = client.post(f"/api/pets/shop/orders/{i}/buy", json={}).json()
        assert data["bought"]["source"] == "order"
    slots = {s["index"]: s for s in data["slots"]}
    assert slots[0]["sold"] and slots[2]["sold"] and not slots[1]["sold"]
    clock["days"] = 2  # bought spots stay "Adopted!" while the others still wait
    assert [s["sold"] for s in orders()["slots"]] == [True, False, True, False]
    assert client.put("/api/pets/shop/save", json={"dept": "orders", "index": 1}).status_code == 400


def test_a_new_order_sends_the_waiting_pets_home(clock):
    home_row()
    give_coins(2000)
    order(species="cat", primary="black")
    clock["days"] = 1
    first = {s["genes"]["seed"] for s in orders()["slots"]}
    data = order(species="bunny", primary="snow").json()
    assert data["slots"] == [] and data["order"]["species"] == "bunny"
    clock["days"] = 2
    second = orders()["slots"]
    assert all(s["species"] == "bunny" for s in second) and not first & {s["genes"]["seed"] for s in second}


def test_orders_only_use_unlocked_colors_and_open_species(clock):
    home_row()
    give_coins(20000)
    assert "unlocked" in order(species="cat", primary="lilac").json()["detail"]
    assert order(species="goat", primary="snow").status_code == 400  # farm isn't open
    assert order(species="cat", primary="orange", secondary="black").status_code == 400  # capitals first
    with db.open_db(main.DB_PATH) as conn:
        db.unlock_pet_colors(conn, 1, ["lilac"])
    assert order(species="cat", primary="lilac").status_code == 200


def test_capitals_open_picking_the_second_color(clock):
    home_row()
    teach_refs(*(lesson_ref(CAPS_ID, g) for g in CAPS_GROUPS))
    give_coins(1000)
    assert orders()["pick_secondary"]
    order(species="cat", primary="orange", secondary="black")
    clock["days"] = 1
    assert all(s["genes"]["coat"]["colors"][:2] == ["orange", "black"] for s in orders()["slots"])


def test_the_preview_rolls_a_sample_and_saves_nothing(clock):
    home_row()
    r = client.get("/api/pets/shop/orders/preview", params={"species": "cat", "primary": "ash"})
    assert r.status_code == 200 and r.json()["pet"]["coat"]["colors"][0] == "ash"
    assert r.json()["pet"]["hex"][0].startswith("#")
    bad = client.get("/api/pets/shop/orders/preview", params={"species": "cat", "primary": "lilac"})
    assert bad.status_code == 400
    assert orders()["order"] is None
