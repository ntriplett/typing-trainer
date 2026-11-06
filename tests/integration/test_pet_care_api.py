"""Integration tests for the Pet Care Center and the Trailhead (app/pet_care.py,
PLAN.md 11i): renaming, feeding garden veggies once a day, bringing pets
along, habitats bought in the Pet Shop, homes, and the hub field."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main, pet_care
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


def add_pet(species="dog", seed=7, growth=0) -> int:
    with db.open_db(main.DB_PATH) as conn:
        pid = db.add_v3_pet(conn, 1, g.roll(species, None, None, seed), species.capitalize(), "shop")
        db.update_v3_pet(conn, 1, pid, growth=growth)
        return pid


def give(coins=0, **veggies):
    with db.open_db(main.DB_PATH) as conn:
        if coins:
            db.add_coins(conn, 1, coins, "test")
        for kind, n in veggies.items():
            db.add_veggies(conn, 1, kind, n, "test")


def pet(state, pid):
    return next(p for p in state["pets"] if p["id"] == pid)


def test_the_book_lists_pets_with_their_details():
    pid = add_pet()
    care = client.get("/api/care").json()
    p = pet(care, pid)
    assert p["name"] == "Dog" and p["growth"] == 0 and p["spot"] is None and p["along"] is None
    assert "playful" in p["genes"]["personality"] and p["genes"]["hex"][0].startswith("#")
    assert p["rarity"] >= 1 and care["max_along"] == 2 and "coins" in care


def test_rename():
    pid = add_pet()
    assert pet(client.put(f"/api/care/{pid}/name", json={"name": "  Sir   Barks "}).json(), pid)["name"] == "Sir Barks"
    assert client.put(f"/api/care/{pid}/name", json={"name": " "}).status_code == 400
    assert client.put(f"/api/care/{pid}/name", json={"name": "x" * 17}).status_code == 400
    assert client.put("/api/care/999/name", json={"name": "Ghost"}).status_code == 400


def test_feeding_once_a_day_and_favorites_count_double(clock):
    pid = add_pet(seed=3)
    favorite = pet(client.get("/api/care").json(), pid)["genes"]["personality"]["favorite"]
    other = next(v for v in g.VEGGIES if v != favorite)
    r = client.post(f"/api/care/{pid}/feed", json={"veggie": other})
    assert r.status_code == 400 and "garden" in r.json()["detail"]
    give(**{other: 1, favorite: 1})
    r = client.post(f"/api/care/{pid}/feed", json={"veggie": other}).json()
    assert r["fed"] == {"growth": 1, "favorite": False} and other not in r["veggies"]
    assert pet(r, pid)["fed_today"]
    r = client.post(f"/api/care/{pid}/feed", json={"veggie": favorite})
    assert r.status_code == 400 and "tomorrow" in r.json()["detail"]
    clock["days"] = 1
    r = client.post(f"/api/care/{pid}/feed", json={"veggie": favorite}).json()
    assert r["fed"] == {"growth": 3, "favorite": True}


def test_grown_pets_dont_eat():
    pid = add_pet(growth=10)
    give(carrot=1)
    r = client.post(f"/api/care/{pid}/feed", json={"veggie": "carrot"})
    assert r.status_code == 400 and "grown up" in r.json()["detail"]
    assert client.get("/api/care").json()["veggies"] == {"carrot": 1}


def test_bring_along_two_at_most_and_never_fish():
    a, b, c = add_pet(seed=1), add_pet("cat", seed=2), add_pet("bunny", seed=3)
    client.put(f"/api/care/{a}/along", json={"slot": 1})
    client.put(f"/api/care/{b}/along", json={"slot": 2})
    state = client.put(f"/api/care/{c}/along", json={"slot": 1}).json()
    assert [pet(state, x)["along"] for x in (a, b, c)] == [None, 2, 1]
    assert client.put(f"/api/care/{a}/along", json={"slot": 3}).status_code == 400
    state = client.put(f"/api/care/{b}/along", json={"slot": None}).json()
    assert pet(state, b)["along"] is None
    fish = add_pet("fish", seed=4)
    assert client.put(f"/api/care/{fish}/along", json={"slot": 1}).status_code == 400


def test_pets_along_ride_with_the_avatar():
    a, b = add_pet(seed=1), add_pet("cat", seed=2)
    client.put(f"/api/care/{a}/along", json={"slot": 2})
    client.put(f"/api/care/{b}/along", json={"slot": 1})
    along = client.get("/api/me").json()["avatar"]["pets"]
    assert [(p["id"], p["slot"]) for p in along] == [(b, 1), (a, 2)]
    assert along[0]["genes"]["hex"][0].startswith("#") and along[0]["name"] == "Cat"


def test_the_first_meadow_is_free_then_1500():
    shop = client.get("/api/pets/shop/habitats").json()
    assert shop["department"]["open"] and shop["slots"] == []
    meadow = shop["habitats"]["kinds"][0]
    assert meadow == {"id": "meadow", "name": "Meadow", "tier": "everyday", "price": 0, "open": True}
    r = client.post("/api/pets/shop/habitats/meadow").json()
    assert r["bought"] == {"spot": 0, "kind": "meadow", "name": "Meadow", "price": 0}
    assert r["habitats"]["kinds"][0]["price"] == 1500
    r = client.post("/api/pets/shop/habitats/meadow")
    assert r.status_code == 400 and "1,500 more coins" in r.json()["detail"]
    give(coins=1600)
    r = client.post("/api/pets/shop/habitats/meadow").json()
    assert r["bought"]["name"] == "Meadow 2" and r["bought"]["spot"] == 1 and r["coins"] == 100
    assert client.post("/api/pets/shop/habitats/castle").status_code == 400


def test_the_trail_has_ten_spots():
    trail = client.get("/api/trail").json()["spots"]
    assert trail == [None] * 10
    client.post("/api/pets/shop/habitats/meadow")
    trail = client.get("/api/trail").json()["spots"]
    assert trail[0]["name"] == "Meadow" and trail[0]["pets"] == [] and trail[1] is None
    assert client.get("/api/trail/0").json()["habitat"]["kind"] == "meadow"
    assert client.get("/api/trail/1").status_code == 404


def test_a_full_trail_grows_another_ten_spots():
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, 100_000, "test")
    for _ in range(9):
        assert client.post("/api/pets/shop/habitats/meadow").status_code == 200
    assert len(client.get("/api/trail").json()["spots"]) == 10
    assert client.get("/api/pets/shop/habitats").json()["habitats"]["spots"] == 10
    assert client.post("/api/pets/shop/habitats/cherry").status_code == 200  # the 10th fills the first section
    trail = client.get("/api/trail").json()
    assert len(trail["spots"]) == 20 and trail["section"] == 10 and trail["spots"][10] is None
    bought = client.post("/api/pets/shop/habitats/forest").json()["bought"]
    assert bought["spot"] == 10
    assert client.get("/api/trail/10").json()["habitat"]["kind"] == "forest"


def test_homes_hold_six_land_pets():
    client.post("/api/pets/shop/habitats/meadow")
    pets = [add_pet(seed=s) for s in range(7)]
    assert client.put(f"/api/care/{pets[0]}/home", json={"spot": 1}).status_code == 400
    for p in pets[:6]:
        assert client.put(f"/api/care/{p}/home", json={"spot": 0}).status_code == 200
    r = client.put(f"/api/care/{pets[6]}/home", json={"spot": 0})
    assert r.status_code == 400 and "full" in r.json()["detail"]
    care = client.put(f"/api/care/{pets[0]}/home", json={"spot": None}).json()
    assert pet(care, pets[0])["spot"] is None and care["habitats"][0]["count"] == 5
    assert len(client.get("/api/trail/0").json()["habitat"]["pets"]) == 5
    fish = add_pet("fish", seed=9)
    assert client.put(f"/api/care/{fish}/home", json={"spot": 0}).status_code == 400


def test_the_hub_field_shows_pets_along_then_the_newest_four_waiting():
    client.post("/api/pets/shop/habitats/meadow")
    pets = [add_pet(seed=s) for s in range(8)]
    add_pet("fish", seed=20)
    client.put(f"/api/care/{pets[0]}/along", json={"slot": 2})
    client.put(f"/api/care/{pets[1]}/along", json={"slot": 1})
    client.put(f"/api/care/{pets[7]}/home", json={"spot": 0})
    hub = client.get("/api/pets/hub").json()
    assert [p["id"] for p in hub["field"]] == [pets[1], pets[0], pets[6], pets[5], pets[4], pets[3]]
    assert hub["visitors"] == [] and len(hub["pets"]) == 9


def test_pet_care_rules_constants():
    assert pet_care.HABITAT_PETS == 6 and pet_care.TRAIL_SPOTS == 10 and pet_care.MAX_GROWTH == 10


def test_tiers_price_habitats_and_only_everyday_ones_start_free():
    kinds = {k["id"]: k for k in client.get("/api/pets/shop/habitats").json()["habitats"]["kinds"]}
    assert kinds["forest"]["price"] == 0 and kinds["mountain"]["price"] == 0
    with db.open_db(main.DB_PATH) as conn:
        assert pet_care.habitat_price(conn, 1, "forest") == 0
    pet_care.HABITAT_KINDS["test_cozy"] = pet_care.HabitatKind("test_cozy", "Test Nook", "cozy")
    pet_care.HABITAT_KINDS["test_magic"] = pet_care.HabitatKind("test_magic", "Test Cave", "magical")
    try:
        kinds = {k["id"]: k for k in client.get("/api/pets/shop/habitats").json()["habitats"]["kinds"]}
        assert kinds["test_cozy"]["price"] == 2500 and kinds["test_magic"]["price"] == 5000
        assert not kinds["test_magic"]["open"]
        give(coins=10_000)
        r = client.post("/api/pets/shop/habitats/test_magic")
        assert r.status_code == 400 and "Mythical" in r.json()["detail"]
        assert client.post("/api/pets/shop/habitats/test_cozy").json()["coins"] == 7500  # never free
    finally:
        del pet_care.HABITAT_KINDS["test_cozy"], pet_care.HABITAT_KINDS["test_magic"]


def test_the_same_habitat_twice():
    give(coins=5000)
    client.post("/api/pets/shop/habitats/forest")
    r = client.post("/api/pets/shop/habitats/forest").json()
    assert r["bought"]["name"] == "Forest 2" and r["bought"]["price"] == 1500


def test_the_lab_adopts_the_pet_as_shown_at_any_growth():
    rolled = g.roll("dog", None, None, 7)
    breed = g.BREEDS["dog"][-1]
    shown = g.resolve({**rolled, "shape": {**rolled["shape"], "breed": breed}})
    r = client.post("/api/pet-lab/adopt", json={"genes": shown, "growth": 2})
    assert r.status_code == 200 and r.json()["name"] == "Dog"
    pet = next(p for p in client.get("/api/care").json()["pets"] if p["id"] == r.json()["id"])
    assert (pet["species"], pet["growth"], pet["genes"]["shape"]["breed"], pet["spot"]) == ("dog", 2, breed, None)
    assert pet["source"] == "lab"


def test_the_lab_only_adopts_real_pets():
    good = g.roll("dog", None, None, 7)
    assert client.post("/api/pet-lab/adopt", json={"genes": {**good, "species": "gryphon"}, "growth": 2}).status_code == 400
    assert client.post("/api/pet-lab/adopt", json={"genes": {"species": "dog"}, "growth": 2}).status_code == 400
    assert client.post("/api/pet-lab/adopt", json={"genes": good, "growth": 11}).status_code == 422
    client.cookies.clear()
    assert client.post("/api/pet-lab/adopt", json={"genes": good, "growth": 2}).status_code == 401


def _adopt(species, growth=6):
    genes = g.roll(species, None, None, 7)
    return client.post("/api/pet-lab/adopt", json={"genes": genes, "growth": growth}).json()["id"]


def test_mermaids_only_move_into_habitats_with_enough_water():
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, 100000, "test")
    assert client.post("/api/pets/shop/habitats/meadow").status_code == 200
    assert client.post("/api/pets/shop/habitats/pond").status_code == 200
    for growth in (0, 2, 6):
        mermaid = _adopt("mermaid", growth)
        dry = client.put(f"/api/care/{mermaid}/home", json={"spot": 0})
        assert dry.status_code == 400 and "water" in dry.json()["detail"]
        assert client.put(f"/api/care/{mermaid}/home", json={"spot": 1}).status_code == 200
        assert client.put(f"/api/care/{mermaid}/home", json={"spot": None}).status_code == 200
    assert client.put(f"/api/care/{_adopt('dog')}/home", json={"spot": 0}).status_code == 200  # others go anywhere
    care = client.get("/api/care").json()
    assert {h["kind"]: h["water"] for h in care["habitats"]} == {"meadow": False, "pond": True}
    assert {p["species"]: p["swimmer"] for p in care["pets"]} == {"mermaid": True, "dog": False}


def test_mermaids_can_still_come_along():
    mermaid = _adopt("mermaid")
    assert client.put(f"/api/care/{mermaid}/along", json={"slot": 1}).status_code == 200


def test_the_water_habitats_are_the_agreed_ones():
    assert {k for k, h in pet_care.HABITAT_KINDS.items() if h.water} == {"stream", "beach", "jungle", "pond", "savanna", "crystalcave", "grove", "lagoon"}


def test_the_foggy_lagoon_is_a_magical_habitat_for_mermaids():
    lagoon = pet_care.HABITAT_KINDS["lagoon"]
    assert (lagoon.name, lagoon.tier, lagoon.water) == ("Foggy Lagoon", "magical", True)


def test_companions_are_always_grown():
    fairy = _adopt("flower_fairy", 0)
    dog = _adopt("dog", 2)
    pets = {p["id"]: p for p in client.get("/api/care").json()["pets"]}
    assert pets[fairy]["growth"] == 10 and pets[fairy]["companion"]
    assert pets[dog]["growth"] == 2 and not pets[dog]["companion"]


def test_companions_who_were_babies_grow_up_on_start():
    with db.open_db(main.DB_PATH) as conn:
        fairy = db.add_v3_pet(conn, 1, g.roll("flower_fairy", None, None, 7), "Fern", "lab", growth=1)
        egg = db.add_v3_pet(conn, 1, g.roll("dragon", None, None, 7), "Egg", "shop", growth=0)
    with db.open_db(main.DB_PATH) as conn:
        db.init_schema(conn)
        assert db.get_v3_pet(conn, 1, fairy)["growth"] == 10
        assert db.get_v3_pet(conn, 1, egg)["growth"] == 0
