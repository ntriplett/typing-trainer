"""Integration tests for Pet Supplies (app/pet_supplies.py, PLAN.md 11l):
treats, toys and fish food, playing in habitats for hearts, and color
potions in four tiers, new each day."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main, pet_supplies
from app import pet_genes as g

client = TestClient(main.app)


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


def give(coins):
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, coins, "test")


def add_pet(species, seed=1, home=None) -> int:
    with db.open_db(main.DB_PATH) as conn:
        pid = db.add_v3_pet(conn, 1, g.roll(species, None, None, seed), species.capitalize(), "shop")
        if home:
            db.update_v3_pet(conn, 1, pid, home=home)
        return pid


def test_the_supplies_department_is_open():
    shop = client.get("/api/pets/shop/supplies").json()
    assert shop["department"]["open"]
    kinds = {i["kind"] for i in shop["supplies"]["items"]}
    assert kinds == {"treat", "toy", "fish_food"}
    assert len(shop["supplies"]["potions"]["stock"]) == 8


def test_buying_treats_and_toys():
    give(300)
    r = client.post("/api/supplies/bone_biscuit").json()
    client.post("/api/supplies/bone_biscuit")
    r = client.post("/api/supplies/ball").json()
    items = {i["id"]: i for i in r["supplies"]["items"]}
    assert items["bone_biscuit"]["have"] == 2 and items["ball"]["have"] == 1 and r["coins"] == 190
    r = client.post("/api/supplies/ball")
    assert r.status_code == 400 and "never get used up" in r.json()["detail"]
    assert client.post("/api/supplies/nope").status_code == 400


def test_playing_gives_hearts_to_pets_that_like_it(clock):
    give(300)
    client.post("/api/pets/shop/habitats/meadow")
    dog = add_pet("dog", home="trail:0")
    cat = add_pet("cat", 2, home="trail:0")
    away = add_pet("dog", 3)
    assert client.post("/api/trail/0/play", json={"item": "bone_biscuit"}).status_code == 400  # none yet
    client.post("/api/supplies/bone_biscuit")
    client.post("/api/supplies/ball")
    shelf = client.get("/api/trail/0").json()["shelf"]
    assert {s["id"] for s in shelf} == {"bone_biscuit", "ball"}
    r = client.post("/api/trail/0/play", json={"item": "bone_biscuit"}).json()
    assert r["likers"] == {str(dog): 1} and r["used_up"] and [s["id"] for s in r["shelf"]] == ["ball"]
    r = client.post("/api/trail/0/play", json={"item": "ball"}).json()
    assert r["likers"] == {str(dog): 2, str(cat): 1} and not r["used_up"]
    for _ in range(5):
        r = client.post("/api/trail/0/play", json={"item": "ball"}).json()
    assert r["likers"][str(dog)] == pet_supplies.MAX_JOY  # hearts top out
    care = {p["id"]: p for p in client.get("/api/care").json()["pets"]}
    assert care[dog]["joy"] == 5 and care[away]["joy"] == 0
    clock["days"] = 2
    care = {p["id"]: p for p in client.get("/api/care").json()["pets"]}
    assert care[dog]["joy"] == 3  # a heart fewer each day nobody plays


def test_fish_food(clock):
    give(50)
    assert client.post("/api/aquarium/0/food", json={"item": "fish_flakes"}).status_code == 400
    client.post("/api/supplies/sinking_pellets")
    assert client.get("/api/aquarium/0").json()["food"][0]["id"] == "sinking_pellets"
    r = client.post("/api/aquarium/0/food", json={"item": "sinking_pellets"}).json()
    assert r["sinks"] and r["shelf"] == []
    client.post("/api/supplies/bone_biscuit")
    assert client.post("/api/aquarium/0/food", json={"item": "bone_biscuit"}).status_code == 400


def test_potions_tiers_and_daily_stock(clock):
    stock = client.get("/api/pets/shop/supplies").json()["supplies"]["potions"]["stock"]
    by_tier = {}
    for p in stock:
        by_tier.setdefault(p["tier"], []).append(p)
    assert {t: len(v) for t, v in by_tier.items()} == {"mystery": 2, "second": 2, "main": 2, "clear": 2}
    assert [p["price"] for p in stock] == [20, 20, 40, 40, 60, 60, 150, 150]
    shown = lambda p: [c is not None for c in p["shown"]]  # noqa: E731
    assert [shown(p) for p in stock[::2]] == [[False, False], [False, True], [True, False], [True, True]]
    assert client.get("/api/pets/shop/supplies").json()["supplies"]["potions"]["stock"] == stock  # the same all day
    clock["days"] = 1
    assert client.get("/api/pets/shop/supplies").json()["supplies"]["potions"]["stock"] != stock  # new tomorrow


def test_using_a_potion_repaints_the_whole_school(clock):
    give(1000)
    r = client.post("/api/supplies/potions/6").json()  # a clear one: both colors shown
    assert r["supplies"]["potions"]["stock"][6]["sold"] and r["coins"] == 850
    assert client.post("/api/supplies/potions/6").status_code == 400
    with db.open_db(main.DB_PATH) as conn:
        colors = pet_supplies.potion_stock(1, main._today())[6]["colors"]
    fish = add_pet("fish", 9)
    client.post(f"/api/care/{fish}/copy")
    potions = client.get(f"/api/care/{fish}/potions").json()["potions"]
    assert len(potions) == 1 and potions[0]["shown"][0]["id"] == colors[0]
    r = client.post(f"/api/care/{fish}/potion", json={"potion": potions[0]["id"]}).json()
    assert [c["id"] for c in r["potion"]["colors"]] == colors
    with db.open_db(main.DB_PATH) as conn:
        school = [p for p in db.list_v3_pets(conn, 1) if p["species"] == "fish"]
        assert len(school) == 2 and all(p["genes"]["coat"]["colors"][:2] == colors for p in school)
        assert set(colors) <= db.list_pet_color_unlocks(conn, 1)
    assert client.get(f"/api/care/{fish}/potions").json()["potions"] == []  # used up
    assert client.post(f"/api/care/{fish}/potion", json={"potion": potions[0]["id"]}).status_code == 400


def test_potions_only_fit_pets_that_can_wear_them():
    give(100)
    client.post("/api/supplies/potions/0")
    phoenix = add_pet("phoenix", 4)  # wears only its own fire colors
    assert client.get(f"/api/care/{phoenix}/potions").json()["potions"] == []


def test_play_words():
    words = client.get("/api/play/words").json()["words"]
    assert len(words) >= 3 and all(isinstance(w, str) and w for w in words)
