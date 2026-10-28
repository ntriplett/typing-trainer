"""Real-browser e2e tests for the Pet Shop page (PLAN.md 11h): departments,
the close-up, Save for me, buying with coins, and the pet coupon."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db

from .conftest import place_on_home_row


def _give_coins(tmp_path, amount: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, amount, "test")


def test_a_new_player_shops_for_fish_and_saves_one(page: Page, live_server):
    page.goto(f"{live_server}/pets/shop")
    expect(page.locator("#dept-title")).to_have_text("Fish")
    expect(page.locator(".shop-card")).to_have_count(16)
    expect(page.locator("[data-dept='household']")).to_contain_text("Learn")
    page.locator("[data-dept='household']").click()
    expect(page.locator("#shop-message")).to_contain_text("opens when you learn")

    page.locator(".shop-card").nth(3).click()
    expect(page.locator("#pet-detail")).to_contain_text("All grown up")
    page.get_by_role("button", name="Save for me").click()
    expect(page.get_by_role("button", name="Let it go")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".shop-card").nth(3).locator(".ribbon-saved")).to_have_text("Saved!")
    expect(page.locator("#shop-saved")).to_contain_text("Saved for you")

    page.locator(".shop-card").nth(4).click()
    expect(page.get_by_role("button", name="Save for me")).to_be_disabled()


def test_buying_a_fish_with_coins(page: Page, live_server, tmp_path):
    _give_coins(tmp_path, 1000)
    page.goto(f"{live_server}/pets/shop?dept=fish")
    card = page.locator(".shop-card").first
    price = int(card.locator(".card-price").inner_text().replace(",", ""))
    card.click()
    page.get_by_role("button", name=f"Buy for {price:,} coins").click()
    page.get_by_role("button", name="Yes, buy it!").click()
    expect(page.locator("#pet-detail")).to_contain_text("Welcome home, Fish!")
    expect(page.locator("#coin-count")).to_have_text(f"{1000 - price:,}")
    page.get_by_role("button", name="Yay!").click()
    expect(page.locator(".shop-card").first).to_contain_text("Adopted!")


def test_the_home_row_coupon_buys_a_household_pet(page: Page, live_server):
    place_on_home_row(page, live_server)
    page.goto(f"{live_server}/pets/shop")
    expect(page.locator("#dept-title")).to_have_text("Household Pets")  # the coupon brings you here
    expect(page.locator("#shop-coupon")).to_contain_text("pet coupon")
    page.locator(".shop-card").nth(1).click()
    page.get_by_role("button", name="Use my coupon (free!)").click()
    page.get_by_role("button", name="Yes, use my coupon!").click()
    expect(page.locator("#pet-detail")).to_contain_text("Welcome home")
    expect(page.locator("#coin-count")).to_have_text("0")
    page.get_by_role("button", name="Yay!").click()
    expect(page.locator("#shop-coupon")).to_be_hidden()
    expect(page.locator(".shop-card").nth(1)).to_contain_text("Adopted!")


def test_sending_a_special_order(page: Page, live_server, tmp_path):
    place_on_home_row(page, live_server)
    _give_coins(tmp_path, 1000)
    page.goto(f"{live_server}/pets/shop?dept=orders")
    expect(page.locator(".order-form")).to_contain_text("Order a special pet!")
    page.locator("[data-species='cat']").click()
    page.locator("[data-primary='black']").click()
    expect(page.locator(".order-explain")).to_contain_text("4 cats")
    expect(page.locator("#order-preview")).to_be_visible()
    page.get_by_role("button", name="Send my order").click()
    page.get_by_role("button", name="Yes, send it!").click()
    expect(page.locator(".order-status")).to_contain_text("4 cats in Black arrive tomorrow")
    expect(page.locator("#coin-count")).to_have_text("600")
    expect(page.locator(".order-warning")).to_contain_text("cats home")
    expect(page.locator("#shop-message")).to_be_empty()
