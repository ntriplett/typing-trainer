"""Real-browser e2e tests for the keyboard-driven teach page: the whole
intro lesson runs on key presses alone (no mouse), wrong keys don't move
on, and the ghost hands light the right finger.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

INTRO = "teach_intro_home_row_v1"
PAIR = "teach_key_pair_v1"


def open_lesson(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_function("steps.length > 0 && !busy")


def open_intro(page: Page, live_server: str) -> None:
    open_lesson(page, f"{live_server}/teach/{INTRO}")


def play_through(page: Page) -> None:
    """Every step by keyboard only: the advance key, or the whole prompt."""
    for _ in range(40):
        if page.evaluate("finished"):
            break
        step = page.evaluate("steps[stepIndex]")
        if step["kind"] == "show":
            page.keyboard.press(step["advance_key"])
        else:
            page.keyboard.type(step["prompt"])
        page.wait_for_function("busy === false || finished")
    expect(page.locator("#teach-done")).to_be_visible()


def wait_ready(page: Page) -> None:
    page.wait_for_function("!busy")


def test_hands_and_keyboard_render(page: Page, live_server):
    open_intro(page, live_server)
    expect(page.locator("#teach-keyboard .tk-key")).to_have_count(61)
    expect(page.locator("#teach-keyboard .tk-hand-fill line")).to_have_count(8)
    # first step: both thumbs lit, space bar lit
    expect(page.locator("#teach-keyboard .tk-finger-lit-fill line")).to_have_count(2)
    expect(page.locator('#teach-keyboard .tk-target[data-key=" "]')).to_have_count(1)


def test_wrong_key_on_a_show_step_hints_and_stays(page: Page, live_server):
    open_intro(page, live_server)
    page.keyboard.press(" ")
    wait_ready(page)
    expect(page.locator("#teach-title")).to_have_text("Find the bumps")
    page.keyboard.press("d")
    expect(page.locator("#teach-hint")).to_contain_text("left pointer finger")
    expect(page.locator("#teach-title")).to_have_text("Find the bumps")
    expect(page.locator('#teach-keyboard .tk-finger-lit-fill [data-finger="left_index"]')).to_have_count(1)


def test_typing_highlights_the_next_finger(page: Page, live_server):
    open_intro(page, live_server)
    for key in (" ", "f", "j", "a"):  # up to the first type step: "a s d f"
        page.keyboard.press(key)
        wait_ready(page)
    expect(page.locator('#teach-keyboard .tk-finger-lit-fill [data-finger="left_pinky"]')).to_have_count(1)
    page.keyboard.press("a")
    expect(page.locator('#teach-keyboard .tk-finger-lit-fill [data-finger="left_thumb"]')).to_have_count(1)


def test_whole_lesson_runs_on_the_keyboard_alone(page: Page, live_server):
    open_intro(page, live_server)
    play_through(page)
    expect(page.locator("#teach-result")).to_contain_text("100%")
    expect(page.locator("#teach-coins")).to_have_text("+250 coins!")
    # Space goes again
    page.keyboard.press(" ")
    page.wait_for_function("typeof steps !== 'undefined' && steps.length > 0 && !finished")
    expect(page.locator("#teach-title")).to_have_text("Welcome!")


def test_reach_lesson_moves_the_finger_to_the_key(page: Page, live_server):
    open_lesson(page, f"{live_server}/teach/{PAIR}?keys=ru")
    expect(page.locator("#teach-title")).to_contain_text("Two new keys!")
    page.keyboard.press(" ")
    wait_ready(page)
    expect(page.locator("#teach-title .keycap")).to_have_text("R")
    # the lit left pointer finger's tip has moved up onto R
    page.wait_for_timeout(400)
    tip_y = page.evaluate(
        "+document.querySelector('.tk-finger-lit-fill [data-finger=left_index]').getAttribute('y2')"
    )
    r_key_y = page.evaluate("kb.keys.get('r').cy")
    assert abs(tip_y - r_key_y) < 2


def test_pair_lesson_plays_through_and_pays_coins(page: Page, live_server):
    open_lesson(page, f"{live_server}/teach/{PAIR}?keys=ei")
    play_through(page)
    expect(page.locator("#teach-coins")).to_have_text("+100 coins!")
    page.keyboard.press("Enter")
    expect(page).to_have_url(f"{live_server}/teach-lab")


def test_lab_lists_lessons_by_row(page: Page, live_server):
    page.goto(f"{live_server}/teach-lab")
    expect(page.locator(".lab-group h2")).to_have_text(["Start here", "Home row", "Top row", "Bottom row", "Numbers"])
    page.get_by_role("link", name="C and ,").click()
    expect(page).to_have_url(f"{live_server}/teach/{PAIR}?keys=c%2C")
    expect(page.locator("#teach-title")).to_contain_text("Two new keys!")
