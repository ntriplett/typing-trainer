"""Wanderpaw saves: walking, fog, trips, naps, fitting a changed world (PLAN.md 11n)."""

import pytest

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app.wanderpaw import save as sv
from app.wanderpaw import story as st
from app.wanderpaw import world as wd

SEED = 11


TEAM = [wp.starter(t, 5) for t in wd.REGIONS]
FULL = sv.WALK_ENERGY + wp.team_energy(TEAM)


@pytest.fixture(autouse=True)
def no_creatures(monkeypatch):
    """These tests aren't about wild creatures (test_wanderpaw_battle.py is)."""
    monkeypatch.setattr(sv.cr, "at", lambda *a: {})


def _on_trip():
    return sv.start_trip({**sv.new_save(SEED), "team": TEAM})


def _path(local, start, goal):
    """Small-map steps from start to goal (breadth first)."""
    came, todo = {start: None}, [start]
    for h in todo:
        for n in hx.neighbors(h):
            if n in lc.CELL_SET and n not in came and local.walkable(n):
                came[n] = h
                todo.append(n)
    out, h = [], goal
    while h != start:
        out.append(h)
        h = came[h]
    return out[::-1]


def test_new_save_starts_at_camp_having_seen_around_it():
    save = sv.new_save(SEED)
    assert save["at"] == [0, 0] and save["spot"] == [0, 0]
    assert sv.seen_in(save, (0, 0)) == {(0, 0), *hx.neighbors((0, 0))}
    assert save["trip"] is None


def test_walking_needs_a_trip_and_costs_energy():
    save = sv.new_save(SEED)
    to = next(n for n in hx.neighbors((0, 0)) if sv.local_of(save).walkable(n))
    with pytest.raises(sv.WanderError, match="trip"):
        sv.apply_walk(save, to)
    save = sv.apply_walk(sv.start_trip(save), to)
    assert save["spot"] == list(to)
    assert save["trip"]["energy"] == sv.WALK_ENERGY + wp.team_energy(save["team"]) - 1
    assert save["trip"]["walk"] == sv.WALK_ENERGY - 1  # your own goes first
    assert hx.neighbors(to)[0] in sv.seen_in(save, (0, 0)) or hx.neighbors(to)[0] not in lc.CELL_SET


def test_blocked_and_far_hexes_refuse():
    save = _on_trip()
    local = sv.local_of(save)
    with pytest.raises(sv.WanderError, match="next to you"):
        sv.apply_walk(save, (3, 0))
    blocked = [h for h in lc.CELLS if not local.walkable(h)]
    spot = next(h for h in lc.CELLS if local.walkable(h) and any(n in blocked for n in hx.neighbors(h)))
    save = {**save, "spot": list(spot)}
    with pytest.raises(sv.WanderError, match="in the way"):
        sv.apply_walk(save, next(n for n in hx.neighbors(spot) if n in blocked))


def _exit_step(local, big=(0, 0)):
    """An exit hex and the step across it (in this big hex's frame)."""
    h, d = next((h, d) for h, d in sorted(local.exits.items()) if h not in local.gates)
    f = next(f for e, f in lc.SIDES[d] if e == h)
    far = hx.neighbor(big, d)
    g = lc.to_world(far, f)
    c = lc.center(big)
    return h, d, (g[0] - c[0], g[1] - c[1]), f


def test_crossing_an_edge_walks_into_the_next_big_hex():
    save = _on_trip()
    local = sv.local_of(save)
    h, d, step, f = _exit_step(local)
    after = sv.apply_walk({**save, "spot": list(h)}, step)
    nxt = hx.neighbor((0, 0), d)
    assert after["at"] == list(nxt) and after["spot"] == list(f)
    assert list(nxt) in after["visited"]
    # and back again
    back = sv.apply_walk(after, hx.add(f, (h[0] - step[0], h[1] - step[1])))
    assert back["at"] == [0, 0] and back["spot"] == list(h)


def test_walls_and_the_edge_of_the_world_refuse():
    world = wd.generate(SEED)
    for big in world.hexes:
        local = lc.generate(SEED, big)
        for d in range(6):
            n = hx.neighbor(big, d)
            if n in world.hexes and world.is_open(big, n) and hx.edge_key(big, n) not in world.gates:
                continue
            # a walled edge (or a gate in one) has no way across
            far = lc.generate(SEED, n) if n in world.hexes else None
            for h, f in lc.SIDES[d]:
                assert not (local.walkable(h) and far and far.walkable(f))
    # stepping off the world
    edge = next(b for b in world.hexes if any(hx.neighbor(b, d) not in world.hexes for d in range(6)))
    d = next(d for d in range(6) if hx.neighbor(edge, d) not in world.hexes)
    local = lc.generate(SEED, edge)
    inner = next(h for h in lc.CELLS if local.walkable(h))
    save = {**_on_trip(), "at": list(edge), "spot": list(inner)}
    h, f = lc.SIDES[d][0]
    c = lc.center(edge)
    g = lc.to_world(hx.neighbor(edge, d), f)
    with pytest.raises(sv.WanderError):
        sv.apply_walk({**save, "spot": list(h)}, (g[0] - c[0], g[1] - c[1]))


def test_resting_at_a_campfire_marks_where_a_new_day_starts():
    save = _on_trip()
    h, d, step, _ = _exit_step(sv.local_of(save))
    save = sv.apply_walk({**save, "spot": list(h)}, step)
    nxt = tuple(save["at"])
    for step in _path(sv.local_of(save), tuple(save["spot"]), sv.local_of(save).campfire):
        save = sv.apply_walk(save, step)
    shown = sv.screen(save)
    assert shown["rest"] and shown["action"] == "camp"
    rested = sv.act(save, "camp")
    # it doesn't end the day: same trip, same party; fresh, you're not ready to rest
    assert rested["trip"] == save["trip"] and rested["team"] == save["team"]
    assert nxt in sv.campfires_rested(rested) and "not ready" in rested["events"][0]["text"]
    # out of energy: wake by the nearest campfire you've rested at
    away = next(n for n in hx.neighbors(tuple(save["spot"])) if sv.local_of(save).walkable(n))
    tired = {**rested, "trip": {**rested["trip"], "walk": 1, "pets": [0] * len(rested["team"]), "energy": 1}}
    napped = sv.apply_walk(tired, away)
    assert napped["trip"] is None and napped["note"] == "napped"
    assert napped["at"] == list(nxt) and napped["spot"] == list(sv.local_of(napped).campfire)
    # without resting there, you'd wake at Camp
    assert sv.apply_walk({**tired, "camps": []}, away)["at"] == [0, 0]


def test_it_is_night_only_between_a_day_ending_and_the_next_starting():
    save = _on_trip()
    assert not sv.is_night(sv.new_save(7)) and not sv.is_night(save)
    tonight = sv.end_trip(save)
    assert sv.is_night(tonight) and sv.view(tonight)["night"]
    assert not sv.is_night(sv.start_trip(tonight))
    assert sv.is_night(sv.nap(save))


def test_ending_the_day_mid_fight_drops_the_fight():
    save = {**_on_trip(), "battle": {"round": 1}}
    assert sv.end_trip(save)["battle"] is None
    assert sv.nap(save)["battle"] is None


def test_a_save_left_with_a_fight_but_no_trip_still_loads():
    save = {**sv.end_trip(_on_trip()), "battle": {"round": 1}}
    assert sv.view(save)["battle"] is None


def test_going_home_ends_the_day_from_anywhere():
    save = _on_trip()
    to = next(n for n in hx.neighbors((0, 0)) if sv.local_of(save).walkable(n))
    home = sv.end_trip(sv.apply_walk(save, to))
    assert home["trip"] is None and home["note"] == "rested" and home["spot"] == [0, 0]
    far = {**home, "at": [1, 0], "spot": list(sv.local_of(home, (1, 0)).campfire)}
    again = sv.start_trip(far, from_camp=True)
    assert again["at"] == [0, 0] and again["trip"]["energy"] == FULL


def test_next_day_refills_where_you_are():
    save = _on_trip()
    to = next(n for n in hx.neighbors((0, 0)) if sv.local_of(save).walkable(n))
    tired = {**sv.apply_walk(save, to), "trip": {**sv._spend(save, FULL - 3)["trip"], "used": ["x"]}}
    day = sv.next_day(tired)
    assert day["spot"] == list(to) and day["trip"]["energy"] == FULL and day["trip"]["used"] == []
    fresh = sv.new_save(SEED)
    assert sv.next_day(fresh)["trip"]["energy"] == sv.WALK_ENERGY + wp.team_energy(fresh["team"])


def test_walking_uses_your_own_energy_then_the_pets_evenly():
    save = _on_trip()
    pets = save["trip"]["pets"]
    assert save["trip"]["walk"] == sv.WALK_ENERGY and pets == [m["energy"] for m in TEAM]
    spent = sv._spend(save, sv.WALK_ENERGY + 10)["trip"]
    assert spent["walk"] == 0 and sum(pets) - sum(spent["pets"]) == 10
    assert max(spent["pets"]) - min(spent["pets"]) <= max(pets) - min(pets)  # shared out, not one pet drained
    # food tops up your own first, then the pets'
    back = sv._restore({**save, "trip": spent}, 5)["trip"]
    assert back["walk"] == 5 and back["pets"] == spent["pets"]
    full = sv._restore({**save, "trip": spent}, 999)["trip"]
    assert full["walk"] == sv.WALK_ENERGY and full["pets"] == pets


def test_view_shows_only_what_you_have_seen():
    save = sv.new_save(SEED)
    view = sv.view(save)
    big = {(h["q"], h["r"]) for h in view["big"]["hexes"]}
    assert big == {(0, 0)}  # only where you've been; the rest is just the world's shape
    assert len(view["big"]["shape"]) == len(wd.generate(SEED).hexes)
    tiles = {(t["q"], t["r"]) for t in view["local"]["tiles"]}
    assert tiles == {(0, 0), *hx.neighbors((0, 0))}
    assert view["local"]["campfire"] == [0, 0] and view["local"]["spot"] == [0, 0]


def test_you_see_across_an_edge():
    save = _on_trip()
    h, d, step, f = _exit_step(sv.local_of(save))
    save = sv.apply_walk({**save, "spot": list(h)}, step)
    save = sv.apply_walk(save, next(n for n in hx.neighbors(f) if lc.owner(lc.to_world(tuple(save["at"]), n))[0] == (0, 0)
                                    and sv.standable(save, sv.local_of(save, (0, 0)), lc.owner(lc.to_world(tuple(save["at"]), n))[1])))
    # standing on the edge, what's across it is seen and in the view
    me = lc.to_world(tuple(save["at"]), tuple(save["spot"]))
    view = {(t["q"], t["r"]): t for t in sv.local_view(save)["tiles"]}
    assert all(n in view for n in hx.neighbors(me) if lc.owner(n)[0] in wd.generate(SEED).hexes)
    assert len({t["big"] for t in view.values()}) >= 2


def test_fit_sends_a_lost_player_to_a_campfire():
    old = {"version": 1, "world_version": -1, "seed": SEED, "at": [99, 99], "visited": [[99, 99]]}
    fitted = sv.fit(old)
    assert fitted["at"] == [0, 0] and fitted["spot"] == [0, 0]
    assert fitted["visited"] == [[0, 0]]
    assert fitted["version"] == sv.SAVE_VERSION and fitted["trip"] is None


# --- nooks, fords, clues ---------------------------------------------------------


def _nook(test, seed=SEED):
    """The first (big, spot, nook) in the world that passes test."""
    for big in sorted(wd.generate(seed).hexes):
        local = lc.generate(seed, big)
        for h, nook in sorted(local.nooks.items()):
            if test(nook):
                return big, h, nook
    raise AssertionError("no such nook")


def _standing(big, spot, **extra):
    save = _on_trip()
    return sv._see({**save, "at": list(big), "spot": list(spot), **extra}, big, spot)


def test_caves_go_in_and_out_by_their_door():
    big, h, nook = _nook(lambda n: n.kind == "cave")
    door = nook.doors[0]
    save = _standing(big, door)
    assert list(lc.to_world(big, h)) in [list(g) for g in sv.steps(save)]
    inside = sv.apply_walk(save, h)
    assert inside["spot"] == list(h)
    assert [list(g) for g in sv.steps(inside)] == [list(lc.to_world(big, door))]
    other = next(n for n in hx.neighbors(h) if n != door)
    with pytest.raises(sv.WanderError):
        sv.apply_walk(inside, other)
    assert sv.apply_walk(inside, door)["spot"] == list(door)
    # not from any other side
    side = next((n for n in hx.neighbors(h) if n != door and sv.local_of(save, big).walkable(n)), None)
    if side:
        with pytest.raises(sv.WanderError, match="in the way"):
            sv.apply_walk(_standing(big, side), h)


def test_a_tunnel_goes_through():
    big, h, nook = _nook(lambda n: n.kind == "tunnel")
    a, b = nook.doors
    save = sv.apply_walk(sv.apply_walk(_standing(big, a), h), b)
    assert save["spot"] == list(b)


def test_searching_a_nook_once_and_once_a_trip():
    big, h, nook = _nook(lambda n: n.need is None and "coins" in n.finds and "forage" not in n.finds)
    save = _standing(big, h)
    shown = sv.screen(save)
    assert shown["action"] == "search"
    after = sv.act(save, "search")
    assert [e["kind"] for e in after["events"]] == ["coins"]
    assert sv.screen(after)["action"] is None  # coins are once ever
    assert sv.screen(sv.next_day(after))["action"] is None
    big, h, nook = _nook(lambda n: n.need is None and n.finds == ("forage",))
    save = sv.act(_standing(big, h), "search")
    assert sum(save["items"].values()) == 1 and sv.screen(save)["action"] is None
    assert sv.screen(sv.next_day(save))["action"] == "search"  # forage grows back


def test_nooks_need_type_levels():
    big, h, nook = _nook(lambda n: n.need is not None and n.need[1] >= 3 and n.kind not in lc.IN_WALL)
    kind, need = nook.need
    weak = _standing(big, h, team=[wp.starter(kind, need - 1)])
    assert sv.screen(weak)["action"] is None and "levels" in sv.screen(weak)["text"]
    with pytest.raises(sv.WanderError):
        sv.act(weak, "search")
    # two pets of the type add up
    assert sv.screen({**weak, "team": [wp.starter(kind, need - 1)] * 2})["action"] is not None


def test_fishing_takes_typing():
    big, h, nook = _nook(lambda n: n.kind == "fishing")
    save = _standing(big, h)
    shown = sv.screen(save)
    assert shown["action"] == "fish" and shown["line"]
    assert sum(sv.act(save, "fish", accuracy=1.0)["items"].values()) == 2
    missed = sv.act(save, "fish", accuracy=0.3)
    assert not any(missed["items"].values()) and sv.screen(missed)["action"] is None


def test_a_clue_leads_to_a_cache():
    big, h, nook = _nook(lambda n: n.need is None and "clue" in n.finds)
    save = sv.act(_standing(big, h), "search")
    far, at = lc.clue_target(SEED, big, h)
    assert list(far) in sv.big_view(save)["marks"]
    there = sv._see({**save, "at": list(far), "spot": list(next(n for n in hx.neighbors(at) if lc.generate(SEED, far).walkable(n)))}, far, at)
    assert any(t.get("poi") == "cache" for t in sv.local_view(there)["tiles"])
    dug = sv.apply_walk(there, at)
    assert [e["kind"] for e in dug["events"]] == ["coins"]
    assert list(far) not in sv.big_view(dug)["marks"]


def test_wading_costs_more_without_a_swimmer():
    for big in sorted(wd.generate(SEED).hexes):
        local = lc.generate(SEED, big)
        ford = next((h for h in lc.CELLS if local.tiles[h] == "ford"), None)
        if ford:
            break
    start = next(n for n in hx.neighbors(ford) if local.walkable(n) and n in lc.CELL_SET)
    save = _standing(big, start)
    swim = sv.apply_walk(save, ford)["trip"]["energy"]
    wade = sv.apply_walk({**save, "team": [wp.starter("leaf")]}, ford)["trip"]["energy"]
    assert save["trip"]["energy"] - swim == st.FORD_ENERGY_SWIM
    assert save["trip"]["energy"] - wade == st.FORD_ENERGY




def test_the_log_keeps_the_last_ten():
    save = {**_on_trip(), "events": [{"kind": "found", "text": f"thing {i}"} for i in range(12)]}
    logged = sv._logged(save)
    assert logged["log"] == [f"thing {i}" for i in range(2, 12)]
    assert sv._logged({**logged, "events": [{"kind": "xp", "amount": 5}]})["log"] == logged["log"]


def test_the_bag_says_what_things_are_for():
    tale = st.STORIES["leaf"]
    npc = st.NPCS[("leaf", "leaf")]
    assert npc.name in st.describe(npc.lost)
    assert "vine ladder" in st.describe(f"{st.SHORTCUTS['leaf'].parts[0]} for the vine ladder")
    assert "Temple" in st.describe(tale.key)
    assert "Heartstone" in st.describe(tale.relic)
    assert "board" in st.describe(st.FORAGE["leaf"])
    view = sv.view({**_on_trip(), "items": {tale.key: 1}})
    assert view["about"] == {tale.key: st.describe(tale.key)}


def test_loading_fills_in_fields_added_later(tmp_path):
    from app import db
    with db.open_db(tmp_path / "t.db") as conn:
        conn.execute("INSERT INTO learner (name, created_at) VALUES ('T', 'now')")
        old = {k: v for k, v in sv.new_save(SEED).items() if k != "log"}
        db.save_wander(conn, 1, old)
        assert sv.load(conn, 1)["log"] == []


def test_resting_gives_energy_once_a_day_once_half_gone():
    save = sv._spend(_on_trip(), FULL // 2 + 5)  # Camp's camp is a campfire
    assert sv.screen(save)["action"] == "camp"
    rested = sv.act(save, "camp")
    assert rested["trip"]["energy"] == save["trip"]["energy"] + sv.st.CAMP_ENERGY
    again = sv.act(rested, "camp")
    assert again["trip"]["energy"] == rested["trip"]["energy"] and "already rested" in again["events"][0]["text"]
    # a new day: you can rest again
    tomorrow = sv._spend(sv.next_day(rested), FULL // 2 + 5)
    assert sv.act(tomorrow, "camp")["trip"]["energy"] > tomorrow["trip"]["energy"]
