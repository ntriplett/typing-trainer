"""Real-browser e2e tests for the analysis page: the 4 panels actually
render, plus a repeated-reload regression probe for the intermittent
white-screen bug (PLAN.md Section 11b, fixed: cross-thread sqlite use).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from .conftest import start_quick_session, type_current_step_prompt


def run_one_quick_step(page: Page, live_server: str) -> None:
    """Generate at least a little real data via the actual session flow,
    so the analysis page has something non-empty to show.
    """
    start_quick_session(page, live_server)
    type_current_step_prompt(page)
    expect(page.locator("#step-result")).to_be_visible()


def test_keyboard_heatmap_renders_on_a_fresh_learner(page: Page, live_server):
    page.goto(f"{live_server}/analysis")
    page.wait_for_function("document.getElementById('keyboard').children.length > 0")
    rows = page.locator("#keyboard .kb-row")
    assert rows.count() == 5  # 4 key rows + the space bar
    keys = page.locator("#keyboard .kb-key")
    assert keys.count() == 41  # every key in KEY_ORDER, space included


def test_finger_bars_render_on_a_fresh_learner(page: Page, live_server):
    page.goto(f"{live_server}/analysis")
    page.wait_for_function("document.getElementById('finger-bars').children.length > 0")
    assert page.locator("#finger-bars .finger-row").count() == 9  # 8 fingers + thumbs


def test_all_four_panels_render_after_a_real_session_step(page: Page, live_server):
    run_one_quick_step(page, live_server)
    page.goto(f"{live_server}/analysis")

    page.wait_for_function("document.getElementById('keyboard').children.length > 0")
    assert page.locator("#keyboard .kb-key").count() == 41
    assert page.locator("#finger-bars .finger-row").count() == 9

    page.click("[data-tab='bigrams']")
    page.wait_for_function("document.querySelector('#bigram-table tbody').children.length > 0")

    page.click("[data-tab='trend']")
    page.wait_for_function("document.getElementById('trend-chart').children.length > 0")


def test_repeated_reloads_of_the_analysis_page_consistently_render(page: Page, live_server):
    """Regression probe for the white-screen bug (PLAN.md 11b): before
    the fix, 5 of 8 fresh loads failed because the page's 4 parallel
    fetches hit sqlite connections used across threadpool threads.
    """
    failures = []
    for i in range(8):
        page.goto(f"{live_server}/analysis")
        try:
            page.wait_for_function(
                "document.getElementById('keyboard').children.length > 0", timeout=2000
            )
        except Exception:
            failures.append(i)

    assert not failures, f"analysis page failed to render keyboard on reloads {failures} of 8"
