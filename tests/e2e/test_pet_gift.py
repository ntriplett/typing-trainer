"""Real-browser e2e tests for gifting a pet designed in the pet lab: the lab's
JSON out and back in, the For Grown-ups form, the box at the shop door and on
the rug, its tag, and naming the pet to take it home."""

from __future__ import annotations

import json
import os

from playwright.sync_api import Page, expect

from app import db
from app import pet_genes as g

from .conftest import GROWNUP_PIN

SHOTS = os.environ.get("GIFT_SHOTS")  # a folder: save screenshots of each step there


def shot(page: Page, name: str) -> None:
    if SHOTS:
        page.screenshot(path=f"{SHOTS}/{name}.png")


def test_the_lab_designs_a_pet_and_its_json_goes_out_and_back(page: Page, live_server):
    page.goto(f"{live_server}/pet-lab")
    page.select_option("#opt-species", "bunny")
    page.wait_for_function("selected && selected.species === 'bunny'")
    page.select_option("#opt-breed", "halflop")
    page.select_option("#opt-c0", "snow")
    page.select_option("#opt-c1", "chestnut")
    page.select_option("#opt-pattern", "dutch")
    page.fill("#opt-name", "Hoppy")
    design = json.loads(page.input_value("#design-json"))
    assert design["name"] == "Hoppy" and design["genes"]["shape"]["breed"] == "halflop"
    assert design["genes"]["coat"]["colors"][:2] == ["snow", "chestnut"] and "hex" not in design["genes"]
    g.design_from(design["genes"])  # the game takes it as it is

    page.select_option("#opt-species", "cat")  # somewhere else, then load the bunny back
    page.wait_for_function("selected && selected.species === 'cat'")
    page.fill("#design-json", json.dumps(design))
    page.click("#json-load")
    expect(page.locator("#json-message")).to_have_text("Loaded!")
    assert page.evaluate("selected.species") == "bunny" and page.input_value("#opt-breed") == "halflop"
    assert page.input_value("#opt-name") == "Hoppy"


def test_a_gift_from_dad_is_opened_at_the_shop_and_named(page: Page, live_server, tmp_path):
    genes = g.roll("bunny", None, None, 12)
    genes["coat"] |= {"colors": ["snow", "chestnut", None], "shares": [0.65, 0.35, 0.0], "pattern": "dutch"}
    page.goto(f"{live_server}/parent")
    page.locator("#pin").fill(GROWNUP_PIN)
    page.keyboard.press("Enter")
    expect(page.locator("#gift-to option")).to_have_text(["Tester"])
    page.fill("#gift-design", json.dumps({"name": "Hoppy", "genes": genes}))
    page.get_by_role("button", name="🎁 Wrap it up").click()
    expect(page.locator("#gift-message")).to_contain_text("Hoppy is wrapped up for Tester, from Dad")

    page.goto(f"{live_server}/pets")
    expect(page.locator(".hub-news")).to_have_text("🎁 A gift for you!")
    shot(page, "1-hub")
    page.goto(f"{live_server}/pets/shop")
    box = page.locator(".gift-spot")
    expect(box).to_be_visible()
    shot(page, "2-rug")
    box.click()
    expect(page.locator(".gift-tag")).to_contain_text("A gift fromDad")
    shot(page, "3-tag")
    page.get_by_role("button", name="🎀 Open it!").click()
    expect(page.locator("#gift-name")).to_have_value("Hoppy")
    shot(page, "4-name")
    page.fill("#gift-name", "Mr Hops")
    page.get_by_role("button", name="Take Mr Hops home (free!)").click()
    expect(page.locator("#detail-body")).to_contain_text("Welcome home, Mr Hops!")
    page.locator("#detail-body").get_by_role("button", name="Yay!").click()
    expect(page.locator(".gift-spot")).to_have_count(0)

    with db.open_db(tmp_path / "e2e.db") as conn:
        [pet] = db.list_v3_pets(conn, 1)
    assert pet["name"] == "Mr Hops" and pet["growth"] == 0
    page.goto(f"{live_server}/pets/care?pet={pet['id']}")
    expect(page.locator(".detail-facts")).to_contain_text("a gift from Dad")
