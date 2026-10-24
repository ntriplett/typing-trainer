"""Real-browser e2e tests for the profile hub and character designer
(PLAN.md 11c-2, phase 1)."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_header_avatar_menu_opens_the_profile_hub(page: Page, live_server):
    page.goto(live_server)
    page.click(".topbar-avatar")
    expect(page.locator(".profile-menu-name")).to_have_text("Tester")
    page.locator(".profile-menu").get_by_role("link", name="My profile").click()
    expect(page).to_have_url(f"{live_server}/profile")
    expect(page.locator("#stats .stat")).to_have_count(5)
    expect(page.locator(".hub-tile[href='/store']")).to_be_visible()


def test_designer_click_saves_the_look(page: Page, live_server):
    page.goto(f"{live_server}/designer")
    page.get_by_role("button", name="Girl").click()
    expect(page.locator("#designer-status")).to_have_text("Saved!")
    page.reload()
    expect(page.get_by_role("button", name="Girl")).to_have_class("choice selected")


def test_locked_dye_swatch_is_marked_locked(page: Page, live_server):
    page.goto(f"{live_server}/designer")
    expect(page.locator("#choices-hair_color .swatch-choice.locked").first).to_be_visible()


def test_rename(page: Page, live_server):
    page.goto(f"{live_server}/designer")
    expect(page.locator("#name-input")).to_have_value("Tester")  # loaded; CI was racing this
    page.fill("#name-input", "Robin")
    page.click("#name-form button")
    expect(page.locator("#designer-status")).to_have_text("Hi, Robin!")
    page.goto(f"{live_server}/profile")
    expect(page.locator("#profile-name")).to_have_text("Robin")


def test_eye_color_choice_saves(page: Page, live_server):
    page.goto(f"{live_server}/designer")
    page.locator("#choices-eye_color .swatch-choice").nth(1).click()
    expect(page.locator("#designer-status")).to_have_text("Saved!")
    assert page.evaluate("fetch('/api/me').then(r => r.json()).then(d => d.avatar.appearance.eye_color)") == "blue"
