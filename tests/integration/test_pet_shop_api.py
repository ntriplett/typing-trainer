"""Integration tests for the Pet Shop API (app/pet_shop.py, PLAN.md 11h):
departments opening by rows learned, stock kept between visits and
restocked at midnight, buying with coins or the coupon, color unlocks,
and Save for me."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main, pet_genes
from app.activities.teach_curriculum import PAIR_ID
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
    """Noon local time on a fixed day; clock["days"] moves it."""
    state = {"days": 0}
    base = datetime(2026, 11, 2, 12, 0).astimezone()
    monkeypatch.setattr(main, "now", lambda: (base + timedelta(days=state["days"])).astimezone(UTC))
    return state


def teach(*pairs):
    with db.open_db(main.DB_PATH) as conn:
        for pair in pairs:
            db.mark_taught(conn, 1, lesson_ref(PAIR_ID, pair), "lesson")


def give_coins(n):
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, n, "test")


def depts():
    return {d["id"]: d for d in client.get("/api/pets/shop").json()["departments"]}


def owned():
    with db.open_db(main.DB_PATH) as conn:
        return db.list_v3_pets(conn, 1)


def test_a_new_player_can_shop_for_fish_and_habitats(clock):
    d = depts()
    assert [k for k, v in d.items() if v["open"]] == ["fish", "habitats", "aqua"]
    assert d["household"]["missing"] == "asdfghjkl;" and d["supplies"]["soon"]
    fish = client.get("/api/pets/shop/fish").json()
    assert len(fish["slots"]) == 16 and all(s["species"] == "fish" for s in fish["slots"])
    assert not fish["coupon"]
    closed = client.get("/api/pets/shop/household")
    assert closed.status_code == 403 and "learn" in closed.json()["detail"]
    assert client.get("/api/pets/shop/supplies").status_code == 403
    assert client.get("/api/pets/shop/nope").status_code == 400


def test_the_home_row_opens_household_and_special_orders_with_a_coupon(clock):
    teach(*HOME_PAIRS)
    d = depts()
    assert d["household"]["open"] and d["orders"]["open"] and not d["farm"]["open"]
    assert client.get("/api/pets/shop").json()["coupon"]
    household = client.get("/api/pets/shop/household").json()
    assert household["coupon"] and len(household["slots"]) == 16


def test_stock_is_kept_between_visits_and_restocks_at_midnight(clock):
    first = [s["genes"]["seed"] for s in client.get("/api/pets/shop/fish").json()["slots"]]
    assert [s["genes"]["seed"] for s in client.get("/api/pets/shop/fish").json()["slots"]] == first
    clock["days"] = 6  # everyone's 2-5 days are up
    later = [s["genes"]["seed"] for s in client.get("/api/pets/shop/fish").json()["slots"]]
    assert not set(first) & set(later)


def test_buying_pays_coins_unlocks_colors_and_empties_the_spot(clock):
    slot = client.get("/api/pets/shop/fish").json()["slots"][0]
    poor = client.post("/api/pets/shop/fish/0/buy", json={})
    assert poor.status_code == 400 and "more coins" in poor.json()["detail"]
    give_coins(5000)
    data = client.post("/api/pets/shop/fish/0/buy", json={}).json()
    assert data["coins"] == 5000 - slot["price"]
    assert data["bought"]["genes"]["seed"] == slot["genes"]["seed"] and data["bought"]["name"] == "Fish"
    assert data["slots"][0]["sold"]
    assert client.post("/api/pets/shop/fish/0/buy", json={}).status_code == 400  # gone already
    pets = owned()
    assert len(pets) == 1 and pets[0]["home"] is None and pets[0]["source"] == "shop"
    with db.open_db(main.DB_PATH) as conn:
        unlocked = db.list_pet_color_unlocks(conn, 1)
    assert {c for c in slot["genes"]["coat"]["colors"] if c} - set(pet_genes.METALS) <= unlocked
    clock["days"] = 1
    assert not client.get("/api/pets/shop/fish").json()["slots"][0]["sold"]  # a new pet tomorrow


def test_the_coupon_buys_one_household_pet_for_free(clock):
    teach(*HOME_PAIRS)
    client.get("/api/pets/shop/household")
    assert client.post("/api/pets/shop/fish/0/buy", json={"coupon": True}).status_code == 400  # household only
    data = client.post("/api/pets/shop/household/3/buy", json={"coupon": True}).json()
    assert data["coins"] == 0 and data["bought"]["species"] in ("dog", "cat", "bunny")
    assert not data["coupon"]
    again = client.post("/api/pets/shop/household/4/buy", json={"coupon": True})
    assert again.status_code == 400 and "coupon" in again.json()["detail"]


def test_save_for_me_keeps_one_pet_until_it_is_let_go(clock):
    teach(*HOME_PAIRS)
    client.get("/api/pets/shop/household")
    data = client.put("/api/pets/shop/save", json={"dept": "fish", "index": 5}).json()
    kept = data["slots"][5]["genes"]["seed"]
    assert data["slots"][5]["saved"] and data["saved"]["genes"]["seed"] == kept
    other = client.put("/api/pets/shop/save", json={"dept": "household", "index": 0})
    assert other.status_code == 400 and "already saving" in other.json()["detail"]
    clock["days"] = 30
    shop = client.get("/api/pets/shop").json()
    assert shop["saved"]["genes"]["seed"] == kept
    freed = client.delete("/api/pets/shop/save").json()
    assert freed["department"]["id"] == "fish" and freed["saved"] is None
    assert freed["slots"][5]["last_day"]  # one last day to change your mind
    assert client.delete("/api/pets/shop/save").status_code == 400
    clock["days"] = 31
    assert client.get("/api/pets/shop/fish").json()["slots"][5]["genes"]["seed"] != kept


def test_buying_the_saved_pet_frees_the_save(clock):
    give_coins(5000)
    client.put("/api/pets/shop/save", json={"dept": "fish", "index": 2})
    data = client.post("/api/pets/shop/fish/2/buy", json={}).json()
    assert data["saved"] is None
    assert client.put("/api/pets/shop/save", json={"dept": "fish", "index": 3}).status_code == 200


def test_shops_belong_to_one_player(clock):
    mine = [s["genes"]["seed"] for s in client.get("/api/pets/shop/fish").json()["slots"]]
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Other"})
    theirs = [s["genes"]["seed"] for s in client.get("/api/pets/shop/fish").json()["slots"]]
    assert not set(mine) & set(theirs)


# --- the Pets hub ------------------------------------------------------------------


def test_a_new_players_field_fills_with_the_same_visitors_all_day(clock):
    hub = client.get("/api/pets/hub").json()
    assert hub["pets"] == [] and len(hub["visitors"]) == 4
    assert all(v["species"] in ("dog", "cat", "bunny", "goat", "sheep", "llama", "fox") for v in hub["visitors"])
    assert all(v["genes"]["hex"][0].startswith("#") for v in hub["visitors"])
    again = client.get("/api/pets/hub").json()["visitors"]
    assert [v["genes"]["seed"] for v in again] == [v["genes"]["seed"] for v in hub["visitors"]]
    clock["days"] = 1
    tomorrow = client.get("/api/pets/hub").json()["visitors"]
    assert [v["genes"]["seed"] for v in tomorrow] != [v["genes"]["seed"] for v in hub["visitors"]]


def test_your_land_pets_take_the_visitors_places_but_fish_dont(clock):
    teach(*HOME_PAIRS)
    give_coins(50000)
    client.post("/api/pets/shop/fish/0/buy", json={})
    hub = client.get("/api/pets/hub").json()
    assert len(hub["pets"]) == 1 and len(hub["visitors"]) == 4  # fish wait for the Aquarium
    client.post("/api/pets/shop/household/0/buy", json={})
    hub = client.get("/api/pets/hub").json()
    assert len(hub["pets"]) == 2 and len(hub["visitors"]) == 3
    assert hub["pets"][1]["name"] in ("Dog", "Cat", "Bunny") and hub["pets"][1]["growth"] == 0


def test_the_hub_tells_the_shop_door_about_coupons_and_orders(clock):
    assert not client.get("/api/pets/hub").json()["coupon"]
    teach(*HOME_PAIRS)
    hub = client.get("/api/pets/hub").json()
    assert hub["coupon"] and hub["unlocks"]["pet_coupon"] and hub["order"] is None
    give_coins(1000)
    client.post("/api/pets/shop/orders", json={"species": "cat", "primary": "black"})
    clock["days"] = 1
    assert client.get("/api/pets/hub").json()["order"]["status"] == "ready"
