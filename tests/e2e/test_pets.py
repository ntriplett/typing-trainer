"""Real-browser e2e tests for pets (PLAN.md 11c-2, phase 4): adopt in the
store, then name and feed in the pet room."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db, pets


def _give_coins(tmp_path, amount: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, amount, "test")


def test_adopt_then_name_and_feed(page: Page, live_server, tmp_path):
    page.goto(live_server)
    expect(page.locator("#coin-count")).to_have_text("0")
    _give_coins(tmp_path, pets.SPECIES["cat"].price + pets.FOOD_PRICE)

    page.goto(f"{live_server}/store")
    page.click("[data-tab='pets']")
    page.locator('.item-card[data-species="cat"]').get_by_role("button", name="Adopt").click()
    expect(page.locator("#store-message")).to_contain_text("Welcome home")

    page.goto(f"{live_server}/pets")
    card = page.locator(".pet-card").first
    card.locator(".pet-name").fill("Whiskers")
    card.get_by_role("button", name="Rename").click()
    expect(page.locator(".pet-card .pet-name").first).to_have_value("Whiskers")

    page.locator(".pet-card").first.get_by_role("button", name="Feed (100)").click()
    expect(page.locator(".pet-card").first.get_by_role("button", name="Fed today ✓")).to_be_disabled()
    expect(page.locator("#coin-count")).to_have_text("0")


def test_empty_pet_room_points_to_the_store(page: Page, live_server):
    page.goto(f"{live_server}/pets")
    expect(page.locator("#pet-cards")).to_contain_text("No pets yet")
