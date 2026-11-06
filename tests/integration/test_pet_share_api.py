"""Integration tests for sharing a pet's design with another player on
this computer (app/pet_share.py): it waits in their Special Orders the
next day for the shop price, one at a time each way, and the sender keeps
their pet."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main, pet_genes, pet_shop
from app.activities.teach_curriculum import PAIR_ID
from app.brain import lesson_ref

client = TestClient(main.app)
HOME_PAIRS = ("fj", "dk", "sl", "a;")
SAM, ALEX, JO = 1, 2, 3


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    lessons._LESSONS.clear()
    client.cookies.clear()
    for name in ("Sam", "Alex"):
        client.post("/api/profiles", json={"name": name})
    teach(SAM, *HOME_PAIRS)
    teach(ALEX, *HOME_PAIRS)
    play_as(SAM)
    yield


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    state = {"days": 0}
    base = datetime(2026, 11, 2, 12, 0).astimezone()
    monkeypatch.setattr(main, "now", lambda: (base + timedelta(days=state["days"])).astimezone(UTC))
    return state


def play_as(learner_id):
    assert client.post(f"/api/profiles/{learner_id}/select").status_code == 200


def teach(learner_id, *pairs):
    with db.open_db(main.DB_PATH) as conn:
        for pair in pairs:
            db.mark_taught(conn, learner_id, lesson_ref(PAIR_ID, pair), "lesson")


def give_coins(learner_id, n):
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, learner_id, n, "test")


def a_pet(learner_id, species="cat", seed=4242):
    genes = pet_genes.shop_roll(species, set(), seed)
    with db.open_db(main.DB_PATH) as conn:
        pet_id = db.add_v3_pet(conn, learner_id, genes, "Mittens", "shop", growth=7)
        conn.commit()
    return pet_id


def share(pet_id, to):
    return client.post(f"/api/care/{pet_id}/share", json={"to": to})


def shelf():
    return client.get("/api/pets/shop/orders").json()["shared"]


def test_a_shared_pet_arrives_the_next_day_and_the_sender_keeps_theirs(clock):
    pet = a_pet(SAM)
    friends = client.get(f"/api/care/{pet}/share").json()["friends"]
    assert friends == [{"id": ALEX, "name": "Alex", "why": None}]
    resp = share(pet, ALEX)
    assert resp.status_code == 200 and resp.json()["shared"]["to"] == "Alex"
    assert any(p["id"] == pet for p in resp.json()["pets"])  # still Sam's

    play_as(ALEX)
    assert shelf() == []  # on its way
    clock["days"] = 1
    [waiting] = shelf()
    assert waiting["from"] == "Sam" and waiting["species"] == "cat"
    assert client.get("/api/pets/shop").json()["shared_waiting"] == 1


def test_adopting_pays_the_shop_price_and_brings_home_a_baby(clock):
    pet = a_pet(SAM)
    with db.open_db(main.DB_PATH) as conn:
        original = db.get_v3_pet(conn, SAM, pet)
    share(pet, ALEX)
    play_as(ALEX)
    clock["days"] = 1
    [waiting] = shelf()
    assert waiting["price"] == pet_shop.price(original["genes"], set(), pet_shop.PRICE_ROLL_MEAN)
    assert client.post(f"/api/pets/shop/shared/{waiting['id']}/adopt").status_code == 400  # no coins yet
    give_coins(ALEX, waiting["price"] + 5)
    resp = client.post(f"/api/pets/shop/shared/{waiting['id']}/adopt")
    assert resp.status_code == 200, resp.text
    bought = resp.json()["bought"]
    assert bought["from"] == "Sam" and bought["growth"] == 0 and bought["source"] == "friend"
    assert resp.json()["coins"] == 5 and resp.json()["shared"] == []
    with db.open_db(main.DB_PATH) as conn:
        copy = db.get_v3_pet(conn, ALEX, bought["id"])
        assert copy["genes"]["coat"] == original["genes"]["coat"] and copy["genes"]["shape"] == original["genes"]["shape"]
        assert set(c for c in original["genes"]["coat"]["colors"] if c) <= db.list_pet_color_unlocks(conn, ALEX)
    care = client.get("/api/care").json()
    assert next(p for p in care["pets"] if p["id"] == bought["id"])["from_friend"] == "Sam"


def test_one_share_waits_at_a_time_each_way(clock):
    first, second = a_pet(SAM), a_pet(SAM, "dog", 7)
    assert share(first, ALEX).status_code == 200
    again = share(second, ALEX)
    assert again.status_code == 400 and "still waiting" in again.json()["detail"]
    assert client.get(f"/api/care/{second}/share").json()["friends"][0]["why"].startswith("Your last pet for Alex")
    play_as(ALEX)
    assert share(a_pet(ALEX, "bunny", 9), SAM).status_code == 200  # the other way is its own
    clock["days"] = 1
    client.post(f"/api/pets/shop/shared/{shelf()[0]['id']}/decline")
    assert shelf() == []
    play_as(SAM)
    assert share(second, ALEX).status_code == 200  # declined: Sam can share again


def test_a_friend_whose_shop_isnt_open_for_it_is_greyed_out(clock):
    client.post("/api/profiles", json={"name": "Jo"})  # learned nothing yet
    play_as(SAM)
    fish = a_pet(SAM, "fish", 11)
    friends = {f["name"]: f["why"] for f in client.get(f"/api/care/{fish}/share").json()["friends"]}
    assert friends == {"Alex": None, "Jo": "Jo needs to learn the home row first."}
    goat = a_pet(SAM, "goat", 12)
    friends = {f["name"]: f["why"] for f in client.get(f"/api/care/{goat}/share").json()["friends"]}
    assert friends["Alex"] == "Alex needs to learn the top row first."
    assert share(goat, ALEX).status_code == 400


def test_companions_cant_be_shared_and_bad_friends_are_refused(clock):
    fairy = a_pet(SAM, "flower_fairy", 13)
    assert client.get(f"/api/care/{fairy}/share").status_code == 400
    cat = a_pet(SAM)
    assert share(cat, SAM).status_code == 400
    assert share(cat, 99).status_code == 400
    play_as(ALEX)
    assert share(cat, SAM).status_code == 400  # not Alex's pet


def test_only_the_friend_can_adopt_and_only_once_its_here(clock):
    share(a_pet(SAM), ALEX)
    with db.open_db(main.DB_PATH) as conn:
        [s] = db.waiting_pet_shares(conn, to_learner=ALEX)
    give_coins(ALEX, 99999)
    give_coins(SAM, 99999)
    play_as(ALEX)
    assert client.post(f"/api/pets/shop/shared/{s['id']}/adopt").status_code == 400  # not here yet
    clock["days"] = 1
    play_as(SAM)
    assert client.post(f"/api/pets/shop/shared/{s['id']}/adopt").status_code == 400  # not for Sam
    play_as(ALEX)
    assert client.post(f"/api/pets/shop/shared/{s['id']}/adopt").status_code == 200
    assert client.post(f"/api/pets/shop/shared/{s['id']}/adopt").status_code == 400  # gone home
