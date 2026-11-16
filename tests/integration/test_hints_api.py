"""Integration tests for the fading keyboard hint: lesson plans, the ratchet,
coins, More/Less, the grown-up override and report (app/hints.py)."""

import pytest
from fastapi.testclient import TestClient

from app import db, hint_model as hm, hints, lessons, main
from tests.integration.lesson_helpers import run_lesson, use_clock

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


def grownup():
    client.post("/api/grownups/pin", json={"pin": "1234"})


def set_supports(value: float, keys="asdfghjkl; "):
    with db.open_db(main.DB_PATH) as conn:
        for k in keys:
            db.set_key_hint(conn, 1, k, value)


def typed(prompt: str, plan: dict, latency_ms=200, correct=True, solo=False) -> list[dict]:
    return [
        {
            "expected_char": ch, "typed_char": ch if correct else "?", "correct": correct, "latency_ms": latency_ms,
            "hint_support": plan["keys"][hm.hint_key(ch)], "solo": solo,
        }
        for ch in prompt
    ]


def next_lesson() -> dict:
    """The next lesson that isn't a new letter (those are on the teach page, without these hints)."""
    while True:
        resp = client.post("/api/lesson/next")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["lesson"]["kind"] != "learn":
            return body
        run_lesson_done(body)


def run_lesson_done(body: dict) -> None:
    strokes = [{"expected_char": c, "typed_char": c, "correct": True, "latency_ms": 200} for c in body["content"]["prompt"]]
    finish(body, strokes)


def finish(body: dict, strokes: list[dict]) -> dict:
    done = client.post(f"/api/lesson/{body['lesson']['lesson_id']}/complete", json={"keystrokes": strokes, "active_ms": 60000})
    assert done.status_code == 200, done.text
    return done.json()


def coins(done: dict, reason: str) -> list[dict]:
    return [c for c in done["coins_earned"] if c["reason"] == reason]


# --- the plan a lesson comes with ---------------------------------------------------


def test_placement_keys_start_past_the_letters(clock):
    home_row_player()
    body = next_lesson()
    plan = body["lesson"]["hints"]
    assert plan["mode"] == "auto" and plan["keyboard"]
    assert set(plan["keys"]) == set(hints.lesson_keys(body["content"]["prompt"]))
    assert set(plan["keys"].values()) == {3.0}
    assert plan["rescue"] == hm.rescue_params()
    assert plan["solo_lines"] == []  # the first lesson of a sitting is a warmup


def test_keys_just_taught_start_at_full_help(clock):
    run_lesson(client, clock)  # the intro: space
    run_lesson(client, clock)  # F and J
    with db.open_db(main.DB_PATH) as conn:
        assert {k: v for k, v in db.get_key_hints(conn, 1).items() if k in "fj"} == {"f": 5.0, "j": 5.0}


# --- finishing a lesson -----------------------------------------------------------------


def test_presses_before_any_light_lower_support_log_and_pay(clock):
    home_row_player()
    body = next_lesson()
    done = finish(body, typed(body["content"]["prompt"], body["lesson"]["hints"], latency_ms=200))
    assert coins(done, "hint_free") == [{"amount": hm.FREE_BONUS_MAX, "reason": "hint_free"}]
    with db.open_db(main.DB_PATH) as conn:
        assert all(v < 3.0 for v in db.get_key_hints(conn, 1).values())
        seen = {r["hint_seen"] for r in conn.execute("SELECT hint_seen FROM keystroke_log")}
    assert seen == {"free"}


def test_misses_raise_support_and_pay_nothing(clock):
    home_row_player()
    body = next_lesson()
    done = finish(body, typed(body["content"]["prompt"], body["lesson"]["hints"], correct=False))
    assert not coins(done, "hint_free")
    with db.open_db(main.DB_PATH) as conn:
        assert all(v > 3.0 for v in db.get_key_hints(conn, 1).values())


def test_guided_presses_dont_count_toward_mastery(clock):
    home_row_player()
    set_supports(5.0)  # lit at once: every press is guided
    body = next_lesson()
    with db.open_db(main.DB_PATH) as conn:
        before = {s.key: s for s in db.list_key_stats(conn, 1)}
    finish(body, typed(body["content"]["prompt"], body["lesson"]["hints"]))
    with db.open_db(main.DB_PATH) as conn:
        assert {s.key: s for s in db.list_key_stats(conn, 1)} == before
        assert lessons.key_records(conn, 1) == {}


def test_graduating_a_key_pays_once(clock):
    home_row_player()
    set_supports(4.1)
    body = next_lesson()
    done = finish(body, typed(body["content"]["prompt"], body["lesson"]["hints"], latency_ms=200))
    graduated = coins(done, hm.LETTERS_OFF)
    assert graduated and all(c["amount"] == hm.GRADUATION_COINS for c in graduated)
    keys = {c["key"] for c in graduated}
    set_supports(4.1)  # it needed the letters again for a while
    again = next_lesson()
    done = finish(again, typed(again["content"]["prompt"], again["lesson"]["hints"], latency_ms=200))
    assert not keys & {c["key"] for c in coins(done, hm.LETTERS_OFF)}


def test_keystrokes_without_hint_support_leave_supports_alone(clock):
    home_row_player()
    body = next_lesson()
    before = body["lesson"]["hints"]["keys"]
    strokes = [{k: v for k, v in s.items() if k != "hint_support"} for s in typed(body["content"]["prompt"], body["lesson"]["hints"])]
    done = finish(body, strokes)
    assert not coins(done, "hint_free")
    with db.open_db(main.DB_PATH) as conn:
        assert {k: v for k, v in db.get_key_hints(conn, 1).items() if k in before} == before


def test_solo_flag_only_counts_when_the_lesson_had_solo_lines(clock):
    home_row_player()
    body = next_lesson()  # a warmup: no solo lines
    finish(body, typed(body["content"]["prompt"], body["lesson"]["hints"], solo=True))
    with db.open_db(main.DB_PATH) as conn:
        assert {r["solo"] for r in conn.execute("SELECT solo FROM keystroke_log")} == {0}


# --- More / Less ---------------------------------------------------------------------------


def test_more_and_less_move_every_key_and_fade_after_a_lesson(clock):
    home_row_player()
    more = client.post("/api/hint/nudge", json={"direction": "more", "keys": "fj"}).json()
    assert more["nudge"] == pytest.approx(hm.NUDGE_MORE_MAX)  # no history: not leaning on help
    assert more["keys"] == {"f": 4.0, "j": 4.0}
    body = next_lesson()
    assert set(body["lesson"]["hints"]["keys"].values()) == {4.0}
    finish(body, typed(body["content"]["prompt"], body["lesson"]["hints"]))
    less = client.post("/api/hint/nudge", json={"direction": "less", "keys": "f"}).json()
    assert less["nudge"] == pytest.approx(hm.NUDGE_MORE_MAX * hm.NUDGE_DECAY + hm.NUDGE_LESS)


def test_more_gives_less_to_a_learner_who_waits_for_the_lights(clock):
    home_row_player()
    body = next_lesson()
    finish(body, typed(body["content"]["prompt"], body["lesson"]["hints"], latency_ms=9000))  # always waited
    step = client.post("/api/hint/nudge", json={"direction": "more", "keys": "f"}).json()["step"]
    assert step == pytest.approx(hm.NUDGE_MORE_MIN, abs=0.05)


def test_bad_nudge_direction_422():
    assert client.post("/api/hint/nudge", json={"direction": "lots"}).status_code == 422


# --- grown-ups ---------------------------------------------------------------------------


def test_report_and_override_need_a_grownup():
    assert client.get("/api/parent/hints").status_code in (401, 403)
    assert client.put("/api/parent/hints", json={"mode": "off"}).status_code in (401, 403)


def test_override_full_and_off(clock):
    home_row_player()
    grownup()
    assert client.put("/api/parent/hints", json={"mode": "full"}).json()["mode"] == "full"
    body = next_lesson()
    plan = body["lesson"]["hints"]
    assert set(plan["keys"].values()) == {5.0} and plan["rescue"] is None
    done = finish(body, typed(body["content"]["prompt"], plan))
    assert not coins(done, "hint_free")  # only the brain's own hints move or pay
    assert client.post("/api/hint/nudge", json={"direction": "more"}).status_code == 409
    client.put("/api/parent/hints", json={"mode": "off"})
    plan = next_lesson()["lesson"]["hints"]
    assert not plan["keyboard"] and set(plan["keys"].values()) == {0.0}


def test_report_shows_supports_and_lift(clock):
    home_row_player()
    grownup()
    body = next_lesson()
    plan = body["lesson"]["hints"]
    prompt = body["content"]["prompt"]
    finish(body, typed(prompt, plan, latency_ms=9000) + typed(prompt, plan, latency_ms=200, correct=False))
    report = client.get("/api/parent/hints").json()
    assert report["mode"] == "auto" and report["supports"]
    lifted = [v for v in report["keys"].values() if v["lift"] is not None]
    assert lifted and all(v["lift"] == pytest.approx(1.0) for v in lifted)


def test_practice_lab_shows_hints_without_solo_lines():
    home_row_player()
    data = client.get("/api/practice/practice_fishing_v1/content", params={"keys": "home"}).json()
    assert data["hints"]["solo_lines"] == [] and data["hints"]["keys"]
