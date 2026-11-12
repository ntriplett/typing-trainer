"""Real-browser e2e tests for place themes and night mode (PLAN.md 11c-2,
phase 2)."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db, store


def _give_coins(tmp_path, amount: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, amount, "test")


def test_a_place_rethemes_the_page(page: Page, live_server, tmp_path):
    page.goto(live_server)
    expect(page.locator(".particles span").first).to_be_attached()
    default_bar = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--topbar')")
    _give_coins(tmp_path, store.CATALOG["bg_under_sea"].price)

    page.goto(f"{live_server}/store")
    page.click("[data-tab='places']")
    page.locator('.item-card[data-item-id="bg_under_sea"]').get_by_role("button", name="Buy").click()
    expect(page.locator('.item-card[data-item-id="bg_under_sea"]')).to_have_class("item-card equipped")
    bar = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--topbar')")
    assert bar != default_bar


def test_night_toggle_appears_once_unlocked_and_switches_to_dark(page: Page, live_server, tmp_path):
    page.goto(live_server)
    expect(page.locator(".night-toggle")).to_be_hidden()
    _give_coins(tmp_path, store.CATALOG["night_forests"].price)

    page.goto(f"{live_server}/store")
    page.click("[data-tab='night']")
    page.locator('.item-card[data-item-id="night_forests"]').get_by_role("button", name="Buy").click()
    expect(page.locator("html")).to_have_attribute("data-night", "")

    page.click(".night-toggle")
    expect(page.locator("html")).not_to_have_attribute("data-night", "")
    expect(page.locator(".night-toggle")).to_have_text("🌙")


def test_typing_page_has_no_particles(page: Page, live_server):
    page.goto(f"{live_server}/session")
    expect(page.locator("#coin-count")).to_be_visible()
    assert page.locator(".particles").count() == 0


def test_your_place_is_drawn_behind_every_page(page: Page, live_server):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live_server)
    expect(page.locator("canvas.scenery")).to_have_count(1)
    assert page.evaluate("Scenery.place") == "bg_meadow"
    for path in ("/session", "/game/game_crow_patrol_v1", "/wanderpaw", "/analysis", "/parent", "/arcade",
                 "/game-lab", "/practice-lab", "/teach-lab", "/wander-lab"):
        page.goto(f"{live_server}{path}")
        if path == "/session":
            page.wait_for_url("**/teach/**")  # a new player is sent on to their first lesson: let it finish first
        expect(page.locator("canvas.scenery")).to_have_count(1)
    assert errors == []

