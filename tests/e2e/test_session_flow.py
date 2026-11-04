"""Real-browser e2e tests for the practice page: one brain-picked lesson
at a time, the result card, Enter for the next lesson, the wrong-streak
lockout, the daily goal's tokens, and practice resting once it's all
done. Each test gets its own server + temp DB via `live_server`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from playwright.sync_api import Page, expect

from app import db

from .conftest import unlock_grownups, place_on_home_row, start_practice_lesson, type_current_lesson


def set_goal(page: Page, live_server: str, minutes: int) -> None:
    unlock_grownups(page, live_server)
    resp = page.request.put(f"{live_server}/api/parent/settings", data={"goal_minutes": minutes, "learn_vs_practice": 0.5})
    assert resp.ok


def practiced_already(tmp_path, seconds: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        if db.latest_chunk(conn, 1) is None:
            db.create_chunk(conn, 1, datetime.now(UTC))
        conn.execute("UPDATE practice_chunk SET practiced_seconds = ? WHERE learner_id = 1", (seconds,))


def test_a_new_player_is_handed_to_the_intro_lesson(page: Page, live_server):
    page.goto(f"{live_server}/session")
    expect(page).to_have_url(re.compile(r"/teach/teach_intro_home_row_v1\?.*lesson=\d+"))
    expect(page.locator("#teach-title")).not_to_have_text("Loading…")


def test_a_warmup_opens_the_day_and_enter_goes_to_the_next_lesson(page: Page, live_server):
    start_practice_lesson(page, live_server)
    expect(page.locator(".stage-label")).to_have_text("Warmup")
    first = page.evaluate("lesson.lesson_id")
    type_current_lesson(page)
    expect(page.locator("#result-rewards")).to_contain_text("+100 coins")
    page.keyboard.press("Enter")
    page.wait_for_function(f"contentLoaded && lesson.lesson_id !== {first}")
    expect(page.locator(".stage-label")).to_have_text("Practice")


def test_progress_counter_advances_as_characters_are_typed(page: Page, live_server):
    start_practice_lesson(page, live_server)
    before = page.locator(".stage-progress").inner_text()
    page.keyboard.press("a")
    assert page.locator(".stage-progress").inner_text() != before


def test_end_now_scores_a_partial_lesson(page: Page, live_server):
    start_practice_lesson(page, live_server)
    page.keyboard.press(page.evaluate("view.expected"))
    page.click("#end-now-button")
    expect(page.locator("#lesson-result")).to_be_visible()
    assert "%" in page.locator("#result-summary").inner_text()


def test_wrong_streak_lockout_blocks_until_the_correct_key(page: Page, live_server):
    start_practice_lesson(page, live_server)
    prompt = page.evaluate("content.prompt")
    wrong_key = next(c for c in "zqxw" if c not in prompt)
    for _ in range(5):
        page.keyboard.press(wrong_key)
    expect(page.locator(".stage-hint")).to_contain_text("Get this one right")
    position_while_locked = page.evaluate("view.typed")
    expected = page.evaluate("view.expected")
    page.keyboard.press(wrong_key)
    assert page.evaluate("view.typed") == position_while_locked
    page.keyboard.press(expected)
    expect(page.locator(".stage-hint")).not_to_contain_text("Get this one right")
    assert page.evaluate("view.typed") == position_while_locked + 1


def test_escape_after_a_lesson_goes_home(page: Page, live_server):
    start_practice_lesson(page, live_server)
    type_current_lesson(page)
    page.keyboard.press("Escape")
    expect(page).to_have_url(re.compile(r"/$"))


def test_reaching_the_goal_pays_tokens_and_the_bonus_rests_practice(page: Page, live_server, tmp_path):
    place_on_home_row(page, live_server)
    set_goal(page, live_server, 2)
    practiced_already(tmp_path, 115)
    page.goto(f"{live_server}/session")
    expect(page.locator("#token-count")).to_have_text("0")
    type_current_lesson(page)
    expect(page.locator("#result-rewards")).to_contain_text("+2 arcade tokens")
    expect(page.locator("#token-count")).to_have_text("2")
    # it crossed half the goal too: a seed, and the garden got watered
    expect(page.locator(".topbar .day-chest.open")).to_have_count(2)
    expect(page.locator("#result-rewards")).to_contain_text("+1 seed")
    expect(page.locator("#seed-count")).to_have_text("1")
    expect(page.locator(".watering")).to_contain_text("garden got watered")

    practiced_already(tmp_path, 175)
    page.keyboard.press("Enter")
    type_current_lesson(page)
    expect(page.locator("#result-rewards")).to_contain_text("+1 arcade token")
    expect(page.locator("#arcade-button")).to_be_visible()
    expect(page.locator("#next-button")).to_be_hidden()

    page.goto(f"{live_server}/session")
    expect(page.locator("#rest-screen")).to_be_visible()
    expect(page.locator("#rest-until")).not_to_be_empty()


def test_a_learn_lesson_comes_back_to_practice(page: Page, live_server):
    from .test_teach_page import play_through

    page.goto(f"{live_server}/session")
    expect(page).to_have_url(re.compile(r"/teach/"))
    page.wait_for_function("typeof steps !== 'undefined' && steps.length > 0")
    play_through(page)
    expect(page.locator("#teach-next")).to_contain_text("next lesson")
    assert page.evaluate("fetch('/api/day').then(r => r.json()).then(d => d.practiced_seconds)") > 0
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"/teach/teach_key_pair_v1\?keys=fj"))  # F and J next
