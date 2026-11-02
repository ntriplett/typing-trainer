"""Real-browser e2e tests for the Pet Shop page (PLAN.md 11h): departments,
the close-up, Save for me, buying with coins, and the pet coupon."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db

from .conftest import place_on_home_row


def _give_coins(tmp_path, amount: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, amount, "test")


def test_a_new_player_walks_in_shops_for_fish_and_saves_one(page: Page, live_server):
    page.goto(f"{live_server}/pets/shop")
    expect(page.locator("#dept-title")).to_have_text("Welcome to the Pet Shop!")
    expect(page.locator(".shop-spot")).to_have_count(7)  # 6 departments and the stairs
    expect(page.locator("[data-dept='household']")).to_contain_text("Learn")
    page.locator("[data-dept='household']").click()
    expect(page.locator("#shop-message")).to_contain_text("opens when you learn")
    page.locator("[data-stairs='up']").click()
    page.locator("[data-dept='fish']").click()
    expect(page.locator("#dept-title")).to_have_text("Fish: Tank Wall")
    expect(page.locator(".shop-slot")).to_have_count(8)

    page.locator(".shop-slot").nth(3).click()
    expect(page.locator("#pet-detail")).to_contain_text("All grown up")
    page.get_by_role("button", name="Save for me").click()
    expect(page.get_by_role("button", name="Let it go")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".shop-slot").nth(3).locator(".slot-ribbon")).to_have_text("Saved!")
    expect(page.locator("#shop-saved")).to_contain_text("Saved for you")

    page.locator(".shop-slot").nth(4).click()
    expect(page.get_by_role("button", name="Save for me")).to_be_disabled()
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Deep Tanks").click()
    expect(page.locator("#dept-title")).to_have_text("Fish: Deep Tanks")
    page.get_by_role("button", name="Upstairs").click()
    expect(page.locator("#dept-title")).to_have_text("Upstairs: Fish, Homes & Supplies")


def test_buying_a_fish_with_coins(page: Page, live_server, tmp_path):
    _give_coins(tmp_path, 1000)
    page.goto(f"{live_server}/pets/shop?dept=fish")
    slot = page.locator(".shop-slot").first
    price = int(slot.locator(".slot-tag").inner_text().strip().split()[0].replace(",", ""))
    slot.click()
    page.get_by_role("button", name=f"Buy for {price:,} coins").click()
    expect(page.locator("#pet-detail")).to_contain_text("Welcome home, Fish!")
    expect(page.locator("#coin-count")).to_have_text(f"{1000 - price:,}")
    page.get_by_role("button", name="Yay!").click()
    expect(page.locator(".shop-slot").first).to_contain_text("Adopted!")


def test_the_home_row_coupon_buys_a_household_pet(page: Page, live_server):
    place_on_home_row(page, live_server)
    page.goto(f"{live_server}/pets/shop")
    expect(page.locator("#shop-coupon")).to_contain_text("pet coupon")
    page.get_by_role("button", name="Go to Household Pets").click()
    expect(page.locator("#dept-title")).to_have_text("Household Pets: Living Room")
    expect(page.locator(".shop-slot").nth(1)).to_contain_text("Free")
    page.locator(".shop-slot").nth(1).click()
    page.get_by_role("button", name="Use my coupon (free!)").click()
    expect(page.locator("#pet-detail")).to_contain_text("Welcome home")
    expect(page.locator("#coin-count")).to_have_text("0")
    page.get_by_role("button", name="Yay!").click()
    expect(page.locator("#shop-coupon")).to_be_hidden()
    expect(page.locator(".shop-slot").nth(1)).to_contain_text("Adopted!")


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
    expect(page.locator(".order-status")).to_contain_text("4 cats in Black arrive tomorrow")
    expect(page.locator("#coin-count")).to_have_text("600")
    expect(page.locator(".order-warning")).to_contain_text("cats home")
    expect(page.locator("#shop-message")).to_be_empty()


def test_the_habitat_gallery(page: Page, live_server, tmp_path):
    _give_coins(tmp_path, 2000)
    page.goto(f"{live_server}/pets/shop")
    page.locator("[data-stairs='up']").click()
    expect(page.locator("#dept-title")).to_have_text("Upstairs: Fish, Homes & Supplies")
    page.locator("[data-dept='habitats']").click()
    expect(page.locator("#dept-title")).to_have_text("Habitats: Outdoors Hall")
    expect(page.locator(".gallery-frame")).to_have_count(8)
    expect(page.locator("[data-kind='forest']")).to_contain_text("Free!")
    page.get_by_role("button", name="Outdoors Annex").click()
    page.get_by_role("button", name="Cozy Corner").click()
    expect(page.locator("#dept-title")).to_have_text("Habitats: Cozy Corner")
    page.get_by_role("button", name="Magical Wing").click()
    expect(page.locator(".gallery-frame.locked")).to_have_count(6)
    page.get_by_role("button", name="Cozy Corner").click()
    page.locator("[data-kind='cottage']").click()
    expect(page.locator("#pet-detail")).to_contain_text("Cozy Cottage")
    expect(page.get_by_role("button", name="Need 500 more coins")).to_be_disabled()
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Upstairs").click()
    page.locator("[data-dept='habitats']").click()
    page.locator("[data-kind='forest']").click()
    page.get_by_role("button", name="Get it free!").click()
    expect(page.locator("#dept-hint")).to_contain_text("Your Forest is ready")
    expect(page.locator("[data-kind='forest']")).to_contain_text("1,500")


def test_aquarium_supplies_upstairs(page: Page, live_server, tmp_path):
    _give_coins(tmp_path, 600)
    page.goto(f"{live_server}/pets/shop?floor=up")
    page.locator("[data-dept='aqua']").click()
    expect(page.locator("#dept-title")).to_have_text("Aquarium Supplies: Tanks & Backdrops")
    page.locator("[data-item='tank']").click()
    page.get_by_role("button", name="Buy for 400 coins").click()
    expect(page.locator("#pet-detail")).to_contain_text("Tank 2 is ready")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Sand & Gravel").click()
    page.get_by_role("button", name="Little Plants").click()
    page.get_by_role("button", name="Plants", exact=True).click()
    page.locator("[data-item='grass']").click()
    page.get_by_role("button", name="Buy for 10 coins").click()
    page.get_by_role("button", name="Buy for 10 coins").click()
    expect(page.locator("#pet-detail")).to_contain_text("You have 2")
    expect(page.locator("#coin-count")).to_have_text("180")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Upstairs").click()
    page.locator("[data-stairs='down']").click()
    expect(page.locator("#dept-title")).to_have_text("Welcome to the Pet Shop!")


def _open_the_desk(tmp_path, coins=20000):
    from app import lessons, pet_shop
    with db.open_db(tmp_path / "e2e.db") as conn:
        lessons.record_placement(conn, 1, set(pet_shop.HOME_ROW + pet_shop.TOP_ROW + pet_shop.BOTTOM_ROW + pet_shop.NUMBERS))
        db.add_coins(conn, 1, coins, "test")


def test_a_friend_writes_and_you_invite_her(page: Page, live_server, tmp_path):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/pets/shop")
    expect(page.locator("[data-dept='companions']")).to_contain_text("Learn the numbers")
    _open_the_desk(tmp_path)
    page.reload()
    desk = page.locator("[data-dept='companions']")
    expect(desk).to_contain_text("A letter for you!")
    desk.click()
    letter = page.locator("#pet-detail")
    expect(letter).to_contain_text("A friend would like to visit you")
    expect(letter).to_contain_text("Dear friend,")
    expect(letter).to_contain_text("Your friend,")
    expect(letter).not_to_contain_text("Buy")
    expect(letter).not_to_contain_text("Save for me")
    page.get_by_role("button", name="Maybe another time").click()
    expect(letter).not_to_be_visible()
    desk.click()
    page.get_by_role("button", name="Invite").click()
    expect(letter).to_contain_text("is here!")
    name = letter.locator("h2").inner_text().replace("🎉 ", "").replace(" is here!", "")
    page.get_by_role("button", name=f"Welcome, {name}!").click()
    expect(desk).to_contain_text("No letters today")
    desk.click()
    expect(letter).to_contain_text("Check back tomorrow")
    page.goto(f"{live_server}/pets/care")
    expect(page.locator(".book-pet")).to_contain_text(name)
    assert not errors


def test_the_desk_link_opens_the_letter(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/pets/shop")
    _open_the_desk(tmp_path)
    page.goto(f"{live_server}/pets/shop?dept=companions")
    expect(page.locator("#pet-detail")).to_contain_text("Dear friend,")
