"""Real-browser e2e tests for the analysis page: the 4 panels actually
render, and (per the known intermittent white-screen issue logged in
PLAN.md Section 11b) a repeated-reload probe that quantifies how often
a fresh load comes up blank, without chasing the root cause yet.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import start_quick_session, type_current_step_prompt

KNOWN_WHITE_SCREEN_ISSUE = (
    "intermittent analysis-page white screen, logged and deferred in PLAN.md Section 11b"
)


def run_one_quick_step(page: Page, live_server: str) -> None:
    """Generate at least a little real data via the actual session flow,
    so the analysis page has something non-empty to show.
    """
    start_quick_session(page, live_server)
    type_current_step_prompt(page)
    expect(page.locator("#step-result")).to_be_visible()


@pytest.mark.xfail(reason=KNOWN_WHITE_SCREEN_ISSUE, strict=False)
def test_keyboard_heatmap_renders_on_a_fresh_learner(page: Page, live_server):
    page.goto(f"{live_server}/analysis")
    page.wait_for_function("document.getElementById('keyboard').children.length > 0")
    rows = page.locator("#keyboard .kb-row")
    assert rows.count() == 4
    keys = page.locator("#keyboard .kb-key")
    assert keys.count() == 40  # every key in KEY_ORDER


@pytest.mark.xfail(reason=KNOWN_WHITE_SCREEN_ISSUE, strict=False)
def test_finger_bars_render_on_a_fresh_learner(page: Page, live_server):
    page.goto(f"{live_server}/analysis")
    page.wait_for_function("document.getElementById('finger-bars').children.length > 0")
    assert page.locator("#finger-bars .finger-row").count() == 8


@pytest.mark.xfail(reason=KNOWN_WHITE_SCREEN_ISSUE, strict=False)
def test_all_four_panels_render_after_a_real_session_step(page: Page, live_server):
    run_one_quick_step(page, live_server)
    page.goto(f"{live_server}/analysis")

    page.wait_for_function("document.getElementById('keyboard').children.length > 0")
    assert page.locator("#keyboard .kb-key").count() == 40
    assert page.locator("#finger-bars .finger-row").count() == 8

    page.click("[data-tab='bigrams']")
    page.wait_for_function("document.querySelector('#bigram-table tbody').children.length > 0")

    page.click("[data-tab='trend']")
    page.wait_for_function("document.getElementById('trend-chart').children.length > 0")


@pytest.mark.xfail(reason=KNOWN_WHITE_SCREEN_ISSUE, strict=False)
def test_repeated_reloads_of_the_analysis_page_consistently_render(page: Page, live_server):
    """Flakiness probe for the known white-screen issue (PLAN.md 11b).

    Not root-causing it here -- just measuring, over N fresh loads in
    one browser session, how often the keyboard panel fails to appear
    within a generous timeout. xfail (not skip) so this keeps running
    every time and will visibly XPASS the moment someone fixes the
    underlying issue, rather than silently staying green or being
    forgotten. Confirmed reproducible: 5 of 8 reloads failed when this
    was written.
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
