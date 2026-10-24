"""Real-browser e2e tests for picking/creating players and the wardrobe
(PLAN.md 11d)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.no_player
def test_no_player_goes_to_welcome_and_new_player_flow(page: Page, live_server):
    page.goto(live_server)
    expect(page).to_have_url(f"{live_server}/welcome")
    expect(page.locator("#new-player")).to_be_visible()  # nobody exists yet

    page.fill("#new-name", "Robin")
    page.click("#new-player-form button")
    expect(page).to_have_url(f"{live_server}/designer?setup=1")
    page.get_by_role("link", name="Next →").click()

    expect(page).to_have_url(f"{live_server}/placement")
    page.get_by_role("button", name="The home row (asdf jkl;)").click()
    page.get_by_role("button", name="Pretty comfy").click()
    page.click("#placement-done")
    expect(page).to_have_url(f"{live_server}/")
    expect(page.locator(".profile-menu-name")).to_have_text("Robin")


def test_switch_player_and_pick_from_the_list(page: Page, live_server):
    page.request.post(f"{live_server}/api/profiles", data={"name": "Sam"})  # now playing as Sam
    page.goto(live_server)
    page.click(".topbar-avatar")
    page.click(".switch-player")
    expect(page).to_have_url(f"{live_server}/welcome")
    page.locator(".player-card", has_text="Tester").click()
    expect(page).to_have_url(f"{live_server}/")
    expect(page.locator(".profile-menu-name")).to_have_text("Tester")


def test_wardrobe_changes_into_owned_clothes(page: Page, live_server, tmp_path):
    from app import db, store

    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, store.CATALOG["shirt_tee_blue"].price, "test")
    page.request.post(f"{live_server}/api/store/buy/shirt_tee_blue")  # bought, not worn

    page.goto(f"{live_server}/wardrobe")
    tunic = page.locator(".wardrobe-choice[data-item-id='shirt_tunic']")
    expect(tunic).to_have_class("choice wardrobe-choice selected")
    page.locator(".wardrobe-choice[data-item-id='shirt_tee_blue']").click()
    expect(page.locator(".wardrobe-choice[data-item-id='shirt_tee_blue']")).to_have_class("choice wardrobe-choice selected")
    assert page.evaluate("fetch('/api/me').then(r => r.json()).then(d => d.avatar.shirt)") == "shirt_tee_blue"
