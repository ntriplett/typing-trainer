"""Real-browser e2e tests for Wanderpaw (PLAN.md 11n): setting off on a
trip and walking by typing, and the lab's small maps and gallery."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_set_off_and_walk_by_typing(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#where-name")).to_have_text("Camp")
    # between trips: pick a party (no pets yet, so starters come)
    expect(page.locator("#picker")).to_be_visible()
    expect(page.locator("#picker-keys")).to_contain_text("Starters coming")
    page.keyboard.press("Enter")
    expect(page.locator("#energy")).to_be_visible()
    expect(page.locator("#picker")).to_be_hidden()
    full = page.locator("#energy-text").inner_text()
    page.wait_for_function("targets.length > 0")
    word = page.evaluate("targets[0].word")
    to = page.evaluate("targets[0].hex")
    page.keyboard.type(word)
    page.wait_for_function(f"state.local.spot[0] === {to[0]} && state.local.spot[1] === {to[1]}")
    expect(page.locator("#energy-text")).not_to_have_text(full)


def test_lab_opens_small_maps_and_the_gallery(page: Page, live_server):
    page.goto(f"{live_server}/wander-lab")
    expect(page.locator("#local-section")).to_be_visible()  # opens on your own place
    page.click("#gallery-button")
    expect(page.locator("#gallery figure").first).to_be_visible()
    assert page.locator("#gallery figure").count() >= 15


def test_go_in_to_a_quest_giver_and_take_the_quest(page: Page, live_server):
    from app.wanderpaw import quests as qs

    page.goto(f"{live_server}/wanderpaw")
    seed = page.request.get(f"{live_server}/api/wander-lab/world").json()["seed"]
    g = qs.plan(seed).givers["leaf:leaf"]
    page.request.post(f"{live_server}/api/wander/trip/start", data={})
    page.request.post(f"{live_server}/api/wander-lab/teleport", data={"q": g.town[0], "r": g.town[1], "spot": list(g.house)})
    page.reload()
    page.wait_for_function("state && state.screen")
    page.keyboard.press("Enter")
    expect(page.locator("#screen-title")).to_have_text("Nanny Bramble")
    page.keyboard.press("Enter")
    expect(page.locator("#screen-text")).to_contain_text("still need the")
    page.keyboard.press("Escape")
    expect(page.locator("#keys")).to_contain_text("Go in: Nanny Bramble")
    page.keyboard.press("2")  # the journal
    expect(page.locator("#menu-body")).to_contain_text("Garden Shears")
    page.keyboard.press("Escape")
    expect(page.locator("#menu")).to_be_hidden()
    page.keyboard.press("Escape")  # go home?
    expect(page.locator("#menu-title")).to_have_text("Heading home?")
