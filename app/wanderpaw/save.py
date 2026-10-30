"""A player's Wanderpaw save (PLAN.md 11n): their world's seed and what
they've found. The world and its small maps are rebuilt from the seed
(world.py, local.py); the story's words are in story.py.

Where you are: `at`, the big hex, and `spot`, the small hex inside it.
You walk small hex by small hex and see only your hex and the six touching
it; everything you've seen stays on your map (`seen`: per big hex, a
bitmask over local.CELLS). Leaving by an exit hex puts you on the matching
exit of the neighbor. Every big hex's campfire can be spotted from
anywhere inside it; one you've seen counts as found.

Trips: walking needs a trip. A trip has energy (for now just steps,
TRIP_ENERGY; pets' energy replaces it later). Out of energy, you nap and
wake at the nearest campfire you've found; at a campfire you can end a
trip early. The next trip starts where you are, or at Camp.

Gates: walking into a gated exit uses the party's field skill if it has
enough pets of the gate's type (`party`, a stand-in list of types until
pets join in phase 4); a cleared gate stays cleared. Quest gates (broken
shortcuts) are repaired by finishing the region's story quest.

Places: forage spots give the region's find once per trip; chests open
once ever (coins); the lost thing of a story quest is picked up by walking
onto it. Enter (act()) talks to town buildings, prays at a shrine (type a
line for energy), opens a temple, or wakes the Heartstone. What happened
on the last move is in `events` (found items, coins, cleared gates, a nap):
the API pays the coins and the page shows the rest.

Kept forever: the map, cleared gates, opened chests, items, story quests,
temples, relics. Reset every trip: forage, shrines, inns, side quests.

view() only ever returns what the player has seen, so the browser can't
spoil the map.
"""

from __future__ import annotations

import random

from app import db
from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import story as st
from app.wanderpaw import world as wd
from app.wanderpaw.hexes import Hex

SAVE_VERSION = 3
CAMP: Hex = (0, 0)
TRIP_ENERGY = 120  # steps, until pets bring their own energy
STAND_IN_PARTY = ["leaf", "splash", "ember", "dream", "shock"]
PARTY_SIZE = 5
DEFAULTS = {
    "trip": None, "note": None, "seen": {}, "visited": [], "party": STAND_IN_PARTY, "items": {},
    "cleared": [], "chests": [], "quests": {}, "temples": [], "charms": 0, "buffs": {},
    "finished": False, "stats": {"trips": 0, "steps": 0}, "events": [],
}


class WanderError(ValueError):
    """Kid-readable, like FarmError."""


def _key(h: Hex) -> str:
    return f"{h[0]},{h[1]}"


def _unkey(k: str) -> Hex:
    q, r = k.split(",")
    return (int(q), int(r))


def _edge_id(edge: tuple[Hex, Hex]) -> str:
    return f"{_key(edge[0])}|{_key(edge[1])}"


def _place_id(big: Hex, spot: Hex) -> str:
    return f"{_key(big)}|{_key(spot)}"


def seen_in(save: dict, big: Hex) -> set[Hex]:
    mask = int(save["seen"].get(_key(big), "0"), 16)
    return {h for i, h in enumerate(lc.CELLS) if mask >> i & 1}


def seen_all(save: dict) -> dict[str, list[list[int]]]:
    """Every small hex seen, per big hex ("q,r")."""
    return {k: sorted(map(list, seen_in(save, _unkey(k)))) for k in save["seen"]}


def _see(save: dict, big: Hex, spot: Hex) -> dict:
    """The save after looking around from spot: it and the six touching it."""
    mask = int(save["seen"].get(_key(big), "0"), 16)
    for h in [spot, *hx.neighbors(spot)]:
        if h in lc.INDEX:
            mask |= 1 << lc.INDEX[h]
    visited = save["visited"] if list(big) in save["visited"] else [*save["visited"], list(big)]
    return {**save, "seen": {**save["seen"], _key(big): format(mask, "x")}, "visited": visited}


def new_save(seed: int) -> dict:
    save = {**DEFAULTS, "version": SAVE_VERSION, "world_version": wd.WORLD_VERSION, "seed": seed,
            "at": list(CAMP), "spot": [0, 0]}
    return _see(save, CAMP, (0, 0))


def world_of(save: dict) -> wd.World:
    return wd.generate(save["seed"])


def local_of(save: dict, big: Hex | None = None) -> lc.LocalMap:
    return lc.generate(save["seed"], tuple(big or save["at"]))


def fit(save: dict) -> dict:
    """The save, made to fit after the generators (or the save layout)
    changed: places that no longer exist are forgotten and a player who
    can't stand where they are goes to that big hex's campfire, or Camp."""
    world = world_of(save)
    save = {**DEFAULTS, **save, "version": SAVE_VERSION, "world_version": wd.WORLD_VERSION, "trip": None}
    save["visited"] = [v for v in save["visited"] if tuple(v) in world.hexes]
    save["seen"] = {k: v for k, v in save["seen"].items() if _unkey(k) in world.hexes}
    at = tuple(save["at"]) if tuple(save["at"]) in world.hexes else CAMP
    local = local_of(save, at)
    spot = tuple(save.get("spot") or local.campfire)
    if not standable(save, local, spot):
        spot = local.campfire
    save = {**save, "at": list(at), "spot": list(spot)}
    return _see(_see(save, CAMP, (0, 0)), at, spot)


def load(conn, learner_id: int, rng: random.Random | None = None) -> dict:
    save = db.get_wander(conn, learner_id)
    if save is None:
        save = new_save((rng or random.Random()).randrange(2**31))
        db.save_wander(conn, learner_id, save)
    elif save.get("world_version") != wd.WORLD_VERSION or save.get("version") != SAVE_VERSION:
        save = fit(save)
        db.save_wander(conn, learner_id, save)
    return save


def campfires_found(save: dict) -> list[Hex]:
    found = []
    for k in save["seen"]:
        big = _unkey(k)
        if local_of(save, big).campfire in seen_in(save, big):
            found.append(big)
    return sorted(found)


def nearest_campfire(save: dict, big: Hex) -> Hex:
    """The found campfire fewest big-map steps from big (then the nearest
    as the crow flies)."""
    steps = wd.distances_from(world_of(save), big)
    return min(campfires_found(save), key=lambda c: (steps.get(c, 999), hx.distance(c, big), c))


# --- gates and standing ---------------------------------------------------------------


def cleared(save: dict, edge: tuple[Hex, Hex]) -> bool:
    return _edge_id(edge) in save["cleared"]


def standable(save: dict, local: lc.LocalMap, h: Hex) -> bool:
    return local.walkable(h) or (h in local.gates and cleared(save, local.gates[h]))


def party_has(save: dict, kind: str, need: int) -> bool:
    return save["party"].count(kind) >= need


def _try_gate(save: dict, local: lc.LocalMap, h: Hex) -> dict:
    """Walking into a gate: clear it with a field skill, or say why not."""
    edge = local.gates[h]
    gate = world_of(save).gates[edge]
    if gate.kind == "quest":
        tale = st.STORIES[gate.region]
        raise WanderError(f"This is {tale.shortcut}, and it's broken. Maybe someone in town can fix it.")
    what, does = st.FIELD_SKILLS[gate.kind]
    name = st.TYPE_NAMES[gate.kind]
    if not party_has(save, gate.kind, gate.need):
        pets = "two " + name + " pets" if gate.need == 2 else "a " + name + " pet"
        raise WanderError(f"{what} is in the way. You need {pets} to get past.")
    energy = save["trip"]["energy"] - st.GATE_ENERGY
    who = "Your two " + name + " pets work together and" if gate.need == 2 else "Your " + name + " pet"
    return {
        **save,
        "cleared": [*save["cleared"], _edge_id(edge)],
        "trip": {**save["trip"], "energy": energy},
        "events": [*save["events"], {"kind": "cleared", "text": f"{who} {does}!"}],
    }


# --- trips ----------------------------------------------------------------------


def _trip(energy: int = TRIP_ENERGY) -> dict:
    return {"energy": energy, "max": TRIP_ENERGY, "used": [], "side": {}}


def start_trip(save: dict, from_camp: bool = False) -> dict:
    if save["trip"]:
        raise WanderError("You're already out exploring!")
    if from_camp:
        save = {**save, "at": list(CAMP), "spot": [0, 0]}
    stats = {**save["stats"], "trips": save["stats"]["trips"] + 1}
    save = {**save, "trip": _trip(), "note": None, "events": [], "stats": stats}
    return _see(save, tuple(save["at"]), tuple(save["spot"]))


def end_trip(save: dict) -> dict:
    """Head home from a campfire."""
    if not save["trip"]:
        raise WanderError("You're not on a trip.")
    if tuple(save["spot"]) != local_of(save).campfire:
        raise WanderError("Find a campfire to rest at first.")
    return {**save, "trip": None, "note": "rested", "events": []}


def nap(save: dict) -> dict:
    """Out of energy: wake at the nearest campfire you've found."""
    big = nearest_campfire(save, tuple(save["at"]))
    save = {**save, "at": list(big), "spot": list(local_of(save, big).campfire), "trip": None, "note": "napped",
            "events": [*save["events"], {"kind": "nap"}]}
    return _see(save, big, tuple(save["spot"]))


def apply_walk(save: dict, to: Hex) -> dict:
    """One step to a small hex next to you, or out through an exit (to is
    then the hex just past the edge of the map)."""
    if not save["trip"]:
        raise WanderError("Start a trip first!")
    save = {**save, "events": []}
    big, spot = tuple(save["at"]), tuple(save["spot"])
    local = local_of(save)
    if hx.distance(spot, to) != 1:
        raise WanderError("You can only walk to a place next to you.")
    if to in lc.CELL_SET:
        if to in local.gates and not cleared(save, local.gates[to]):
            save = _try_gate(save, local, to)
        elif not standable(save, local, to):
            raise WanderError(f"The {local.tiles[to].replace('_', ' ')} is in the way.")
        save = {**save, "spot": list(to)}
    else:
        d = hx.direction_to(spot, to)
        if local.exits.get(spot) != d:
            raise WanderError("There's no way out here.")
        nxt = hx.neighbor(big, d)
        save = {**save, "at": list(nxt), "spot": list(lc.mirror(spot, d))}
    save = _see(save, tuple(save["at"]), tuple(save["spot"]))
    save = _arrive(save)
    energy = save["trip"]["energy"] - 1
    stats = {**save["stats"], "steps": save["stats"]["steps"] + 1}
    save = {**save, "trip": {**save["trip"], "energy": energy}, "stats": stats}
    return nap(save) if energy <= 0 else save


def _give(save: dict, item: str, n: int = 1) -> dict:
    return {**save, "items": {**save["items"], item: save["items"].get(item, 0) + n}}


def _event(save: dict, **event) -> dict:
    return {**save, "events": [*save["events"], event]}


def _arrive(save: dict) -> dict:
    """Picking up whatever is where you just stepped."""
    big, spot = tuple(save["at"]), tuple(save["spot"])
    local = local_of(save)
    poi = local.pois.get(spot)
    here = world_of(save).hexes[big]
    pid = _place_id(big, spot)
    if poi == "forage" and pid not in save["trip"]["used"]:
        item = st.FORAGE[here.region]
        save = _give(save, item)
        save = {**save, "trip": {**save["trip"], "used": [*save["trip"]["used"], pid]}}
        save = _event(save, kind="found", text=f"You found a {item}!")
    elif poi == "chest" and pid not in save["chests"]:
        coins = random.randint(*st.CHEST_COINS) + here.ring
        save = {**save, "chests": [*save["chests"], pid]}
        save = _event(save, kind="coins", amount=coins, text=f"A treasure chest! {coins} coins inside.")
    elif poi == "lost":
        tale = st.STORIES[here.region]
        if save["quests"].get(here.region) != "done" and not save["items"].get(tale.lost):
            save = _give(save, tale.lost)
            save = _event(save, kind="found", text=f"You found the {tale.lost}! Someone must be missing it.")
    return save


# --- going in: buildings, shrines, temples, the Heartstone ------------------------------


def place(save: dict) -> dict | None:
    """What you can go into where you're standing (None: nothing)."""
    big, spot = tuple(save["at"]), tuple(save["spot"])
    local = local_of(save)
    here = world_of(save).hexes[big]
    tile = local.tiles.get(spot)
    if spot in local.buildings:
        return {"kind": local.buildings[spot], "region": here.region}
    if local.pois.get(spot) == "shrine":
        return {"kind": "shrine", "region": here.region}
    if tile == "temple":
        return {"kind": "temple", "region": here.region}
    if tile == "stone":
        return {"kind": "heartstone", "region": here.region}
    return None


def screen(save: dict) -> dict | None:
    """What going in shows: a title, what's said, and what Enter does."""
    where = place(save)
    if not where:
        return None
    kind, region = where["kind"], where["region"]
    trip = save["trip"] or _trip(0)
    pid = _place_id(tuple(save["at"]), tuple(save["spot"]))
    if kind == "elder":
        tale = st.STORIES[region]
        state = save["quests"].get(region)
        lost_at = world_of(save).hexes[world_of(save).quests[region].lost].name
        if state == "done":
            return {"title": tale.elder, "text": f"Thanks again! The {tale.key} will open the {st.TYPE_NAMES[region]} Temple.", "action": None}
        if save["items"].get(tale.lost):
            return {"title": tale.elder, "text": f"My {tale.lost}! You found it! Please, take the {tale.key}. And my friends will mend {tale.shortcut} for you.", "action": "give", "label": "Give it back"}
        if state == "asked":
            return {"title": tale.elder, "text": f"Any luck finding my {tale.lost}? Try {lost_at}.", "action": None}
        return {"title": tale.elder, "text": f"Oh dear, I've lost my {tale.lost}. {tale.lost_hint} Somewhere around {lost_at}. Could you look for it?", "action": "ask", "label": "I'll look"}
    if kind == "board":
        item = st.FORAGE[region]
        wanted = trip["side"].get(pid)
        have = save["items"].get(item, 0)
        if wanted and have >= st.SIDE_QUEST_COUNT:
            return {"title": "Notice board", "text": f"You have {have} {item}s. Hand in {st.SIDE_QUEST_COUNT} for {st.SIDE_QUEST_COINS} coins?", "action": "board", "label": "Hand them in"}
        if wanted:
            return {"title": "Notice board", "text": f"Wanted: {st.SIDE_QUEST_COUNT} {item}s. You have {have}.", "action": None}
        return {"title": "Notice board", "text": f"Wanted: {st.SIDE_QUEST_COUNT} {item}s, for {st.SIDE_QUEST_COINS} coins.", "action": "board", "label": "Take the job"}
    if kind == "inn":
        if pid in trip["used"]:
            return {"title": "Inn", "text": "You're full! Come back next trip.", "action": None}
        return {"title": "Inn", "text": f"A warm bowl of soup? (+{st.INN_ENERGY} energy)", "action": "inn", "label": "Yes please"}
    if kind == "shop":
        return {"title": "Shop", "text": "The shopkeeper is still unpacking. Come back soon!", "action": None}
    if kind == "house":
        lines = st.HOUSE_LINES
        return {"title": "A cozy house", "text": lines[sum(map(ord, pid)) % len(lines)], "action": None}
    if kind == "shrine":
        if pid in trip["used"]:
            return {"title": "Shrine", "text": "The shrine is quiet. Come back next trip.", "action": None}
        line = st.SHRINE_LINES[sum(map(ord, pid)) % len(st.SHRINE_LINES)]
        return {"title": "Shrine", "text": "Type the words on the stone:", "action": "shrine", "label": "Begin", "line": line}
    if kind == "temple":
        name = st.TYPE_NAMES[region]
        tale = st.STORIES[region]
        if region in save["temples"]:
            return {"title": f"{name} Temple", "text": f"The temple is open. The {tale.relic} is safe with you.", "action": None}
        if not save["items"].get(tale.key):
            return {"title": f"{name} Temple", "text": f"The door is sealed. There's a little hole shaped like a {tale.key}.", "action": None}
        if not party_has(save, region, 1):
            return {"title": f"{name} Temple", "text": f"The {tale.key} fits! But the door only opens for a {name} pet.", "action": None}
        return {"title": f"{name} Temple", "text": f"The {tale.key} fits, and your {name} pet glows.", "action": "temple", "label": "Open the door"}
    if kind == "heartstone":
        if save["finished"]:
            return {"title": "The Heartstone", "text": "The Heartstone hums happily.", "action": "credits", "label": "See the ending"}
        have = len(save["temples"])
        if have < len(wd.REGIONS):
            return {"title": "The Heartstone", "text": f"Five hollows in the stone. {have} of them glow. Bring all five relics.", "action": None}
        return {"title": "The Heartstone", "text": "Five hollows, five relics. The stone is waiting.", "action": "heartstone", "label": "Place the relics"}
    return None


def act(save: dict, action: str, accuracy: float = 1.0) -> dict:
    """Doing what the screen offers (its `action`)."""
    if not save["trip"]:
        raise WanderError("Start a trip first!")
    shown = screen(save)
    if not shown or shown["action"] != action:
        raise WanderError("There's nothing to do here.")
    save = {**save, "events": []}
    region = place(save)["region"]
    pid = _place_id(tuple(save["at"]), tuple(save["spot"]))
    trip = save["trip"]
    if action == "ask":
        return {**save, "quests": {**save["quests"], region: "asked"}}
    if action == "give":
        tale = st.STORIES[region]
        items = {**save["items"], tale.lost: 0, tale.key: 1}
        shortcut = world_of(save).quests[region].shortcut
        save = {**save, "items": items, "quests": {**save["quests"], region: "done"},
                "cleared": [*save["cleared"], _edge_id(shortcut)]}
        return _event(save, kind="found", text=f"You got the {tale.key}! And {tale.shortcut} is fixed.")
    if action == "board":
        item = st.FORAGE[region]
        if pid in trip["side"]:
            save = {**save, "items": {**save["items"], item: save["items"][item] - st.SIDE_QUEST_COUNT},
                    "trip": {**trip, "side": {k: v for k, v in trip["side"].items() if k != pid}}}
            return _event(save, kind="coins", amount=st.SIDE_QUEST_COINS, text=f"Thanks! {st.SIDE_QUEST_COINS} coins.")
        return {**save, "trip": {**trip, "side": {**trip["side"], pid: item}}}
    if action == "inn":
        energy = min(trip["max"], trip["energy"] + st.INN_ENERGY)
        save = {**save, "trip": {**trip, "energy": energy, "used": [*trip["used"], pid]}}
        return _event(save, kind="found", text="Yum! You feel ready to go.")
    if action == "shrine":
        gain = round(st.SHRINE_ENERGY * max(0.0, min(1.0, accuracy)))
        energy = min(trip["max"], trip["energy"] + gain)
        save = {**save, "trip": {**trip, "energy": energy, "used": [*trip["used"], pid]}}
        return _event(save, kind="found", text=f"The shrine glows. +{gain} energy.")
    if action == "temple":
        tale = st.STORIES[region]
        save = {**save, "temples": [*save["temples"], region], "charms": save["charms"] + 1,
                "buffs": {**save["buffs"], region: tale.buff}}
        save = _give(save, tale.relic)
        return _event(save, kind="relic", text=f"You found the {tale.relic}! Your {st.TYPE_NAMES[region]} pet becomes {tale.buff}, and you get a befriending charm.")
    if action == "heartstone":
        return _event({**save, "finished": True}, kind="credits")
    if action == "credits":
        return _event(save, kind="credits")
    raise WanderError("There's nothing to do here.")


# --- writing ------------------------------------------------------------------------


def _write(conn, learner_id: int, change) -> dict:
    save = change(load(conn, learner_id))
    db.save_wander(conn, learner_id, save)
    for e in save["events"]:
        if e["kind"] == "coins":
            db.add_coins(conn, learner_id, e["amount"], "game", ref="wanderpaw")
    return save


def walk(conn, learner_id: int, to: Hex) -> dict:
    return _write(conn, learner_id, lambda s: apply_walk(s, to))


def begin(conn, learner_id: int, from_camp: bool) -> dict:
    return _write(conn, learner_id, lambda s: start_trip(s, from_camp))


def finish(conn, learner_id: int) -> dict:
    return _write(conn, learner_id, end_trip)


def go_in(conn, learner_id: int, action: str, accuracy: float = 1.0) -> dict:
    return _write(conn, learner_id, lambda s: act(s, action, accuracy))


# --- what the player sees ---------------------------------------------------------


def big_view(save: dict) -> dict:
    world = world_of(save)
    visited = {tuple(v) for v in save["visited"]}
    seen = visited | {n for v in visited for n in hx.neighbors(v) if n in world.hexes}
    hexes = []
    for h in sorted(seen):
        out = wd.hex_json(world.hexes[h])
        out["visited"] = h in visited
        if h not in visited:
            out["name"] = None
        hexes.append(out)
    edges = []
    for k, v in world.edges.items():
        if k[0] in visited or k[1] in visited:
            edge = wd.edge_json(k, v, world.gates.get(k))
            if "gate" in edge:
                edge["gate"]["cleared"] = cleared(save, k)
            edges.append(edge)
    # Where an elder asked you to look, even before you've been there.
    marks = [list(world.quests[r].lost) for r, s in save["quests"].items() if s == "asked"]
    return {"at": save["at"], "radius": wd.MAP_RADIUS, "hexes": hexes, "edges": edges, "marks": marks}


def _tile(save: dict, local: lc.LocalMap, big: Hex, h: Hex) -> dict:
    out = lc.tile_json(local, h)
    if h in local.gates and cleared(save, local.gates[h]):
        out["kind"] = lc.CLEARED_TILES.get(out["kind"], "path")
    poi = out.get("poi")
    pid = _place_id(big, h)
    gone = (
        (poi == "forage" and save["trip"] and pid in save["trip"]["used"])
        or (poi == "chest" and pid in save["chests"])
        or (poi == "lost" and (save["items"].get(st.STORIES[world_of(save).hexes[big].region].lost)
                               or save["quests"].get(world_of(save).hexes[big].region) == "done"))
    )
    if gone:
        del out["poi"]
    return out


def local_view(save: dict) -> dict:
    world = world_of(save)
    big, spot = tuple(save["at"]), tuple(save["spot"])
    here = world.hexes[big]
    local = local_of(save)
    seen = seen_in(save, big)
    near = {spot, *hx.neighbors(spot)}
    tiles = [{**_tile(save, local, big, h), "near": h in near} for h in lc.CELLS if h in seen]
    # Standing on an exit: the land just past it, where the next step goes.
    ghosts = []
    if spot in local.exits:
        d = local.exits[spot]
        nxt = world.hexes[hx.neighbor(big, d)]
        to = hx.neighbor(spot, d)
        ghosts.append({"q": to[0], "r": to[1], "biome": nxt.biome, "region": nxt.region,
                       "name": nxt.name if list(nxt.coord) in save["visited"] else None})
    return {
        "big": list(big), "name": here.name, "region": here.region, "biome": here.biome, "special": here.special,
        "radius": lc.LOCAL_RADIUS, "spot": list(spot), "campfire": list(local.campfire),
        "tiles": tiles, "ghosts": ghosts,
    }


def quests_view(save: dict) -> list[dict]:
    world = world_of(save)
    out = []
    for region, state in save["quests"].items():
        tale = st.STORIES[region]
        q = world.quests[region]
        out.append({
            "region": region, "state": state, "elder": tale.elder, "lost": tale.lost,
            "town": world.hexes[q.town].name, "lost_at": world.hexes[q.lost].name,
            "found": bool(save["items"].get(tale.lost)),
        })
    return out


def view(save: dict) -> dict:
    return {
        "big": big_view(save),
        "local": local_view(save),
        "trip": save["trip"],
        "note": save["note"],
        "events": save["events"],
        "screen": screen(save),
        "campfires": len(campfires_found(save)),
        "at_camp": tuple(save["at"]) == CAMP,
        "party": save["party"],
        "items": {k: v for k, v in sorted(save["items"].items()) if v},
        "quests": quests_view(save),
        "temples": save["temples"],
        "charms": save["charms"],
        "buffs": save["buffs"],
        "finished": save["finished"],
        "credits": st.CREDITS if any(e["kind"] == "credits" for e in save["events"]) else None,
        "stats": save["stats"],
    }


# --- lab (admin) moves: no walls, no fog --------------------------------------------


def teleport(conn, learner_id: int, big: Hex, spot: Hex | None = None) -> dict:
    save = load(conn, learner_id)
    if big not in world_of(save).hexes:
        raise WanderError("That place isn't on the map.")
    local = local_of(save, big)
    spot = spot if spot is not None else local.campfire
    if spot not in lc.CELL_SET or not standable(save, local, spot):
        raise WanderError("You can't stand there.")
    save = _see({**save, "at": list(big), "spot": list(spot), "events": []}, big, spot)
    db.save_wander(conn, learner_id, save)
    return save


def refill(conn, learner_id: int) -> dict:
    """Full energy (starting a trip where you are if you're not on one)."""
    def change(s: dict) -> dict:
        s = s if s["trip"] else start_trip(s)
        return {**s, "trip": {**s["trip"], "energy": TRIP_ENERGY}}
    return _write(conn, learner_id, change)


def set_party(conn, learner_id: int, party: list[str]) -> dict:
    """The stand-in party's types (until real pets join)."""
    if len(party) > PARTY_SIZE or any(t not in wd.REGIONS for t in party):
        raise WanderError("A party is up to five of ember, splash, leaf, dream, shock.")
    return _write(conn, learner_id, lambda s: {**s, "party": list(party), "events": []})


def reset(conn, learner_id: int, seed: int | None = None) -> dict:
    save = new_save(seed if seed is not None else random.randrange(2**31))
    db.save_wander(conn, learner_id, save)
    return save
