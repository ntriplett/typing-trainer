"""Integration tests for reward pets (app/pet_rewards.py): learning certain
keys wraps up a free, random pet at the Pet Shop, once each."""

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main, pet_rewards
from app.activities.teach_curriculum import PAIR_ID
from app.brain import lesson_ref

client = TestClient(main.app)
KID = 1


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    lessons._LESSONS.clear()
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Sam"})
    yield


def teach(*pairs):
    with db.open_db(main.DB_PATH) as conn:
        for pair in pairs:
            db.mark_taught(conn, KID, lesson_ref(PAIR_ID, pair), "lesson")


def waiting():
    with db.open_db(main.DB_PATH) as conn:
        return db.waiting_pet_gifts(conn, KID)


def grant():
    with db.open_db(main.DB_PATH) as conn:
        return pet_rewards.grant(conn, KID)


def test_nothing_before_four_keys():
    teach("fj")
    assert grant() == [] and waiting() == []


@pytest.mark.parametrize(
    ("pairs", "species"),
    [
        (("fj", "dk"), ["bunny"]),
        (("fj", "dk", "ru"), ["bunny", "sheep"]),
        (("fj", "dk", "ru", "ei"), ["bunny", "sheep"]),
        (("fj", "dk", "ru", "ei", "wo"), ["bunny", "sheep", "fox"]),
        (("fj", "dk", "ru", "ei", "wo", "vm", "c,"), ["bunny", "sheep", "fox", "turtle"]),
    ],
)
def test_each_milestone_wraps_up_its_pet(pairs, species):
    teach(*pairs)
    assert [r["species"] for r in grant()] == species
    gifts = waiting()
    assert [x["genes"]["species"] for x in gifts] == species
    assert all(x["from_name"] == "the Pet Shop" and "hard work" in x["note"] for x in gifts)


def test_each_reward_is_given_once_even_after_opening():
    teach("fj", "dk")
    assert len(grant()) == 1
    assert grant() == []
    client.post(f"/api/profiles/{KID}/select")
    gift = client.get("/api/pets/shop").json()["gift"]
    assert gift["species"] == "bunny" and gift["note"] == "For learning F, J, D and K. All your hard work is paying off!"
    opened = client.post(f"/api/pets/shop/gift/{gift['id']}/open", json={"name": "Clover"})
    assert opened.status_code == 200 and opened.json()["opened"]["growth"] == 0
    assert grant() == [] and client.get("/api/pets/shop").json()["gift"] is None


def test_players_who_learned_the_keys_already_get_theirs_at_the_pets_hub():
    teach("fj", "dk", "ru", "ei", "wo")  # learned before rewards existed, or by placement
    client.post(f"/api/profiles/{KID}/select")
    assert client.get("/api/pets/hub").json()["gift"] is True
    gift = client.get("/api/pets/shop").json()["gift"]
    assert gift["species"] == "bunny" and gift["more"] == 2
