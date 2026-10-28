"""Real-browser e2e tests for pets (PLAN.md 11c-2, phase 4): adopt in the
store, then name and feed in the pet room."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db, pets

from .conftest import place_on_home_row


def _give_coins(tmp_path, amount: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, amount, "test")


def test_adopt_then_name_and_feed(page: Page, live_server, tmp_path):
    place_on_home_row(page, live_server)  # opens the pet room
    page.goto(live_server)
    expect(page.locator("#coin-count")).to_have_text("0")
    _give_coins(tmp_path, pets.FOOD_PRICE)

    page.goto(f"{live_server}/pets/room")
    expect(page.locator("#pet-cards")).to_contain_text("Your first pet is free")
    page.get_by_role("link", name="Pick your pet").click()
    expect(page.locator(".item-card[data-species='cat']")).to_contain_text("Free!")
    page.locator('.item-card[data-species="cat"]').get_by_role("button", name="Adopt for free").click()
    expect(page.locator("#store-message")).to_contain_text("Welcome home")

    page.goto(f"{live_server}/pets/room")
    card = page.locator(".pet-card").first
    card.locator(".pet-name").fill("Whiskers")
    card.get_by_role("button", name="Rename").click()
    expect(page.locator(".pet-card .pet-name").first).to_have_value("Whiskers")

    page.locator(".pet-card").first.get_by_role("button", name="Feed (100)").click()
    expect(page.locator(".pet-card").first.get_by_role("button", name="Fed today ✓")).to_be_disabled()
    expect(page.locator("#coin-count")).to_have_text("0")


def test_the_pet_room_is_a_mystery_until_the_home_row(page: Page, live_server):
    page.goto(f"{live_server}/pets/room")
    expect(page.locator(".mystery h1")).to_have_text("A mystery room!")
    expect(page.locator(".mystery")).to_contain_text("home row")
    page.goto(f"{live_server}/store")
    expect(page.locator("[data-tab='pets']")).to_have_count(0)
    expect(page.locator("[data-tab='bedroom']")).to_have_count(0)
    page.goto(live_server)
    expect(page.locator("#pets-name")).to_have_text("Pets")  # the Pets hub is open from the start
    expect(page.locator("#bedroom-name")).to_have_text("Mystery")


def test_after_the_free_pet_the_next_one_costs_coins(page: Page, live_server):
    place_on_home_row(page, live_server)
    page.request.post(f"{live_server}/api/pets/adopt", data={"species": "cat", "color": "orange"})
    page.goto(f"{live_server}/store?tab=pets")
    expect(page.locator(".item-card[data-species='dog']")).not_to_contain_text("Free!")
    page.goto(live_server)
    expect(page.locator("#pets-name")).to_have_text("Pets")
