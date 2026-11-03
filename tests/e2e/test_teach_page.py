"""Real-browser e2e tests for the keyboard-driven teach page: the whole
intro lesson runs on key presses alone (no mouse), wrong keys don't move
on, and the ghost hands light the right finger.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

INTRO = "teach_intro_home_row_v1"
PAIR = "teach_key_pair_v1"


def open_lesson(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_function("steps.length > 0 && !busy")


def press_with_right_shift(page: Page, key: str) -> None:
    """A capital is pressed holding the other hand's Shift, like a learner would."""
    if key.isupper():
        side = "ShiftRight" if key.lower() in "qwertasdfgzxcvb" else "ShiftLeft"
        page.keyboard.press(f"{side}+{key}")
    else:
        page.keyboard.press(key)


def open_intro(page: Page, live_server: str) -> None:
    open_lesson(page, f"{live_server}/teach/{INTRO}")


def play_through(page: Page) -> None:
    """Every step by keyboard only: the advance key, or the whole prompt."""
    for _ in range(40):
        if page.evaluate("finished"):
            break
        step = page.evaluate("steps[stepIndex]")
        if step["kind"] == "show":
            press_with_right_shift(page, step["advance_key"])
        else:
            page.keyboard.type(page.evaluate("view.typeable"))
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
    expect(page.locator(".lab-group h2")).to_have_text(
        ["Start here", "Home row", "Top row", "Bottom row", "Numbers", "Capitals"]
    )
    page.get_by_role("link", name="C and ,").click()
    expect(page).to_have_url(f"{live_server}/teach/{PAIR}?keys=c%2C")
    expect(page.locator("#teach-title")).to_contain_text("Two new keys!")


def test_long_prompt_wraps_between_words_one_line_at_a_time(page: Page, live_server):
    open_intro(page, live_server)
    lines = page.evaluate(
        "(() => { const v = new PromptView(document.getElementById('teach-lines'));"
        " document.getElementById('teach-lines').hidden = false;"
        " document.getElementById('teach-lines').style.width = '300px';"
        " v.load('salad flask dad asks a lass all fall'); return v.lines.map(l => l.map(i => v.chars[i]).join('')); })()"
    )
    assert len(lines) > 1
    for line in lines:
        assert not line.startswith(" ") and not line.endswith(" ")
    assert " ".join(lines) == "salad flask dad asks a lass all fall"


def test_spaces_are_plain_gaps_and_a_missed_one_is_boxed(page: Page, live_server):
    open_intro(page, live_server)
    for key in (" ", "f", "j", "a"):  # up to the first type step: "a s d f"
        page.keyboard.press(key)
        wait_ready(page)
    page.keyboard.press("a")
    space = page.locator("#teach-lines .prompt-current .space").first
    expect(space).to_have_text(" ")
    expect(space).to_have_class(re.compile("current"))
    page.keyboard.press("x")
    expect(space).to_have_class(re.compile("missed"))


def test_caps_lesson_lights_the_other_shift_and_plays_through(page: Page, live_server):
    open_lesson(page, f"{live_server}/teach/teach_caps_v1?keys=asdf")
    page.keyboard.press(" ")
    wait_ready(page)
    expect(page.locator("#teach-title")).to_contain_text("Big")
    expect(page.locator('#teach-keyboard .tk-target[data-key="shift_r"]')).to_have_count(1)
    expect(page.locator('#teach-keyboard .tk-finger-lit-fill [data-finger="right_pinky"]')).to_have_count(1)
    play_through(page)
    expect(page.locator("#teach-result")).to_contain_text("100%")


def test_caps_wrong_shift_or_no_shift_is_caught(page: Page, live_server):
    open_lesson(page, f"{live_server}/teach/teach_caps_intro_v1")
    for _ in range(2):
        page.keyboard.press(" ")
        wait_ready(page)
    expect(page.locator("#teach-title")).to_contain_text("Big")  # Big J: needs LEFT shift
    page.keyboard.press("j")
    expect(page.locator("#teach-hint")).to_contain_text("Hold left")
    page.keyboard.press("ShiftRight+J")
    expect(page.locator("#teach-hint")).to_contain_text("other Shift")
    expect(page.locator("#teach-title")).to_contain_text("Big")
    page.keyboard.press("ShiftLeft+J")
    wait_ready(page)
    expect(page.locator("#teach-title .keycap")).to_have_text("F")
