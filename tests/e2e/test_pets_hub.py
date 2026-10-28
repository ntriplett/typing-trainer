"""Real-browser e2e tests for the Pets hub (PLAN.md 11h): open from the
start, buildings to visit, and news on the shop's door."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from .conftest import place_on_home_row


def test_the_pets_hub_is_open_from_the_start(page: Page, live_server):
    page.goto(live_server)
    expect(page.locator("#pets-name")).to_have_text("Pets")
    page.locator(".tile-pets").click()
    expect(page.locator("h1")).to_have_text("Pets")
    expect(page.locator(".hub-building")).to_have_count(4)
    expect(page.locator("#hub-pets")).to_contain_text("No pets yet")
    page.locator("[data-building='aquarium']").click()
    expect(page.locator("#hub-message")).to_contain_text("Aquarium is still being built")
    page.locator("[data-building='shop']").click()
    expect(page).to_have_url(f"{live_server}/pets/shop?dept=fish")
    page.get_by_role("link", name="← Pets").click()
    expect(page.locator("#hub-canvas")).to_be_visible()


def test_the_shop_door_shows_the_free_pet(page: Page, live_server):
    place_on_home_row(page, live_server)
    page.goto(live_server)
    expect(page.locator("#pets-sub")).to_have_text("A free pet is waiting!")
    page.goto(f"{live_server}/pets")
    expect(page.locator("[data-building='shop'] .hub-news")).to_contain_text("free pet")


def test_the_care_center_and_trailhead_doors_open(page: Page, live_server):
    page.goto(f"{live_server}/pets")
    page.locator("[data-building='care']").click()
    expect(page.locator("h1")).to_have_text("Pet Care Center")
    page.goto(f"{live_server}/pets")
    page.locator("[data-building='trailhead']").click()
    expect(page.locator("h1")).to_have_text("Trailhead")
