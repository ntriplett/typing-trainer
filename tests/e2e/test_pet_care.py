"""Real-browser e2e tests for the Pet Care Center book (PLAN.md 11i):
picking a pet, renaming, feeding a garden veggie, moving it into a
habitat bought in the Pet Shop, and bringing it along."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db
from app import pet_genes as g


def _setup(tmp_path, pets=("dog", "cat"), **veggies) -> list[int]:
    with db.open_db(tmp_path / "e2e.db") as conn:
        ids = [db.add_v3_pet(conn, 1, g.roll(sp, None, None, 10 + i), sp.capitalize(), "shop") for i, sp in enumerate(pets)]
        for kind, n in veggies.items():
            db.add_veggies(conn, 1, kind, n, "test")
        return ids


def test_an_empty_book_points_to_the_shop(page: Page, live_server):
    page.goto(f"{live_server}/pets/care")
    expect(page.locator("#book-grid")).to_contain_text("Visit the Pet Shop")


def test_rename_and_feed_a_pet(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/pets/care")  # makes the player
    dog, _ = _setup(tmp_path, carrot=1)
    page.goto(f"{live_server}/pets/care?pet={dog}")
    expect(page.locator(".book-pet")).to_have_count(2)
    expect(page.locator("#book-detail h2")).to_have_text("Dog")
    page.get_by_role("button", name="✏️ Rename").click()
    page.locator("#rename-input").fill("Biscuit")
    page.keyboard.press("Enter")
    expect(page.locator("#book-detail h2")).to_have_text("Biscuit")
    expect(page.locator(".book-pet.current")).to_contain_text("Biscuit")

    page.get_by_role("button", name="🥕 Feed").click()
    page.locator("[data-veggie='carrot']").click()
    expect(page.locator("#care-message")).to_contain_text("Biscuit grew")
    expect(page.get_by_role("button", name="Full for today")).to_be_disabled()
    expect(page.locator(".growth")).to_contain_text("/10")


def test_move_into_a_meadow_and_bring_along(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/pets/shop?dept=habitats")
    page.get_by_role("button", name="Get it free!").click()
    page.get_by_role("button", name="Yes, get it!").click()
    expect(page.locator("#dept-hint")).to_contain_text("Your Meadow is ready")
    dog, cat = _setup(tmp_path)
    page.goto(f"{live_server}/pets/care?pet={cat}")
    page.get_by_role("button", name="🏡 Move to a habitat").click()
    page.get_by_role("button", name="Meadow (0/6)").click()
    expect(page.locator(".detail-facts")).to_contain_text("Lives in Meadow")
    page.locator("#care-filter").select_option("spot:0")
    expect(page.locator(".book-pet")).to_have_count(1)

    page.get_by_role("button", name="🎒 Bring along").click()
    expect(page.locator(".detail-facts")).to_contain_text("Comes along on your right")
    expect(page.locator(".book-pet.current .book-pet-badge")).to_have_text("🎒")
    page.get_by_role("button", name="Stay home").click()
    expect(page.get_by_role("button", name="🎒 Bring along")).to_be_visible()
