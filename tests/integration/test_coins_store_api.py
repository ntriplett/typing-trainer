"""Integration tests for coins + store over HTTP (PLAN.md Section 11c):
lesson completion pays coins, /api/me reports them, the store endpoints
buy/equip against a real temp SQLite DB.
"""

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main, store
from tests.integration.lesson_helpers import keystrokes_for, run_lesson

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    lessons._LESSONS.clear()
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})  # picks the player (cookie) as learner 1
    yield


def _give_coins(amount: int) -> None:
    client.get("/api/me")  # creates learner 1 + starters
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, amount, "test")


def test_me_starts_with_zero_coins_and_a_starter_avatar():
    data = client.get("/api/me").json()
    assert data["coins"] == 0
    assert data["learner"]["id"] == 1
    assert data["avatar"]["background"] == store.DEFAULT_BACKGROUND
    assert set(data["avatar"]["appearance"]) == {"gender", "skin", "hair_color", "hair_style", "eye_color"}


def _home_row():
    client.put("/api/profiles/placement", json={"keys": "home_row", "speed": "some"})


def test_perfect_lesson_pays_100_coins():
    _home_row()
    resp = run_lesson(client)["done"]
    lesson = [c for c in resp["coins_earned"] if c["reason"] == "lesson"]
    assert lesson == [{"amount": 100, "reason": "lesson"}]
    assert client.get("/api/me").json()["coins"] == resp["coin_balance"]


def test_spaces_dropped_at_line_wraps_dont_cost_coins():
    _home_row()
    nxt = client.post("/api/lesson/next").json()
    prompt = nxt["content"]["prompt"]
    assert prompt.count(" ") >= 2
    typed = prompt.replace(" ", "", 2)  # the page wrapped twice, dropping 2 spaces
    resp = client.post(
        f"/api/lesson/{nxt['lesson']['lesson_id']}/complete",
        json={"keystrokes": keystrokes_for(typed), "skipped_chars": 2},
    ).json()
    assert [c for c in resp["coins_earned"] if c["reason"] == "lesson"] == [{"amount": 100, "reason": "lesson"}]


def test_empty_lesson_pays_nothing():
    _home_row()
    nxt = client.post("/api/lesson/next").json()
    resp = client.post(f"/api/lesson/{nxt['lesson']['lesson_id']}/complete", json={"keystrokes": []}).json()
    assert [c for c in resp["coins_earned"] if c["reason"] == "lesson"] == []


def test_the_intro_pays_its_first_time_bonus():
    resp = run_lesson(client)["done"]
    assert resp["coins_earned"][0] == {"amount": 250, "reason": "teach_first"}


def test_store_lists_catalog_without_starters_and_with_flags():
    items = client.get("/api/store").json()["items"]
    assert items and all(not i["starter"] for i in items)
    assert all(not i["owned"] and not i["equipped"] and not i["affordable"] for i in items)


def test_buy_and_equip_round_trip():
    item = min((i for i in store.CATALOG.values() if not i.starter), key=lambda i: i.price)
    _give_coins(item.price)

    resp = client.post(f"/api/store/buy/{item.id}")
    assert resp.status_code == 200
    assert resp.json()["coins"] == 0

    resp = client.post(f"/api/store/equip/{item.id}")
    assert resp.status_code == 200
    assert resp.json()["avatar"][item.slot] == item.id

    resp = client.post(f"/api/store/unequip/{item.slot}")
    # an emptied slot is either bare or back to its free starter item
    assert resp.json()["avatar"].get(item.slot) in (None, store.SLOT_DEFAULTS.get(item.slot))


def test_buy_without_coins_is_a_400_with_a_reason():
    item = next(i for i in store.CATALOG.values() if not i.starter)
    resp = client.post(f"/api/store/buy/{item.id}")
    assert resp.status_code == 400
    assert "coins" in resp.json()["detail"]


def test_store_page_is_served():
    resp = client.get("/store")
    assert resp.status_code == 200
    assert "Store" in resp.text


def test_profile_reports_stats():
    data = client.get("/api/profile").json()
    assert data["stats"] == {
        "coins_earned_total": 0, "sessions_completed": 0, "keys_mastered": 0,
        "items_owned": sum(1 for i in store.CATALOG.values() if i.starter),
    }


def test_rename():
    assert client.put("/api/me/name", json={"name": "  Robin "}).json()["learner"]["name"] == "Robin"
    assert client.put("/api/me/name", json={"name": "   "}).status_code == 400


def test_designer_saves_appearance_and_guards_dyes():
    opts = client.get("/api/appearance").json()["options"]
    assert {"boy", "girl"} == set(opts["gender"])
    assert any(c["dye"] and not c["unlocked"] for c in opts["hair_color"])

    look = {"gender": "girl", "skin": "tan", "hair_color": "ginger", "hair_style": "long", "eye_color": "green"}
    assert client.put("/api/appearance", json=look).json()["avatar"]["appearance"] == look

    resp = client.put("/api/appearance", json={**look, "hair_color": "blue"})
    assert resp.status_code == 400
    assert "dye" in resp.json()["detail"]


def test_profile_and_designer_pages_are_served():
    assert "Profile" in client.get("/profile").text
    assert "Designer" in client.get("/designer").text


def test_night_toggle_endpoint():
    assert client.put("/api/me/night", json={"on": True}).status_code == 400
    _give_coins(store.CATALOG["night_forests"].price)
    client.post("/api/store/buy/night_forests")
    data = client.put("/api/me/night", json={"on": True}).json()
    assert data["night"]["on"] is True and data["avatar"]["night"] is True
    assert client.put("/api/me/night", json={"on": False}).json()["night"]["on"] is False


def test_pets_api_round_trip():
    _home_row()  # opens the pet room
    _give_coins(10_000)
    data = client.post("/api/pets/adopt", json={"species": "dog", "color": "golden"}).json()
    pet = data["pets"][0]
    assert data["avatar"]["pets"][0]["species"] == "dog"
    pet_id = pet["id"]
    assert client.post(f"/api/pets/{pet_id}/feed").json()["pets"][0]["growth"] == 1
    assert client.post(f"/api/pets/{pet_id}/feed").status_code == 400
    assert client.put(f"/api/pets/{pet_id}/name", json={"name": "Biscuit"}).json()["pets"][0]["name"] == "Biscuit"
    assert client.put(f"/api/pets/{pet_id}/along", json={"slot": None}).json()["avatar"]["pets"] == []
    assert client.get("/pets").status_code == 200


def test_room_api_round_trip():
    client.put("/api/profiles/placement", json={"keys": "letters", "speed": "some"})  # opens the bedroom
    _give_coins(5_000)
    client.post("/api/store/buy/furniture_bed_blue")
    data = client.post("/api/room/items", json={"item_id": "furniture_bed_blue"}).json()
    placed = data["room"]["items"][0]
    moved = client.put(f"/api/room/items/{placed['id']}", json={"x": 5, "y": 60}).json()["room"]["items"][0]
    assert (moved["x"], moved["y"]) == (5, 60)
    assert client.delete(f"/api/room/items/{placed['id']}").json()["room"]["items"] == []
    assert client.put("/api/room/surface", json={"item_id": "flooring_stone"}).status_code == 400
    assert client.get("/bedroom").status_code == 200
