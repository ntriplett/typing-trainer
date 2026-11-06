"""Integration tests for gifts from grown-ups (app/pet_gift.py): a pet lab
design pasted on the For Grown-ups page waits wrapped up at the Pet Shop
until the player opens it, names it and takes it home, free, as a baby."""

import json

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main
from app import pet_genes as g

client = TestClient(main.app)
KID, DAD = 1, 2


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    lessons._LESSONS.clear()
    client.cookies.clear()
    for name in ("Sam", "Dad"):
        client.post("/api/profiles", json={"name": name})
    client.post("/api/grownups/pin", json={"pin": "1234"})
    yield


def bunny(name="Hoppy", seed=5):
    genes = g.roll("bunny", None, None, seed)
    genes["coat"] |= {"colors": ["snow", "chestnut", None], "shares": [0.7, 0.3, 0.0], "pattern": "dutch"}
    genes["battle"] |= {"level": 30}
    return {"name": name, "genes": json.loads(json.dumps(genes))}


def gift(design, to=KID, from_name="Dad"):
    return client.post("/api/parent/gift", json={"to": to, "from_name": from_name, "design": design})


def test_a_gift_waits_wrapped_at_the_shop_and_comes_home_named():
    sent = gift(bunny())
    assert sent.status_code == 200, sent.text
    assert sent.json()["gift"] == {"id": 1, "name": "Hoppy", "species": "bunny", "from": "Dad"}
    client.post(f"/api/profiles/{KID}/select")
    assert client.get("/api/pets/hub").json()["gift"] is True
    waiting = client.get("/api/pets/shop").json()["gift"]
    assert waiting["from"] == "Dad" and waiting["name"] == "Hoppy" and waiting["more"] == 0
    assert waiting["genes"]["coat"]["colors"] == ["snow", "chestnut", None] and waiting["genes"]["hex"][0]
    opened = client.post(f"/api/pets/shop/gift/{waiting['id']}/open", json={"name": "  Mr  Hops "})
    assert opened.status_code == 200, opened.text
    pet = opened.json()["opened"]
    assert pet["name"] == "Mr Hops" and pet["growth"] == 0 and pet["source"] == "gift" and pet["from"] == "Dad"
    assert opened.json()["gift"] is None and opened.json()["coins"] == 0  # free
    with db.open_db(main.DB_PATH) as conn:
        assert {"snow", "chestnut"} <= db.list_pet_color_unlocks(conn, KID)
        assert db.get_v3_pet(conn, KID, pet["id"])["genes"]["battle"]["level"] == 1
    care = client.get("/api/care").json()
    assert next(p for p in care["pets"] if p["id"] == pet["id"])["gift_from"] == "Dad"
    assert client.post(f"/api/pets/shop/gift/{waiting['id']}/open", json={}).status_code == 400  # opened already


def test_two_gifts_are_opened_one_at_a_time_and_a_blank_name_keeps_the_given_one():
    gift(bunny("Hoppy"))
    gift(bunny("Clover", seed=9))
    client.post(f"/api/profiles/{KID}/select")
    first = client.get("/api/pets/shop").json()["gift"]
    assert first["name"] == "Hoppy" and first["more"] == 1
    assert client.post(f"/api/pets/shop/gift/{first['id']}/open", json={"name": ""}).json()["opened"]["name"] == "Hoppy"
    second = client.get("/api/pets/shop").json()["gift"]
    assert second["name"] == "Clover" and second["more"] == 0


def test_only_grownups_can_give_and_only_real_pets():
    client.post("/api/grownups/lock")
    assert gift(bunny()).status_code in (401, 403)
    client.post("/api/grownups/unlock", json={"pin": "1234"})
    assert gift(bunny(), to=99).status_code == 400
    bad = bunny()
    bad["genes"]["coat"]["pattern"] = "plaid"
    assert gift(bad).status_code == 400
    assert gift({"species": "mermaid"}).status_code == 400
    assert gift(bunny()["genes"]).status_code == 200  # bare genes work too, named for their kind


def test_a_gift_is_only_for_its_player():
    gift(bunny(), to=DAD)
    client.post(f"/api/profiles/{KID}/select")
    assert client.get("/api/pets/shop").json()["gift"] is None
    assert client.post("/api/pets/shop/gift/1/open", json={}).status_code == 400
