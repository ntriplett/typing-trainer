"""Real-browser e2e tests for the session flow: config screen, typing
through steps, the progress bar, the idle-pause timer, the wrong-streak
lockout, and navigation. Each test gets its own server + temp DB via
the `live_server` fixture in conftest.py.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def start_quick_session(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/session")
    page.check("#quick-test-checkbox")
    page.click("#start-button")
    expect(page.locator("#session-screen")).to_be_visible()


def type_current_step_prompt(page: Page) -> None:
    """Type the full, correct prompt for whichever step is active."""
    page.wait_for_function("typeof stepIndex !== 'undefined' && !!contentCache[stepIndex]")
    prompt = page.evaluate("contentCache[stepIndex].prompt")
    page.keyboard.type(prompt)


def run_full_quick_session(page: Page, live_server: str) -> None:
    start_quick_session(page, live_server)
    for _ in range(30):  # generous upper bound; real sessions are ~10 steps
        type_current_step_prompt(page)
        expect(page.locator("#step-result")).to_be_visible()
        is_last = "summary" in page.locator("#next-button").inner_text().lower()
        page.click("#next-button")
        if is_last:
            break
    expect(page.locator("#complete-screen")).to_be_visible()


def test_start_screen_shows_the_three_config_sliders(page: Page, live_server):
    page.goto(f"{live_server}/session")
    expect(page.locator("#duration-slider")).to_be_visible()
    expect(page.locator("#learn-practice-slider")).to_be_visible()
    expect(page.locator("#focus-slider")).to_be_visible()
    expect(page.locator("#start-button")).to_be_visible()


def test_duration_slider_updates_its_live_label(page: Page, live_server):
    page.goto(f"{live_server}/session")
    page.locator("#duration-slider").fill("25")
    expect(page.locator("#duration-value")).to_have_text("25")


def test_full_quick_session_reaches_the_summary_screen(page: Page, live_server):
    run_full_quick_session(page, live_server)
    # summary should list one result line per completed step
    items = page.locator("#summary-list li")
    assert items.count() >= 4


def test_plan_preview_marks_steps_done_as_the_session_progresses(page: Page, live_server):
    start_quick_session(page, live_server)
    # before finishing step 0, it should show as "current"
    assert "current" in page.locator("#plan-preview .plan-phase").first.get_attribute("class")

    type_current_step_prompt(page)
    expect(page.locator("#step-result")).to_be_visible()
    page.click("#next-button")

    # the first phase chip should now read "done"
    first_chip_class = page.locator("#plan-preview .plan-phase").first.get_attribute("class")
    assert "done" in first_chip_class


def test_progress_counter_advances_as_characters_are_typed(page: Page, live_server):
    start_quick_session(page, live_server)
    before = page.locator("#progress").inner_text()
    page.keyboard.press("a")  # one keystroke, right or wrong doesn't matter for the counter
    after = page.locator("#progress").inner_text()
    assert before != after


def test_end_now_scores_a_partial_step_instead_of_the_full_prompt(page: Page, live_server):
    start_quick_session(page, live_server)
    prompt = page.evaluate("contentCache[stepIndex].prompt")
    # type only the first real character, correctly
    page.keyboard.press(prompt.strip()[0])
    page.click("#end-now-button")
    expect(page.locator("#step-result")).to_be_visible()
    summary = page.locator("#result-summary").inner_text()
    assert "%" in summary  # a real (if tiny) accuracy was computed, not skipped


def test_wrong_streak_lockout_blocks_until_the_correct_key(page: Page, live_server):
    start_quick_session(page, live_server)
    prompt = page.evaluate("contentCache[stepIndex].prompt")
    # The first 4 wrong presses still ADVANCE position (only the 5th
    # one in a row actually locks) -- so pick a wrong_key that's wrong
    # for every position we'll pass through, and read the real
    # "expected" character only after the lock has actually engaged.
    wrong_key = next(c for c in "zqxw" if c not in prompt)

    for _ in range(5):
        page.keyboard.press(wrong_key)

    expect(page.locator("#lock-message")).to_be_visible()
    position_while_locked = page.evaluate("position")
    expected = page.evaluate("contentCache[stepIndex].prompt[position]")

    # more wrong keys while locked must not advance anything
    page.keyboard.press(wrong_key)
    assert page.evaluate("position") == position_while_locked

    # the correct key unlocks and advances
    page.keyboard.press(expected)
    expect(page.locator("#lock-message")).to_be_hidden()
    assert page.evaluate("position") == position_while_locked + 1


def test_home_button_navigates_to_the_home_page(page: Page, live_server):
    start_quick_session(page, live_server)
    page.click("#home-button")
    expect(page).to_have_url(re.compile(r"/$"))


def test_complete_screen_offers_home_and_new_session(page: Page, live_server):
    run_full_quick_session(page, live_server)
    expect(page.locator("#complete-home-button")).to_be_visible()
    expect(page.locator("#complete-new-session-button")).to_be_visible()
    page.click("#complete-home-button")
    expect(page).to_have_url(re.compile(r"/$"))
