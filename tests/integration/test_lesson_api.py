"""Integration tests for the brain-driven lesson loop, the daily goal and
its tokens, the parent page API, and the arcade."""

import pytest
from fastapi.testclient import TestClient

from app import brain, daily, db, lessons, main
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
    client.post("/api/grownups/pin", json={"pin": "1234"})
    assert client.put("/api/parent/settings", json={"goal_minutes": minutes, "learn_vs_practice": learn}).status_code == 200


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


def test_key_bonuses_wait_for_practice_after_the_teach_page(clock):
    run_lesson(client, clock)  # the intro
    learned = run_lesson(client, clock)["done"]  # F and J
    assert not [c for c in learned["coins_earned"] if c["reason"].startswith("key_")]
    paid = []
    for _ in range(lessons.PRACTICE_LESSONS_FOR_BONUS):
        done = run_lesson(client, clock)["done"]
        assert done["kind"] != "learn"
        paid.append({c["key"] for c in done["coins_earned"] if c["reason"] == lessons.KEY_SOLID})
    assert paid[:-1] == [set()] * (lessons.PRACTICE_LESSONS_FOR_BONUS - 1)
    assert {"f", "j"} <= paid[-1]


def test_a_learn_lesson_names_its_letters_and_what_they_opened(clock, monkeypatch):
    monkeypatch.setattr(brain, "MAX_LEARNS_PER_DAY", 99)
    run_lesson(client, clock)  # the intro
    fj = run_lesson(client, clock)["done"]
    assert fj["learned"] == ["f", "j"] and fj["shop_opened"] == [] and not fj["pet_coupon"]
    assert fj["key_bonus"] == lessons.KEY_BONUS
    with db.open_db(main.DB_PATH) as conn:  # D K and S L too: A ; is next, the last home key
        for pair in ("dk", "sl"):
            db.mark_taught(conn, 1, f"{PAIR_ID}:{pair}", "lesson")
    for _ in range(30):  # practice until the brain's ready for the next new lesson
        lesson = run_lesson(client, clock)
        if lesson["lesson"]["kind"] == "learn":
            break
    assert lesson["lesson"]["teach_keys"] == "a;", lesson["lesson"]["reasons"]
    done = lesson["done"]
    assert done["learned"] == [";", "a"]
    assert [d["id"] for d in done["shop_opened"]] == ["household", "orders"]
    assert done["pet_coupon"]


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


def test_extra_practice_opens_a_resting_day_and_pays_two_tokens(clock):
    home_row_player()
    set_goal(2)  # bonus at 3 minutes
    run_lesson(client, clock, seconds=180)
    assert client.post("/api/lesson/next").status_code == 409  # resting
    entry = client.post("/api/parent/extra").json()
    assert entry["day"]["extra"] == {"seconds": 900, "practiced_seconds": 0, "tokens": 2, "active": True}
    assert entry["day"]["resting_until"] is None
    assert client.post("/api/parent/extra").status_code == 400  # one at a time
    part = run_lesson(client, clock, seconds=500)["done"]
    assert part["day"]["extra"]["practiced_seconds"] == 500 and part["tokens_earned"] == []
    done = run_lesson(client, clock, seconds=400)["done"]
    assert done["tokens_earned"] == [{"amount": daily.EXTRA_TOKENS, "reason": "daily_extra"}]
    assert done["day"]["extra"] is None and done["day"]["resting_until"]
    assert client.post("/api/lesson/next").status_code == 409
    assert client.post("/api/parent/extra").status_code == 200  # another one, if a grown-up says so


def test_extra_practice_waits_for_the_regular_day_and_expires_with_it(clock):
    home_row_player()
    set_goal(2)
    client.post("/api/parent/extra")
    day = client.get("/api/day").json()
    assert day["extra"]["active"] is False and day["practiced_seconds"] == 0
    over = run_lesson(client, clock, seconds=300)["done"]  # 3 minutes fill the day, 2 go to extra
    assert [t["reason"] for t in over["tokens_earned"]] == ["daily_goal", "daily_bonus"]
    assert over["day"]["extra"] == {"seconds": 900, "practiced_seconds": 120, "tokens": 2, "active": True}
    clock.advance(hours=12, minutes=1)  # the next practice day: unused extra time is gone
    assert client.get("/api/day").json()["extra"] is None


def test_extra_practice_needs_the_grownups_pin(clock):
    home_row_player()
    client.post("/api/grownups/pin", json={"pin": "1234"})
    client.post("/api/grownups/lock")
    assert client.post("/api/parent/extra").status_code in (401, 403)


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


def test_grownups_see_just_the_current_player_with_the_brains_next_pick():
    assert client.get("/api/parent").status_code == 403  # no PIN yet
    client.post("/api/grownups/pin", json={"pin": "1234"})
    me = client.get("/api/parent").json()
    assert me["name"] == "Tester"
    assert me["brain"]["kind"] == "learn" and me["brain"]["reasons"]
    assert me["settings"] == {"goal_minutes": 10, "learn_vs_practice": 0.5}
    client.post("/api/profiles", json={"name": "Second"})  # becomes the current player
    assert client.get("/api/parent").json()["name"] == "Second"


def test_the_pin_is_needed_once_chosen():
    client.post("/api/grownups/pin", json={"pin": "1234"})
    client.post("/api/grownups/lock")
    assert client.get("/api/parent").status_code == 403
    assert client.post("/api/grownups/pin", json={"pin": "9999"}).status_code == 403  # can't just choose another
    assert client.post("/api/grownups/unlock", json={"pin": "0000"}).status_code == 403
    assert client.post("/api/grownups/unlock", json={"pin": "1234"}).status_code == 200
    assert client.get("/api/parent").status_code == 200
    assert client.post("/api/grownups/pin", json={"pin": "abcd"}).status_code == 400
    client.post("/api/grownups/pin", json={"pin": "5555"})
    client.post("/api/grownups/lock")
    assert client.post("/api/grownups/unlock", json={"pin": "1234"}).status_code == 403
    assert client.post("/api/grownups/unlock", json={"pin": "5555"}).status_code == 200


def test_only_a_salted_hash_of_the_pin_is_kept():
    client.post("/api/grownups/pin", json={"pin": "1234"})
    saved = (main.DB_PATH.parent / "grownup_pin.json").read_text()
    assert "1234" not in saved


def test_parent_settings_save_and_validate():
    client.post("/api/grownups/pin", json={"pin": "1234"})
    resp = client.put("/api/parent/settings", json={"goal_minutes": 15, "learn_vs_practice": 0.0})
    assert resp.json()["settings"] == {"goal_minutes": 15, "learn_vs_practice": 0.0}
    assert resp.json()["solid_bar"] == 0.98
    assert client.put("/api/parent/settings", json={"goal_minutes": 0, "learn_vs_practice": 0.5}).status_code == 422


# --- arcade ---------------------------------------------------------------------------------


def give_tokens(n: int):
    with db.open_db(main.DB_PATH) as conn:
        db.add_tokens(conn, 1, n, "test")


def test_arcade_lists_games_with_prices():
    games = {g["id"]: g for g in client.get("/api/arcade").json()["games"]}
    assert games["game_crow_patrol_v1"]["price"] == 1
    assert games["wanderpaw"]["price"] == 2 and games["wanderpaw"]["url"] == "/wanderpaw"
    assert "game_pet_battle_v1" not in games  # Wanderpaw took its place
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
    poor = client.post("/api/arcade/play/wanderpaw")
    assert poor.status_code == 400 and "2 tokens" in poor.json()["detail"]
    assert client.post("/api/arcade/play/game_pet_battle_v1").status_code == 400
    assert client.post("/api/arcade/play/nope").status_code == 400


def test_outside_dev_mode_a_game_only_pays_for_the_rounds_you_bought(monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DEV_MODE", False)
    home_row_player()
    crows = "game_crow_patrol_v1"
    pay = lambda: client.post(f"/api/game/{crows}/round", json={"keys": ["a"], "keystrokes": [], "score": 1000}).json()  # noqa: E731
    assert pay()["coins_earned"] == []  # none bought
    page = client.get(f"/game/{crows}?arcade=1", follow_redirects=False)
    assert page.status_code in (302, 307) and page.headers["location"] == "/arcade"
    give_tokens(1)
    assert client.post(f"/api/arcade/play/{crows}").status_code == 200
    assert client.get(f"/game/{crows}?arcade=1", follow_redirects=False).status_code == 200
    rounds = [pay()["coins_earned"] for _ in range(6)]
    assert [bool(r) for r in rounds] == [True] * 5 + [False]  # its 5 rounds, then no more
    assert client.get(f"/game/{crows}?arcade=1", follow_redirects=False).status_code in (302, 307)  # used up


def test_pages_are_served():
    for path in ("/", "/session", "/arcade", "/parent"):
        assert client.get(path).status_code == 200
