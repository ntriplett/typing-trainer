"""Integration tests for aquariums (app/aquarium.py, PLAN.md 11k): the
starter tank, buying tanks and supplies, decorating (place, move, layers,
flip, storage), looks, and fish moving in."""

import pytest
from fastapi.testclient import TestClient

from app import aquarium, db, lessons, main
from app import pet_genes as g

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    lessons._LESSONS.clear()
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    yield


def give(coins):
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, coins, "test")


def add_pet(species="fish", seed=1) -> int:
    with db.open_db(main.DB_PATH) as conn:
        return db.add_v3_pet(conn, 1, g.roll(species, None, None, seed), species.capitalize(), "shop")


def test_everyone_starts_with_one_empty_basic_tank():
    hall = client.get("/api/aquarium").json()
    assert len(hall["spots"]) == 10 and hall["spots"][1:] == [None] * 9
    tank = hall["spots"][0]
    assert tank["name"] == "Tank 1" and tank["background"] == "bg_blue" and tank["substrate"] == "sand"
    assert tank["pieces"] == [] and tank["fish"] == [] and tank["capacity"] == 10
    assert hall["size"] == {"w": 160, "h": 70, "substrate": 8}


def test_buying_a_tank_and_supplies():
    r = client.post("/api/aquarium-shop/tank")
    assert r.status_code == 400 and "400 more coins" in r.json()["detail"]
    give(1000)
    r = client.post("/api/aquarium-shop/tank").json()
    assert r["bought"] == {"spot": 1, "name": "Tank 2"} and r["coins"] == 600 and r["tanks"] == 2
    r = client.post("/api/aquarium-shop/grass").json()
    assert r["coins"] == 590 and next(i for i in r["items"] if i["id"] == "grass")["owned"] == 1
    client.post("/api/aquarium-shop/grass")
    r = client.post("/api/aquarium-shop/bg_night").json()
    assert next(i for i in r["items"] if i["id"] == "bg_night")["owned"] is True and r["coins"] == 540
    assert client.post("/api/aquarium-shop/bg_night").status_code == 400  # already yours
    assert client.post("/api/aquarium-shop/bg_blue").status_code == 400  # a starter look
    assert client.post("/api/aquarium-shop/unicorn").status_code == 400


def test_decorating_a_tank():
    give(500)
    grass = client.post("/api/aquarium-shop/grass").json()["bought"]["piece"]
    wood = client.post("/api/aquarium-shop/driftwood").json()["bought"]["piece"]
    state = client.get("/api/aquarium/0").json()
    assert [p["id"] for p in state["storage"]] == [grass, wood]
    state = client.post("/api/aquarium/0/pieces", json={"piece": wood}).json()
    placed = state["tank"]["pieces"][0]
    assert placed["id"] == wood and placed["x"] == 55 and placed["y"] == 66 and placed["layer"] == "middle"
    state = client.put(f"/api/aquarium/0/pieces/{wood}", json={"x": 500, "y": 2, "layer": "front", "flip": True}).json()
    placed = state["tank"]["pieces"][0]
    assert (placed["x"], placed["y"], placed["layer"], placed["flip"]) == (110, 26, "front", True)  # kept inside
    assert client.put(f"/api/aquarium/0/pieces/{wood}", json={"x": 1, "y": 60, "layer": "top"}).status_code == 400
    assert client.put(f"/api/aquarium/0/pieces/{grass}", json={"x": 1, "y": 60}).status_code == 400  # in storage
    state = client.delete(f"/api/aquarium/0/pieces/{wood}").json()
    assert state["tank"]["pieces"] == [] and len(state["storage"]) == 2
    assert client.post("/api/aquarium/4/pieces", json={"piece": grass}).status_code == 400  # no tank there


def test_looks_must_be_owned():
    give(100)
    assert client.put("/api/aquarium/0/look", json={"background": "bg_coral"}).status_code == 400
    assert client.put("/api/aquarium/0/look", json={"background": "sand"}).status_code == 400
    client.post("/api/aquarium-shop/bg_coral")
    client.post("/api/aquarium-shop/gravel_pink")
    tank = client.put("/api/aquarium/0/look", json={"background": "bg_coral", "substrate": "gravel_pink"}).json()["tank"]
    assert (tank["background"], tank["substrate"]) == ("bg_coral", "gravel_pink")
    assert client.put("/api/aquarium/0/name", json={"name": "  Reef   Tank "}).json()["tank"]["name"] == "Reef Tank"


def test_fish_move_in_up_to_ten():
    fish = [add_pet(seed=s) for s in range(11)]
    dog = add_pet("dog")
    for f in fish[:10]:
        assert client.put(f"/api/aquarium/0/fish/{f}").status_code == 200
    r = client.put(f"/api/aquarium/0/fish/{fish[10]}")
    assert r.status_code == 400 and "full" in r.json()["detail"]
    assert client.put(f"/api/aquarium/0/fish/{dog}").status_code == 400
    state = client.get("/api/aquarium/0").json()
    assert len(state["tank"]["fish"]) == 10 and [f["id"] for f in state["waiting_fish"]] == [fish[10]]
    state = client.delete(f"/api/aquarium/0/fish/{fish[0]}").json()
    assert len(state["tank"]["fish"]) == 9
    care = client.put(f"/api/care/{fish[10]}/tank", json={"spot": 0}).json()
    pet = next(p for p in care["pets"] if p["id"] == fish[10])
    assert pet["tank"] == 0 and care["tanks"][0]["count"] == 10


def test_every_item_is_well_formed():
    for item in aquarium.CATALOG.values():
        assert item.kind in aquarium.LOOK_KINDS + aquarium.PIECE_KINDS
        if item.kind in aquarium.PIECE_KINDS:
            assert 10 <= item.price <= 100 and item.w > 0 and item.h > 0 and item.layer in aquarium.LAYERS
            assert set(item.sees) <= {"hide", "explore", "through", "bubbles"}


def test_schools_of_fish():
    give(5000)
    head = add_pet(seed=8)
    dog = add_pet("dog")
    care = client.get("/api/care").json()
    fish = next(p for p in care["pets"] if p["id"] == head)
    assert fish["school"] == 1 and 5 <= fish["copy_price"] <= 60  # a fifth of a fish's price
    assert client.post(f"/api/care/{dog}/copy").status_code == 400
    for _ in range(3):
        r = client.post(f"/api/care/{head}/copy").json()
    fish = next(p for p in r["pets"] if p["id"] == head)
    assert fish["school"] == 4 and len(r["pets"]) == 2  # one entry in the book
    assert r["coins"] == 5000 - 3 * fish["copy_price"]
    client.put(f"/api/care/{head}/name", json={"name": "Neon"})
    state = client.get("/api/aquarium/0").json()
    assert [f["name"] for f in state["waiting_fish"]] == ["Neon"] * 4  # each copy can swim on its own
    care = client.put(f"/api/care/{head}/tank", json={"spot": 0}).json()  # the whole school moves in
    assert care["tanks"][0]["count"] == 4 and next(p for p in care["pets"] if p["id"] == head)["school_tanks"] == [0]
    copy = client.get("/api/aquarium/0").json()["tank"]["fish"][1]["id"]
    client.delete(f"/api/aquarium/0/fish/{copy}")
    assert len(client.get("/api/aquarium/0").json()["tank"]["fish"]) == 3
    with db.open_db(main.DB_PATH) as conn:
        for k in range(6):
            pid = db.add_v3_pet(conn, 1, g.roll("fish", None, None, 50 + k), "X", "shop")
            db.update_v3_pet(conn, 1, pid, home="tank:0")
    r = client.put(f"/api/care/{head}/tank", json={"spot": 0})  # 9 in there: no room for the school's last
    assert r.status_code == 200  # the 3 already in stay; the 4th fits
    r = client.post(f"/api/care/{head}/copy")
    r = client.put(f"/api/care/{head}/tank", json={"spot": 0})
    assert r.status_code == 400 and "room for" in r.json()["detail"]


def test_driftwood_and_rocks_turn():
    give(500)
    wood = client.post("/api/aquarium-shop/spiderwood").json()["bought"]["piece"]
    grass = client.post("/api/aquarium-shop/grass").json()["bought"]["piece"]
    client.post("/api/aquarium/0/pieces", json={"piece": wood})
    client.post("/api/aquarium/0/pieces", json={"piece": grass})
    state = client.put(f"/api/aquarium/0/pieces/{wood}", json={"x": 200, "y": 70, "rot": 90}).json()
    placed = next(p for p in state["tank"]["pieces"] if p["id"] == wood)
    assert placed["rot"] == 90 and placed["x"] == 160 - 52  # turned: 52 wide now
    assert client.put(f"/api/aquarium/0/pieces/{wood}", json={"x": 0, "y": 70, "rot": 45}).status_code == 400
    assert client.put(f"/api/aquarium/0/pieces/{grass}", json={"x": 0, "y": 70, "rot": 90}).status_code == 400
    assert client.put(f"/api/aquarium/0/pieces/{grass}", json={"x": 0, "y": 70, "rot": 0}).status_code == 200
