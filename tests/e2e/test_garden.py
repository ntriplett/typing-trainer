"""Real-browser e2e tests for the garden: the seed pill, planting and
picking by keyboard, the basket, and the home tile."""

from __future__ import annotations

from datetime import UTC, datetime

from playwright.sync_api import Page, expect

from app import db, garden


def give_seeds(tmp_path, n: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_seeds(conn, 1, n, "test")


def test_the_seed_pill_is_in_the_top_bar(page: Page, live_server, tmp_path):
    give_seeds(tmp_path, 2)
    page.goto(f"{live_server}/store")
    expect(page.locator("#seed-count")).to_have_text("2")


def test_plant_by_keyboard_then_pick_after_watering(page: Page, live_server, tmp_path):
    give_seeds(tmp_path, 1)
    page.goto(f"{live_server}/garden")
    expect(page.locator(".garden-spot")).to_have_count(garden.SPOTS)
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(page.locator("#garden-message")).to_contain_text("planted")
    expect(page.locator("#seed-count")).to_have_text("0")
    expect(page.locator(".garden-spot").nth(1)).to_contain_text("5 growing")

    with db.open_db(tmp_path / "e2e.db") as conn:
        garden.water(conn, 1, datetime.now(UTC))
    page.reload()
    expect(page.locator(".garden-spot.ripe")).to_have_count(1)
    page.keyboard.press("Enter")  # the cursor starts on the ripe plant
    expect(page.locator("#garden-message")).to_contain_text("You picked 1")
    expect(page.locator("#pantry-list .veggie-chip")).to_have_count(1)


def test_collect_the_basket_with_b(page: Page, live_server, tmp_path):
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_to_basket(conn, 1, "corn", 3)
    page.goto(f"{live_server}/garden")
    expect(page.locator("#basket-button")).to_be_visible()
    page.keyboard.press("b")
    expect(page.locator("#garden-message")).to_contain_text("3 veggies")
    expect(page.locator("#pantry-list")).to_contain_text("3")
    expect(page.locator("#basket-button")).to_be_hidden()


def test_home_garden_tile_says_what_to_do(page: Page, live_server, tmp_path):
    page.goto(live_server)
    expect(page.locator("#garden-sub")).to_have_text("Practice for a seed")
    give_seeds(tmp_path, 1)
    page.reload()
    expect(page.locator("#garden-sub")).to_have_text("Plant your seed!")
