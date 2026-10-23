"""Integration tests for coins + store over HTTP (PLAN.md Section 11c):
step completion pays coins, /api/me reports them, the store endpoints
buy/equip against a real temp SQLite DB.
"""

import pytest
from fastapi.testclient import TestClient

from app import db, main, store

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    main._SESSION_PLANS.clear()
    yield


def _all_correct(prompt: str) -> list[dict]:
    return [
        {"expected_char": ch, "typed_char": ch, "correct": True, "latency_ms": 200}
        for ch in prompt
    ]


def _give_coins(amount: int) -> None:
    client.get("/api/me")  # creates learner 1 + starters
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, amount, "test")


def test_me_starts_with_zero_coins_and_a_starter_avatar():
    data = client.get("/api/me").json()
    assert data["coins"] == 0
    assert data["learner"]["id"] == 1
    assert data["avatar"]["body"] == store.DEFAULT_BODY


def test_perfect_step_pays_100_coins():
    start = client.post("/api/session/start", params={"quick": True}).json()
    prompt = start["first_step_content"]["prompt"]
    resp = client.post(
        f"/api/session/{start['session_id']}/steps/0/complete",
        json={"keystrokes": _all_correct(prompt)},
    ).json()
    lesson = [c for c in resp["coins_earned"] if c["reason"] == "lesson"]
    assert lesson == [{"amount": 100, "reason": "lesson"}]
    assert resp["coin_balance"] == sum(c["amount"] for c in resp["coins_earned"])
    assert client.get("/api/me").json()["coins"] == resp["coin_balance"]


def test_empty_step_pays_nothing():
    start = client.post("/api/session/start", params={"quick": True}).json()
    resp = client.post(
        f"/api/session/{start['session_id']}/steps/0/complete", json={"keystrokes": []}
    ).json()
    assert [c for c in resp["coins_earned"] if c["reason"] == "lesson"] == []


def test_finishing_a_session_pays_the_completion_bonus():
    start = client.post("/api/session/start", params={"quick": True}).json()
    sid, steps = start["session_id"], len(start["steps"])
    last = None
    for i in range(steps):
        content = (
            start["first_step_content"]
            if i == 0
            else client.get(f"/api/session/{sid}/steps/{i}/content").json()["content"]
        )
        last = client.post(
            f"/api/session/{sid}/steps/{i}/complete",
            json={"keystrokes": _all_correct(content["prompt"])},
        ).json()
    assert last["session_complete"]
    assert {"amount": main.SESSION_COMPLETE_BONUS, "reason": "session_complete"} in last["coins_earned"]


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
    assert item.slot not in resp.json()["avatar"]


def test_buy_without_coins_is_a_400_with_a_reason():
    item = next(i for i in store.CATALOG.values() if not i.starter)
    resp = client.post(f"/api/store/buy/{item.id}")
    assert resp.status_code == 400
    assert "coins" in resp.json()["detail"]


def test_store_page_is_served():
    resp = client.get("/store")
    assert resp.status_code == 200
    assert "Store" in resp.text
