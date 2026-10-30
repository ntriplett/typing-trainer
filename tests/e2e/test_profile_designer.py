"""Real-browser e2e tests for the profile page and changing your look at
the Home's vanity mirror (PLAN.md 11c-2, phase 1)."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_header_avatar_menu_opens_the_profile_page(page: Page, live_server):
    page.goto(live_server)
    page.click(".topbar-avatar")
    expect(page.locator(".profile-menu-name")).to_have_text("Tester")
    page.locator(".profile-menu").get_by_role("link", name="My profile").click()
    expect(page).to_have_url(f"{live_server}/profile")
    expect(page.locator("#stats .stat")).to_have_count(5)


def _look(page: Page, field: str) -> str:
    return page.evaluate(f"fetch('/api/me').then(r => r.json()).then(d => d.avatar.appearance.{field})")


def _mirror(page: Page, live_server) -> None:
    page.goto(f"{live_server}/bedroom?room=mirror")
    expect(page.locator("#name-plate")).to_have_value("Tester")  # loaded


def test_clicking_a_portrait_at_the_mirror_saves_the_look(page: Page, live_server):
    _mirror(page, live_server)
    page.locator("[data-spot='gender-girl']").click()
    page.wait_for_function("fetch('/api/me').then(r => r.json()).then(d => d.avatar.appearance.gender === 'girl')")


def test_a_locked_dye_points_to_the_store(page: Page, live_server):
    _mirror(page, live_server)
    page.locator("[data-spot='hair_color-blue']").click()
    expect(page.locator("#room-message")).to_contain_text("store")
    assert _look(page, "hair_color") != "blue"


def test_rename_at_the_name_plate(page: Page, live_server):
    _mirror(page, live_server)
    page.fill("#name-plate", "Robin")
    page.locator("#name-plate").press("Enter")
    expect(page.locator("#room-message")).to_have_text("Hi, Robin!")
    page.goto(f"{live_server}/profile")
    expect(page.locator("#profile-name")).to_have_text("Robin")


def test_eye_color_choice_saves(page: Page, live_server):
    _mirror(page, live_server)
    page.locator("[data-spot='eye_color-blue']").click()
    page.wait_for_function("fetch('/api/me').then(r => r.json()).then(d => d.avatar.appearance.eye_color === 'blue')")
