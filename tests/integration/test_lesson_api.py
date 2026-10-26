"""Integration tests for the brain-driven lesson loop, the daily goal and
its tokens, the parent page API, and the arcade."""

import pytest
from fastapi.testclient import TestClient

from app import daily, db, lessons, main
from app.activities.teach_curriculum import INTRO_ID, PAIR_ID
from tests.integration.lesson_helpers import keystrokes_for, run_lesson, use_clock

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
    return use_clock(monkeypatch)


def home_row_player():
    client.put("/api/profiles/placement", json={"keys": "home_row", "speed": "some"})


def set_goal(minutes: int, learn: float = 0.5):
    assert client.put("/api/parent/1/settings", json={"goal_minutes": minutes, "learn_vs_practice": learn}).status_code == 200


# --- the lesson loop -------------------------------------------------------------


def test_a_new_player_starts_with_the_intro_then_f_and_j(clock):
    first = run_lesson(client, clock)
    assert (first["lesson"]["kind"], first["lesson"]["activity_id"]) == ("learn", INTRO_ID)
    assert first["content"]["micro_steps"]
    second = client.post("/api/lesson/next").json()["lesson"]
    assert (second["kind"], second["activity_id"], second["teach_keys"]) == ("learn", PAIR_ID, "fj")
    assert second["title"] == "F and J"


def test_learning_marks_keys_taught_and_unlocked(clock):
    run_lesson(client, clock)
    run_lesson(client, clock)  # F and J
    with db.open_db(main.DB_PATH) as conn:
        assert set(db.list_taught(conn, 1)) == {f"{INTRO_ID}:", f"{PAIR_ID}:fj"}
        assert db.get_key_stat(conn, 1, "f").unlocked_at is not None
    nxt = client.post("/api/lesson/next").json()
    assert nxt["lesson"]["kind"] == "practice"  # one new lesson a day after the first letters
    assert set(nxt["content"]["prompt"]) <= set("fj ")


def test_placement_skips_ahead_and_opens_with_a_warmup(clock):
    home_row_player()
    data = client.post("/api/lesson/next").json()
    assert data["lesson"]["kind"] == "warmup"
    assert set(data["content"]["prompt"]) <= set("asdfghjkl; ")
    assert data["lesson"]["predicted_wpm"] == 12
    assert data["lesson"]["reasons"]


def test_finishing_a_practice_lesson_scores_pays_and_records(clock):
    home_row_player()
    done = run_lesson(client, clock, seconds=50)["done"]
    assert done["result"]["accuracy"] == 1.0
    assert {"amount": 100, "reason": "lesson"} in done["coins_earned"]
    assert done["day"]["practiced_seconds"] == 50
    with db.open_db(main.DB_PATH) as conn:
        events = db.recent_lesson_events(conn, 1)
        assert [e["phase"] for e in events] == ["warmup"]
        assert events[0]["stats"]["finished_share"] == 1.0
        assert db.list_bigram_stats(conn, 1)


def test_active_time_is_capped_by_the_clock(clock):
    home_row_player()
    nxt = client.post("/api/lesson/next").json()
    clock.advance(seconds=20)
    done = client.post(
        f"/api/lesson/{nxt['lesson']['lesson_id']}/complete",
        json={"keystrokes": keystrokes_for(nxt["content"]["prompt"]), "active_ms": 600_000},
    ).json()
    assert done["active_seconds"] <= 22


def test_lessons_close_together_share_a_sitting(clock):
    home_row_player()
    run_lesson(client, clock)
    run_lesson(client, clock)
    clock.advance(minutes=45)
    run_lesson(client, clock)
    with db.open_db(main.DB_PATH) as conn:
        assert conn.execute("SELECT COUNT(*) FROM session").fetchone()[0] == 2


def test_a_struggle_gets_an_easier_lesson(clock):
    home_row_player()
    run_lesson(client, clock)
    run_lesson(client, clock, correct=False)
    nxt = client.post("/api/lesson/next").json()["lesson"]
    assert nxt["comfort"] and nxt["difficulty"] == 0.0


def test_unknown_or_finished_lessons_404(clock):
    home_row_player()
    assert client.post("/api/lesson/999/complete", json={"keystrokes": []}).status_code == 404
    lesson_id = run_lesson(client, clock)["lesson"]["lesson_id"]
    assert client.post(f"/api/lesson/{lesson_id}/complete", json={"keystrokes": []}).status_code == 404
    assert client.get(f"/api/lesson/{lesson_id}").status_code == 404


def test_a_lesson_can_be_fetched_again_by_id(clock):
    home_row_player()
    nxt = client.post("/api/lesson/next").json()
    again = client.get(f"/api/lesson/{nxt['lesson']['lesson_id']}").json()
    assert again["content"]["prompt"] == nxt["content"]["prompt"]


# --- the daily goal and tokens ---------------------------------------------------------


def test_goal_pays_two_tokens_and_the_bonus_one_more_then_rests(clock):
    home_row_player()
    set_goal(2)  # bonus at 3 minutes
    assert run_lesson(client, clock, seconds=60)["done"]["tokens_earned"] == []
    goal = run_lesson(client, clock, seconds=60)["done"]
    assert goal["tokens_earned"] == [{"amount": 2, "reason": "daily_goal"}]
    assert {"amount": daily.GOAL_COINS, "reason": "daily_goal"} in goal["coins_earned"]
    assert goal["day"]["goal_reached"] and not goal["day"]["bonus_reached"]
    bonus = run_lesson(client, clock, seconds=60)["done"]
    assert bonus["tokens_earned"] == [{"amount": 1, "reason": "daily_bonus"}]
    assert bonus["token_balance"] == 3
    assert bonus["day"]["resting_until"]

    resting = client.post("/api/lesson/next")
    assert resting.status_code == 409
    assert resting.json()["detail"]["resting_until"] == bonus["day"]["resting_until"]

    clock.advance(hours=12, minutes=1)
    day = client.get("/api/day").json()
    assert day["practiced_seconds"] == 0 and not day["goal_reached"]
    assert client.post("/api/lesson/next").status_code == 200


def test_skipping_the_bonus_forfeits_it_after_twelve_hours(clock):
    home_row_player()
    set_goal(2)
    run_lesson(client, clock, seconds=120)
    clock.advance(hours=12, minutes=1)
    done = run_lesson(client, clock, seconds=60)["done"]
    assert done["tokens_earned"] == []  # a fresh day, 1 of 2 minutes
    assert done["day"]["practiced_seconds"] == 60


def test_an_unfinished_day_resets_overnight(clock):
    home_row_player()
    set_goal(10)
    run_lesson(client, clock, seconds=60)
    clock.advance(hours=17)
    assert client.get("/api/day").json()["practiced_seconds"] == 60
    clock.advance(hours=2)
    assert client.get("/api/day").json()["practiced_seconds"] == 0


def test_me_carries_tokens_and_the_day():
    me = client.get("/api/me").json()
    assert me["tokens"] == 0
    assert me["day"]["goal_seconds"] == daily.DEFAULT_GOAL_MINUTES * 60
    assert me["day"]["bonus_seconds"] == daily.DEFAULT_GOAL_MINUTES * 90


# --- parent page ------------------------------------------------------------------------


def test_parent_overview_lists_every_player_with_the_brains_next_pick():
    client.post("/api/profiles", json={"name": "Second"})
    players = client.get("/api/parent").json()
    assert [p["name"] for p in players] == ["Tester", "Second"]
    assert players[0]["brain"]["kind"] == "learn" and players[0]["brain"]["reasons"]
    assert players[0]["settings"] == {"goal_minutes": 10, "learn_vs_practice": 0.5}


def test_parent_settings_save_and_validate():
    resp = client.put("/api/parent/1/settings", json={"goal_minutes": 15, "learn_vs_practice": 0.0})
    assert resp.json()["settings"] == {"goal_minutes": 15, "learn_vs_practice": 0.0}
    assert resp.json()["solid_bar"] == 0.98
    assert client.put("/api/parent/1/settings", json={"goal_minutes": 0, "learn_vs_practice": 0.5}).status_code == 422
    assert client.put("/api/parent/9/settings", json={"goal_minutes": 10, "learn_vs_practice": 0.5}).status_code == 404


# --- arcade ---------------------------------------------------------------------------------


def give_tokens(n: int):
    with db.open_db(main.DB_PATH) as conn:
        db.add_tokens(conn, 1, n, "test")


def test_arcade_lists_games_with_prices():
    games = {g["id"]: g for g in client.get("/api/arcade").json()["games"]}
    assert games["game_crow_patrol_v1"]["price"] == 1
    assert games["game_pet_battle_v1"]["price"] == 2
    assert not any(g["affordable"] for g in games.values())


def test_games_wait_for_enough_letters():
    give_tokens(2)
    assert not any(g["ready"] for g in client.get("/api/arcade").json()["games"])
    resp = client.post("/api/arcade/play/game_crow_patrol_v1")
    assert resp.status_code == 400 and "letters" in resp.json()["detail"]
    assert client.get("/api/me").json()["tokens"] == 2


def test_playing_spends_tokens():
    home_row_player()
    give_tokens(2)
    assert client.post("/api/arcade/play/game_crow_patrol_v1").json()["tokens"] == 1
    poor = client.post("/api/arcade/play/game_pet_battle_v1")
    assert poor.status_code == 400 and "2 tokens" in poor.json()["detail"]
    assert client.post("/api/arcade/play/nope").status_code == 400


def test_pages_are_served():
    for path in ("/", "/session", "/arcade", "/parent"):
        assert client.get(path).status_code == 200
