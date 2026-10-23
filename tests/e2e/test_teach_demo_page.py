"""Real-browser e2e tests for the teach-demo page: picking a module,
seeing the hand diagram render, typing through micro-steps, and
reaching a scored result for each of the 3 variants.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def run_full_lesson(page: Page, live_server: str, module_id: str) -> None:
    page.goto(f"{live_server}/teach-demo")
    page.select_option("#module-select", module_id)
    page.click("#start-button")
    expect(page.locator("#lesson-screen")).to_be_visible()

    for _ in range(10):  # generous upper bound; these are short lessons
        # diagram-only steps have no prompt and the "continue" button
        # is already enabled; typing steps need the prompt completed first.
        prompt_len = page.evaluate("promptChars.length")
        if prompt_len > 0:
            prompt = page.evaluate("promptChars.join('')")
            page.keyboard.type(prompt)
        expect(page.locator("#micro-step-result")).to_be_visible()
        is_last = page.evaluate("stepIndex >= microSteps.length - 1")
        page.click("#continue-button")
        if is_last:
            break

    expect(page.locator("#lesson-complete-screen")).to_be_visible()


def test_setup_screen_lists_all_three_modules(page: Page, live_server):
    page.goto(f"{live_server}/teach-demo")
    options = page.locator("#module-select option")
    assert options.count() == 3


def test_hand_diagram_renders_on_the_first_step(page: Page, live_server):
    page.goto(f"{live_server}/teach-demo")
    page.click("#start-button")
    expect(page.locator("#hand-diagram .dkey-highlight")).to_have_count(1)
    expect(page.locator("#hand-diagram .dfinger-active")).to_have_count(1)


def test_hand_anchor_demo_full_lesson_reaches_a_result(page: Page, live_server):
    run_full_lesson(page, live_server, "teach_hand_anchor_demo_v1")
    expect(page.locator("#final-result")).to_contain_text("%")


def test_reach_return_demo_full_lesson_reaches_a_result(page: Page, live_server):
    run_full_lesson(page, live_server, "teach_reach_return_demo_v1")
    expect(page.locator("#final-result")).to_contain_text("%")


def test_staged_combo_demo_full_lesson_reaches_a_result(page: Page, live_server):
    run_full_lesson(page, live_server, "teach_staged_combo_demo_v1")
    expect(page.locator("#final-result")).to_contain_text("%")


def test_try_another_button_returns_to_setup(page: Page, live_server):
    run_full_lesson(page, live_server, "teach_hand_anchor_demo_v1")
    page.click("#try-another-button")
    expect(page.locator("#setup-screen")).to_be_visible()
