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


def _in_a_habitat(page, live_server, tmp_path, pets, kind="meadow"):
    page.goto(f"{live_server}/pets/trail")
    page.request.post(f"{live_server}/api/pets/shop/habitats/{kind}")
    with db.open_db(tmp_path / "e2e.db") as conn:
        for species, growth in pets:
            pid = db.add_v3_pet(conn, 1, g.roll(species, None, None, 5), g.species_name(species), "shop")
            db.update_v3_pet(conn, 1, pid, home="trail:0", growth=growth)
    page.goto(f"{live_server}/pets/trail/0")
    page.wait_for_function(f"typeof world !== 'undefined' && world && world.walkers.length === {len(pets)}")


# Runs the scene, drawing as it goes, and reports each pet's time in the air.
AIRTIME = """(makeWorld) => {
  const w0 = makeWorld ? PetMotion.create(world.walkers.map((w) => w.p), { ...world.area, sky: false }, 2 / 3) : world;
  const ticks = 12000;
  const air = w0.walkers.map(() => 0);
  let offscreen = 0;
  const px = () => {};
  for (let i = 0; i < ticks; i++) {
    PetMotion.step(w0);
    w0.walkers.forEach((w, k) => {
      if (w.state === "fly") air[k] += 1;
      if (w.hop > 0 && w.y - w.hop - w.height < 0 && w.y >= w.height + 2) offscreen += 1;
    });
    if (i % 50 === 0) PetMotion.draw(w0, px);
  }
  return { offscreen, pets: w0.walkers.map((w, k) => ({ species: w.p.species, growth: w.p.growth, air: air[k] / ticks })) };
}"""


def test_grown_fairies_dragons_and_phoenixes_fly_in_habitats(page: Page, live_server, tmp_path):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _in_a_habitat(page, live_server, tmp_path, [("flower_fairy", 6), ("dragon", 6), ("phoenix", 10), ("dragon", 3), ("dog", 6)])
    seen = page.evaluate(AIRTIME, False)
    by = {(p["species"], p["growth"]): p["air"] for p in seen["pets"]}
    assert by[("flower_fairy", 10)] > 0.5  # mostly in the air
    assert 0 < by[("dragon", 6)] < 0.5 and 0 < by[("phoenix", 10)] < 0.5  # some of the time
    assert by[("dragon", 3)] == 0 and by[("dog", 6)] == 0  # too young, and no wings
    assert seen["offscreen"] == 0
    assert not errors


def test_pets_stay_on_the_ground_without_a_sky(page: Page, live_server, tmp_path):
    _in_a_habitat(page, live_server, tmp_path, [("flower_fairy", 6), ("dragon", 6)])
    assert all(p["air"] == 0 for p in page.evaluate(AIRTIME, True)["pets"])


def test_flying_pets_land_somewhere_they_can_stand(page: Page, live_server, tmp_path):
    _in_a_habitat(page, live_server, tmp_path, [("flower_fairy", 6), ("phoenix", 6)], kind="stream")
    bad = page.evaluate("""() => {
      const inside = (cx, y, r) => cx >= r.x && cx <= r.x + r.w && y >= r.y && y <= r.y + r.h;
      const t = world.area.terrain;
      let landings = 0, wet = 0;
      const was = world.walkers.map((w) => w.state);
      for (let i = 0; i < 12000; i++) {
        PetMotion.step(world);
        world.walkers.forEach((w, k) => {
          if (was[k] === "fly" && w.state !== "fly" && w.ledge === null) {
            landings += 1;
            const cx = w.x + w.width / 2;
            if ((t.water || []).concat(t.blocks || []).some((r) => inside(cx, w.y, r))) wet += 1;
          }
          was[k] = w.state;
        });
      }
      return { landings, wet };
    }""")
    assert bad["landings"] > 0 and bad["wet"] == 0


def test_the_server_and_the_drawings_agree_on_which_habitats_have_water(page: Page, live_server):
    page.goto(f"{live_server}/pets/trail")
    widest = page.evaluate("""(kinds) => Object.fromEntries(kinds.map((k) => {
      const water = (HABITAT_LOOKS[k].terrain || {}).water || [];
      const left = Math.min(...water.map((r) => r.x)), right = Math.max(...water.map((r) => r.x + r.w));
      return [k, water.length ? right - left : 0];
    }))""", list(pet_care.HABITAT_KINDS))
    for kind, h in pet_care.HABITAT_KINDS.items():
        assert (widest[kind] >= 36) == h.water, kind


def test_a_mermaid_stays_in_her_pool_in_every_water_habitat(page: Page, live_server):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/pets/trail")
    genes = g.resolve(g.roll("mermaid", None, None, 3))
    kinds = [k for k, h in pet_care.HABITAT_KINDS.items() if h.water]
    seen = page.evaluate("""([kinds, genes]) => Object.fromEntries(kinds.map((kind) => {
      const look = HABITAT_LOOKS[kind];
      const area = { left: 2, right: HABITAT_W - 2, top: look.groundTop, bottom: look.groundBottom, sky: true, props: look.props, terrain: look.terrain };
      const world = PetMotion.create([{ id: 1, species: "mermaid", growth: 10, genes }], area, 2 / 3);
      const w = world.walkers[0];
      const was = [w.x, w.y];
      let dry = 0, moved = false;
      const inWater = (cx, y) => w.pool.some((r) => cx >= r.x - 1 && cx <= r.x + r.w + 1 && y >= r.y - 1 && y <= r.y + r.h + 1);
      for (let i = 0; i < 6000; i++) {
        PetMotion.step(world);
        if (w.ledge === null && w.state !== "leap" && !inWater(w.x + w.width / 2, w.y)) dry += 1;
        moved ||= w.x !== was[0];
        if (i % 40 === 0) PetMotion.draw(world, () => {});
      }
      return [kind, { dry, moved }];
    }))""", [kinds, genes])
    for kind, s in seen.items():
        assert s["dry"] == 0 and s["moved"], kind
    assert not errors


def test_a_mermaid_on_land_sits_and_flicks_her_tail(page: Page, live_server):
    page.goto(f"{live_server}/pets/trail")
    genes = g.resolve({**g.roll("mermaid", None, None, 3)})
    genes["shape"] = {**genes["shape"], "breed": "swim", "mix": {}}
    seen = page.evaluate("""(genes) => {
      const world = PetMotion.create([{ id: 1, species: "mermaid", growth: 10, genes }], { left: 2, right: 158, top: 50, bottom: 88, props: [] }, 0.5);
      const w = world.walkers[0];
      const was = [w.x, w.y];
      let flicked = false;
      for (let i = 0; i < 4000; i++) {
        PetMotion.step(world);
        flicked ||= w.frame > 0;
      }
      let arrived = 0;
      PetMotion.attract(world, [1], 80, 70, () => (arrived += 1));
      return { moved: w.x !== was[0] || w.y !== was[1], flicked, happy: w.state, arrived, scene: w.genes.scene, pool: w.pool };
    }""", genes)
    assert not seen["moved"] and seen["flicked"] and seen["scene"] == "land" and seen["pool"] is None
    assert seen["happy"] == "happy" and seen["arrived"] == 1  # she can't come over for a treat, but she gets it


def test_a_mermaid_swims_over_for_a_treat(page: Page, live_server):
    page.goto(f"{live_server}/pets/trail")
    genes = g.resolve(g.roll("mermaid", None, None, 3))
    seen = page.evaluate("""(genes) => {
      const look = HABITAT_LOOKS.pond;
      const world = PetMotion.create([{ id: 1, species: "mermaid", growth: 10, genes }], { left: 2, right: 158, top: look.groundTop, bottom: look.groundBottom, sky: true, props: [], terrain: look.terrain }, 2 / 3);
      const w = world.walkers[0];
      let arrived = 0;
      PetMotion.attract(world, [1], 150, 85, () => (arrived += 1));
      for (let i = 0; i < 3000 && !arrived; i++) PetMotion.step(world);
      return { arrived, state: w.state, inPool: w.pool.some((r) => w.x + w.width / 2 >= r.x && w.x + w.width / 2 <= r.x + r.w) };
    }""", genes)
    assert seen["arrived"] == 1 and seen["inPool"]


def test_the_move_list_only_offers_a_mermaid_water(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/pets/trail")
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, 100000, "test")
        mermaid = db.add_v3_pet(conn, 1, g.roll("mermaid", None, None, 3), "Marina", "shop", growth=6)
    page.goto(f"{live_server}/pets/care?pet={mermaid}")
    page.request.post(f"{live_server}/api/pets/shop/habitats/meadow")
    page.reload()
    page.get_by_role("button", name="🏡 Move to a habitat").click()
    expect(page.locator("#detail-picker")).to_contain_text("needs a habitat with plenty of water")
    page.request.post(f"{live_server}/api/pets/shop/habitats/pond")
    page.reload()
    page.get_by_role("button", name="🏡 Move to a habitat").click()
    expect(page.locator("#detail-picker")).to_contain_text("Pond & Marsh")
    expect(page.locator("#detail-picker")).not_to_contain_text("Meadow")


def test_only_mermaids_climb_the_lagoons_rocks(page: Page, live_server):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/pets/trail")
    pets = [{"id": i, "species": sp, "growth": 10, "genes": g.resolve(g.roll(sp, None, None, 20 + i))} for i, sp in enumerate(("mermaid", "goat", "flower_fairy", "dragon", "turtle"))]
    seen = page.evaluate("""(pets) => {
      const look = HABITAT_LOOKS.lagoon;
      const world = PetMotion.create(pets, { left: 2, right: HABITAT_W - 2, top: look.groundTop, bottom: look.groundBottom, sky: true, props: look.props, terrain: look.terrain }, 2 / 3);
      const onRock = pets.map(() => 0);
      let dove = 0, wasUp = false;
      for (let i = 0; i < 30000; i++) {
        PetMotion.step(world);
        world.walkers.forEach((w, k) => { if (w.ledge !== null) onRock[k] += 1; });
        const up = world.walkers[0].ledge !== null;
        if (wasUp && !up) dove += 1;
        wasUp = up;
        if (i % 40 === 0) PetMotion.draw(world, () => {});
      }
      // called down from her rock for a treat
      const her = world.walkers[0];
      her.ledge = 0; her.state = "idle"; her.timer = 99;
      let ate = 0;
      PetMotion.attract(world, [0], 80, 70, () => (ate += 1));
      for (let i = 0; i < 3000 && !ate; i++) PetMotion.step(world);
      return { onRock, dove, ate, ledge: her.ledge };
    }""", pets)
    assert seen["onRock"][0] > 0 and seen["dove"] > 0
    assert seen["onRock"][1:] == [0, 0, 0, 0]
    assert seen["ate"] == 1 and seen["ledge"] is None
    assert not errors


def test_a_swimming_mermaid_stays_in_the_picture_with_water_under_her_tail(page: Page, live_server):
    page.goto(f"{live_server}/pets/trail")
    genes = g.resolve(g.roll("mermaid", None, None, 3))
    seen = page.evaluate("""(genes) => {
      const look = HABITAT_LOOKS.lagoon;
      const world = PetMotion.create([{ id: 1, species: "mermaid", growth: 10, genes }], { left: 2, right: HABITAT_W - 2, top: look.groundTop, bottom: look.groundBottom, sky: true, props: [], terrain: look.terrain }, 2 / 3);
      const w = world.walkers[0];
      let left = 999, right = -999, low = -999;
      for (let i = 0; i < 20000; i++) {
        PetMotion.step(world);
        if (w.ledge !== null || w.state === "leap") continue;
        left = Math.min(left, w.x);
        right = Math.max(right, w.x + w.width);
        low = Math.max(low, w.y);
      }
      return { left, right, low, tail: w.height * (0.28 / 0.72) };
    }""", genes)
    assert seen["left"] >= 2 and seen["right"] <= 158
    assert seen["low"] <= 48 + 27 - seen["tail"] + 0.01


def test_companions_dont_bounce_chase_or_dig(page: Page, live_server):
    page.goto(f"{live_server}/pets/trail")
    pets = [{"id": i, "species": sp, "growth": 10, "genes": g.resolve(g.roll(sp, None, None, 30 + i))} for i, sp in enumerate(("flower_fairy", "dog", "mermaid"))]
    seen = page.evaluate("""(pets) => {
      const look = HABITAT_LOOKS.pond;
      const world = PetMotion.create(pets, { left: 2, right: HABITAT_W - 2, top: look.groundTop, bottom: look.groundBottom, sky: true, props: look.props, terrain: look.terrain }, 2 / 3);
      const states = pets.map(() => new Set());
      let chasedFriend = false;
      for (let i = 0; i < 30000; i++) {
        PetMotion.step(world);
        world.walkers.forEach((w, k) => states[k].add(w.state));
        if (world.walkers[1].state === "chase" && world.walkers[1].target.companion) chasedFriend = true;
      }
      // a gift lands: she comes over and is pleased, without bouncing
      const results = [0, 2].map((k) => {
        const w = world.walkers[k];
        Object.assign(w, { state: "idle", timer: 99, ledge: null, hop: 0 });
        let done = 0, hop = 0;
        PetMotion.attract(world, [k], 80, 80, () => (done += 1));
        for (let i = 0; i < 4000 && !done; i++) PetMotion.step(world);
        const frames = [];
        for (let i = 0; i < 40 && w.state === "happy"; i++) {
          PetMotion.step(world);
          hop = Math.max(hop, w.hop);
          frames.push(w.dir);
        }
        return { done, hop, turned: new Set(frames).size > 1 };
      });
      return { fairy: [...states[0]], dog: [...states[1]], mermaid: [...states[2]], chasedFriend, results };
    }""", pets)
    for banned in ("hop", "chase", "dig", "jump", "splash"):
        assert banned not in seen["fairy"] and banned not in seen["mermaid"], banned
    assert not seen["chasedFriend"]
    for r in seen["results"]:
        assert r["done"] == 1 and r["hop"] == 0 and not r["turned"]


def test_every_supply_has_art(page: Page, live_server):
    from app import pet_supplies
    page.goto(f"{live_server}/pets/care")
    missing = page.evaluate("(ids) => ids.filter((id) => !SUPPLY_ART[id])", list(pet_supplies.SUPPLIES))
    assert missing == []
