"""Real-browser e2e tests for the Aquarium (PLAN.md 11k): the hall of tanks
and its side rooms, decorating a tank, fish moving in, and the Care Center
moving a fish into a tank."""

from __future__ import annotations

import random

from playwright.sync_api import Page, expect

from app import db
from app import pet_genes as g


def _fish(tmp_path, count=2) -> list[int]:
    rng = random.Random(3)
    with db.open_db(tmp_path / "e2e.db") as conn:
        return [db.add_v3_pet(conn, 1, g.shop_roll("fish", set(), g.new_seed(rng)), f"Fish{k}", "shop") for k in range(count)]


def test_the_hall_has_a_starter_tank_and_side_rooms(page: Page, live_server):
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/pets")
    page.locator("[data-building='aquarium']").click()
    expect(page.locator("#hall-title")).to_have_text("Aquarium")
    expect(page.locator(".hall-tank")).to_have_count(4)
    expect(page.locator("[data-spot='0']")).to_contain_text("Tank 1")
    expect(page.locator(".hall-tank.empty")).to_have_count(3)
    page.locator("[data-room='reef']").click()
    expect(page.locator("#hall-title")).to_have_text("Reef Room")
    expect(page.locator(".hall-tank")).to_have_count(3)
    page.locator("[data-room='main']").click()
    page.locator("[data-spot='0']").click()
    expect(page.locator("#tank-name")).to_have_text("Tank 1")
    assert errors == []


def test_decorating_a_tank(page: Page, live_server, tmp_path):
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/pets/aquarium/0")
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, 500, "test")
    for item in ("castle", "grass", "bg_night"):
        page.request.post(f"{live_server}/api/aquarium-shop/{item}")
    page.goto(f"{live_server}/pets/aquarium/0")
    page.get_by_role("button", name="🎨 Decorate").click()
    expect(page.locator(".storage-piece")).to_have_count(2)
    page.locator("[data-item='castle']").click()
    expect(page.locator("#piece-tools")).to_contain_text("Castle")
    expect(page.locator(".storage-piece")).to_have_count(1)
    page.get_by_role("button", name="↔ Flip").click()
    page.get_by_role("button", name="In front of fish").click()
    expect(page.get_by_role("button", name="In front of fish")).to_have_class("button-go")
    # drag it to the left
    page.locator("#tank-canvas").scroll_into_view_if_needed()
    box = page.locator("#tank-canvas").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.8)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.2, box["y"] + box["height"] * 0.8, steps=5)
    page.mouse.up()
    page.wait_for_timeout(300)
    piece = page.request.get(f"{live_server}/api/aquarium/0").json()["tank"]["pieces"][0]
    assert piece["x"] < 50 and piece["flip"] and piece["layer"] == "front"
    page.locator("[data-background='bg_night']").click()
    expect(page.locator("[data-background='bg_night']")).to_have_class("look-pick current")
    page.get_by_role("button", name="📦 Put away").click()
    expect(page.locator(".storage-piece")).to_have_count(2)
    assert errors == []


def test_fish_move_in_from_the_tank_and_the_care_center(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/pets/aquarium/0")
    a, b = _fish(tmp_path)
    page.goto(f"{live_server}/pets/aquarium/0")
    page.get_by_role("button", name="🐠 Fish (0/10)").click()
    page.locator(f"#waiting-fish [data-fish='{a}']").click()
    expect(page.get_by_role("button", name="🐠 Fish (1/10)")).to_be_visible()
    page.goto(f"{live_server}/pets/care?pet={b}")
    expect(page.locator(".detail-facts")).to_contain_text("Waiting for a tank")
    page.get_by_role("button", name="🐠 Move to a tank").click()
    page.get_by_role("button", name="Tank 1 (1/10)").click()
    expect(page.locator(".detail-facts")).to_contain_text("Swims in Tank 1")


def test_buying_a_school_of_fish(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/pets/care")
    (head,) = _fish(tmp_path, 1)
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, 2000, "test")
    page.goto(f"{live_server}/pets/care?pet={head}")
    expect(page.locator(".detail-facts")).to_contain_text("Just one")
    buy = page.get_by_role("button", name="🐟 Buy another")
    buy.click()
    expect(page.locator("#care-message")).to_contain_text("You have 2")
    page.get_by_role("button", name="🐟 Buy another").click()
    expect(page.locator(".book-pet.current .book-pet-count")).to_have_text("×3")
    expect(page.locator(".detail-facts")).to_contain_text("You have 3 of these")
    page.get_by_role("button", name="🐠 Move the school to a tank").click()
    page.get_by_role("button", name="Tank 1 (0/10)").click()
    expect(page.locator(".detail-facts")).to_contain_text("Swims in Tank 1")
    page.goto(f"{live_server}/pets/aquarium/0")
    expect(page.get_by_role("button", name="🐠 Fish (3/10)")).to_be_visible()
