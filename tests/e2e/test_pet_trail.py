"""Real-browser e2e tests for the Trailhead and habitats (PLAN.md 11i):
walking the trail, the map, and visiting a habitat with its pets."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db
from app import pet_care
from app import pet_genes as g


def test_walk_the_trail_and_use_the_map(page: Page, live_server):
    page.goto(f"{live_server}/pets/trail")
    expect(page.locator("#trail-stop")).to_have_text("Stop 1 of 10")
    expect(page.locator("#trail-sign")).to_contain_text("Empty lot")
    expect(page.locator("#trail-window")).to_have_attribute("href", "/pets/shop?dept=habitats")
    expect(page.locator("#trail-down")).to_have_text("▼ Back to Pets")
    page.keyboard.press("ArrowUp")
    expect(page.locator("#trail-stop")).to_have_text("Stop 2 of 10")
    page.get_by_role("button", name="🗺️ Map").click()
    expect(page.locator(".map-spot")).to_have_count(10)
    page.locator("[data-spot='9']").click()
    expect(page.locator("#trail-stop")).to_have_text("Stop 10 of 10")
    expect(page.locator("#trail-up")).to_be_disabled()


def test_visit_a_habitat_with_its_pets(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/pets/trail")  # makes the player
    page.request.post(f"{live_server}/api/pets/shop/habitats/meadow")
    with db.open_db(tmp_path / "e2e.db") as conn:
        pid = db.add_v3_pet(conn, 1, g.roll("goat", None, None, 5), "Pickles", "shop")
        db.update_v3_pet(conn, 1, pid, home="trail:0", growth=6)
    page.goto(f"{live_server}/pets/trail")
    expect(page.locator("#trail-sign")).to_contain_text("Meadow")
    expect(page.locator("#trail-sign")).to_contain_text("1 of 6 pets")
    page.locator("#trail-window").click()
    expect(page).to_have_url(f"{live_server}/pets/trail/0")
    expect(page.locator("#habitat-name")).to_have_text("Meadow")
    expect(page.locator("#habitat-count")).to_have_text("Living here: 1 of 6")
    page.get_by_role("link", name="Pickles").click()
    expect(page.locator("#book-detail h2")).to_have_text("Pickles")
    page.goto(f"{live_server}/pets/trail/0")
    page.get_by_role("link", name="⬅ To the trail").click()
    expect(page.locator("#trail-stop")).to_have_text("Stop 1 of 10")


def test_an_empty_spot_has_no_habitat_page(page: Page, live_server):
    page.goto(f"{live_server}/pets/trail/3")
    expect(page.locator("#habitat-message")).to_contain_text("no habitat there")


def test_down_from_the_first_stop_goes_back_to_pets(page: Page, live_server):
    page.goto(f"{live_server}/pets/trail")
    expect(page.locator("#trail-down")).to_have_text("▼ Back to Pets")
    page.keyboard.press("ArrowDown")
    expect(page).to_have_url(f"{live_server}/pets")
    page.get_by_role("link", name="🏠 Home").click()
    expect(page).to_have_url(f"{live_server}/")


def test_every_habitat_kind_has_a_look_and_runs_with_pets(page: Page, live_server, tmp_path):
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/pets/trail")
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_habitat(conn, 1, 0, "meadow", "Test")
        for k, sp in enumerate(["goat", "turtle", "cat", "lizard", "dog", "phoenix"]):
            pid = db.add_v3_pet(conn, 1, g.roll(sp, None, None, 40 + k), sp.capitalize(), "shop")
            db.update_v3_pet(conn, 1, pid, home="trail:0", growth=6)
    page.goto(f"{live_server}/pets/trail/0")
    expect(page.locator("#habitat-name")).to_have_text("Test")
    looks = set(page.evaluate("Object.keys(HABITAT_LOOKS)"))
    assert set(pet_care.HABITAT_KINDS) <= looks
    for kind in pet_care.HABITAT_KINDS:
        with db.open_db(tmp_path / "e2e.db") as conn:
            conn.execute("UPDATE habitat SET kind = ? WHERE learner_id = 1 AND spot = 0", (kind,))
        page.goto(f"{live_server}/pets/trail/0")
        expect(page.locator("#habitat-count")).to_have_text("Living here: 6 of 6")
        page.evaluate("for (let i = 0; i < 1500; i++) PetMotion.step(world)")  # minutes of pet life, fast
    assert errors == []
