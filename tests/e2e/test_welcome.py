"""Real-browser e2e tests for picking/creating players and getting dressed
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
    expect(page).to_have_url(f"{live_server}/bedroom?room=mirror&setup=1")  # set up your look at the mirror
    page.locator("#room-nav").get_by_role("button", name="Next").click()

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


def test_the_closet_changes_into_owned_clothes(page: Page, live_server, tmp_path):
    from app import db, store

    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, store.CATALOG["shirt_tee_blue"].price, "test")
    page.request.post(f"{live_server}/api/store/buy/shirt_tee_blue")  # bought, not worn

    page.goto(f"{live_server}/wardrobe")  # the old page: now the Home's closet
    expect(page).to_have_url(f"{live_server}/bedroom?room=closet")
    page.locator("[data-spot='shirt_tee_blue']").click()
    page.wait_for_function("fetch('/api/me').then(r => r.json()).then(d => d.avatar.shirt === 'shirt_tee_blue')")
