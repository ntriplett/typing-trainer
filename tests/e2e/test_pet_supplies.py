"""Real-browser e2e tests for Pet Supplies (PLAN.md 11l): buying in the
shop, throwing a treat or toy in a habitat by typing a word, fish food in a
tank, and using a color potion in the Pet Care Center."""

from __future__ import annotations

import random

from playwright.sync_api import Page, expect

from app import db
from app import pet_genes as g


def _setup(tmp_path, coins=1000):
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, coins, "test")


def test_buying_treats_toys_and_potions(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/pets/shop?floor=up")
    _setup(tmp_path)
    page.goto(f"{live_server}/pets/shop?floor=up")
    page.locator("[data-dept='supplies']").click()
    expect(page.locator("#dept-title")).to_have_text("Pet Supplies: Treats & Fish Food")
    page.locator("[data-item='bone_biscuit']").click()
    expect(page.locator("#pet-detail")).to_contain_text("Dogs and Foxes love it!")
    page.get_by_role("button", name="Buy for 5 coins").click()
    page.get_by_role("button", name="Buy for 5 coins").click()
    expect(page.locator("#pet-detail")).to_contain_text("You have 2")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Toys").click()
    page.locator("[data-item='ball']").click()
    page.get_by_role("button", name="Buy for 100 coins").click()
    expect(page.get_by_role("button", name="Yours!")).to_be_disabled()
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Magic Potions").click()
    page.locator("[data-potion='0']").click()
    expect(page.locator("#pet-detail")).to_contain_text("Mystery Potion")
    page.get_by_role("button", name="Buy for 20 coins").click()
    expect(page.locator("#pet-detail")).to_contain_text("It's yours!")
    page.keyboard.press("Escape")
    expect(page.locator("[data-potion='0']")).to_contain_text("Sold!")
    expect(page.locator("#coin-count")).to_have_text(f"{1000 - 10 - 100 - 20:,}")


def test_throwing_a_ball_in_a_habitat(page: Page, live_server, tmp_path):
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/pets/trail")
    _setup(tmp_path)
    page.request.post(f"{live_server}/api/pets/shop/habitats/meadow")
    page.request.post(f"{live_server}/api/supplies/ball")
    with db.open_db(tmp_path / "e2e.db") as conn:
        dog = db.add_v3_pet(conn, 1, g.roll("dog", None, None, 4), "Rex", "shop")
        db.update_v3_pet(conn, 1, dog, home="trail:0", growth=6)
    page.goto(f"{live_server}/pets/trail/0")
    page.locator("[data-item='ball']").click()
    expect(page.locator(".throw-word")).to_have_count(3)
    word = page.evaluate("aiming.choices[1].word")
    page.keyboard.type(word)
    expect(page.locator(".throw-word")).to_have_count(0)
    expect(page.locator("#habitat-pets")).to_contain_text("Rex ♥", timeout=8000)
    page.goto(f"{live_server}/pets/care?pet={dog}")
    expect(page.locator(".hearts")).to_contain_text("♥")
    assert errors == []


def test_feeding_fish(page: Page, live_server, tmp_path):
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/pets/aquarium/0")
    _setup(tmp_path)
    page.request.post(f"{live_server}/api/supplies/fish_flakes")
    rng = random.Random(5)
    with db.open_db(tmp_path / "e2e.db") as conn:
        fish = db.add_v3_pet(conn, 1, g.shop_roll("fish", set(), g.new_seed(rng)), "Nemo", "shop")
        db.update_v3_pet(conn, 1, fish, home="tank:0")
    page.goto(f"{live_server}/pets/aquarium/0")
    page.locator("[data-food='fish_flakes']").click()
    word = page.evaluate("aiming.choices[0].word")
    page.keyboard.type(word)
    page.wait_for_function("world.food.length > 0")
    expect(page.locator("#food")).to_contain_text("None yet")
    page.evaluate("for (let i = 0; i < 1500; i++) FishMotion.step(world)")
    assert page.evaluate("world.food.length") < 12  # some got eaten
    assert errors == []


def test_using_a_potion(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/pets/care")
    _setup(tmp_path)
    page.request.post(f"{live_server}/api/supplies/potions/7")  # a clear one
    with db.open_db(tmp_path / "e2e.db") as conn:
        cat = db.add_v3_pet(conn, 1, g.roll("cat", None, None, 3), "Mittens", "shop")
    page.goto(f"{live_server}/pets/care?pet={cat}")
    page.get_by_role("button", name="🧪 Use a potion").click()
    page.locator(".potion-pick").first.click()
    expect(page.locator("#care-message")).to_contain_text("Ta-da! Mittens is now")
    page.get_by_role("button", name="🧪 Use a potion").click()
    expect(page.locator("#detail-picker")).to_contain_text("No potions that work")
