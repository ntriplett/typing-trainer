"""Real-browser e2e tests for Wanderpaw (PLAN.md 11n): setting off on a
trip and walking by typing, and the lab's small maps and gallery."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_set_off_and_walk_by_typing(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#where-name")).to_have_text("Camp")
    page.keyboard.press("Enter")
    expect(page.locator("#energy")).to_be_visible()
    page.wait_for_function("targets.length > 0")
    word = page.evaluate("targets[0].word")
    to = page.evaluate("targets[0].hex")
    page.keyboard.type(word)
    page.wait_for_function(f"state.local.spot[0] === {to[0]} && state.local.spot[1] === {to[1]}")
    expect(page.locator("#energy-text")).not_to_have_text("120")


def test_lab_opens_small_maps_and_the_gallery(page: Page, live_server):
    page.goto(f"{live_server}/wander-lab")
    expect(page.locator("#local-section")).to_be_visible()  # opens on your own place
    page.click("#gallery-button")
    expect(page.locator("#gallery figure").first).to_be_visible()
    assert page.locator("#gallery figure").count() >= 15


def test_go_in_to_the_elder_and_take_the_quest(page: Page, live_server):
    from app.wanderpaw import local as lc
    from app.wanderpaw import world as wd

    page.goto(f"{live_server}/wanderpaw")
    seed = page.request.get(f"{live_server}/api/wander-lab/world").json()["seed"]
    q = wd.generate(seed).quests["leaf"]
    elder = next(h for h, role in lc.generate(seed, q.town).buildings.items() if role == "elder")
    page.request.post(f"{live_server}/api/wander/trip/start", data={})
    page.request.post(f"{live_server}/api/wander-lab/teleport", data={"q": q.town[0], "r": q.town[1], "spot": list(elder)})
    page.reload()
    page.wait_for_function("state && state.screen")
    page.keyboard.press("Enter")
    expect(page.locator("#screen-title")).to_have_text("Old Badger")
    page.keyboard.press("Enter")
    expect(page.locator("#story")).to_contain_text("Acorn Locket")
