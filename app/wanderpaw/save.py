"""A player's Wanderpaw save (PLAN.md 11n): their world's seed and what
they've found. The world and its small maps are rebuilt from the seed
(world.py, local.py); the story's words are in story.py.

Where you are: `at`, the big hex, and `spot`, the small hex inside it.
The small maps make one seamless world grid (local.to_world): you walk
small hex by small hex, across big edges wherever both sides are
walkable, and see only your hex and the six touching it; everything
you've seen stays on your map (`seen`: per big hex, a bitmask over
local.CELLS). Every big hex's campfire can be spotted from anywhere
inside it; one you've seen counts as found.

Trips: walking needs a trip. A trip has energy (for now just steps,
TRIP_ENERGY; pets' energy replaces it later). Out of energy, you nap and
wake at the nearest campfire you've found; at a campfire you can end a
trip early. The next trip starts where you are, or at Camp.

Type levels: what a party can do is counted in levels of a type, summed
over its pets (levels()). For now the party is a stand-in list of types
(`party`), each pet at `party_level`, until pets join in phase 4; then a
pet's first type has its level and a second type counts up from 1.

Gates: walking into a gated exit uses the party's field skill if it has
enough levels of the gate's type (st.GATE_LEVELS); a cleared gate stays
cleared. Wading a ford costs st.FORD_ENERGY (less with a swimmer). Quest gates (broken
shortcuts) are repaired by finishing the region's story quest.

Places: forage spots give the region's find once per trip; chests open
once ever (coins); the lost thing of a story quest is picked up by walking
onto it. Enter (act()) talks to town buildings, prays at a shrine (type a
line for energy), opens a temple, or wakes the Heartstone. What happened
on the last move is in `events` (found items, coins, cleared gates, a nap):
the API pays the coins and the page shows the rest.

Nooks (local.Nook): a cave, tunnel or glade is a blocker hex you can only
step into from its doors (and out of to them; a tunnel's two doors make it
a way through). Standing on a nook, Enter shows what's there; if the
party has the levels it needs, Enter again searches (or fishes: type the
line). Coins and clues are found once ever (`found`); forage, energy and
fish once a trip. A clue marks a buried cache (`clues`: clue -> where);
stepping on it digs it up.

Kept forever: the map, cleared gates, opened chests, nook finds, clues, items, story quests,
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

SAVE_VERSION = 4
CAMP: Hex = (0, 0)
TRIP_ENERGY = 120  # steps, until pets bring their own energy
STAND_IN_PARTY = ["leaf", "splash", "ember", "dream", "shock"]
STAND_IN_LEVEL = 5
PARTY_SIZE = 5
DEFAULTS = {
    "trip": None, "note": None, "seen": {}, "visited": [], "party": STAND_IN_PARTY, "party_level": STAND_IN_LEVEL, "items": {},
    "found": [], "clues": {},
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
    """The save after looking around from spot: it and the six touching
    it, whichever big hexes they're in."""
    save = _mark_seen(save, hx.spiral(lc.to_world(big, spot), 1))
    visited = save["visited"] if list(big) in save["visited"] else [*save["visited"], list(big)]
    return {**save, "visited": visited}


def _mark_seen(save: dict, world_hexes) -> dict:
    hexes = world_of(save).hexes
    seen = dict(save["seen"])
    for w in world_hexes:
        b, h = lc.owner(w)
        if b in hexes:
            seen[_key(b)] = format(int(seen.get(_key(b), "0"), 16) | 1 << lc.INDEX[h], "x")
    return {**save, "seen": seen}


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


def levels(save: dict, kind: str) -> int:
    """The party's levels of a type, all its pets together."""
    return save["party"].count(kind) * save["party_level"]


def has_levels(save: dict, need: tuple[str, int] | None) -> bool:
    return need is None or levels(save, need[0]) >= need[1]


def _try_gate(save: dict, local: lc.LocalMap, h: Hex) -> dict:
    """Walking into a gate: clear it with a field skill, or say why not."""
    edge = local.gates[h]
    gate = world_of(save).gates[edge]
    if gate.kind == "quest":
        tale = st.STORIES[gate.region]
        raise WanderError(f"This is {tale.shortcut}, and it's broken. Maybe someone in town can fix it.")
    what, does = st.FIELD_SKILLS[gate.kind]
    name = st.TYPE_NAMES[gate.kind]
    need = st.GATE_LEVELS[gate.need]
    if not has_levels(save, (gate.kind, need)):
        raise WanderError(f"{what} is in the way. It takes {need} {name} levels to get past (you have {levels(save, gate.kind)}).")
    energy = save["trip"]["energy"] - st.GATE_ENERGY
    who = "Your " + name + " pets work together and" if save["party"].count(gate.kind) > 1 else "Your " + name + " pet"
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


def next_day(save: dict) -> dict:
    """A new day: a fresh trip from where you are (whatever's left of
    today's is dropped). For now a dev button; later it costs tokens."""
    return {**start_trip({**save, "trip": None}), "note": "new_day"}


def apply_walk(save: dict, to: Hex) -> dict:
    """One step to a small hex next to you. `to` is in this big hex's
    frame, so past its edge it's a hex of the big hex next door."""
    if not save["trip"]:
        raise WanderError("Start a trip first!")
    save = {**save, "events": []}
    big, spot = tuple(save["at"]), tuple(save["spot"])
    if hx.distance(spot, to) != 1:
        raise WanderError("You can only walk to a place next to you.")
    nbig, h = lc.owner(lc.to_world(big, to))
    if nbig not in world_of(save).hexes:
        raise WanderError("That's the edge of the world.")
    local = local_of(save, nbig)
    why = _blocked(save, big, spot, nbig, h)
    if why == "gate":
        save = _try_gate(save, local, h)
    elif why:
        raise WanderError(why)
    save = {**save, "at": list(nbig), "spot": list(h)}
    save = _see(save, tuple(save["at"]), tuple(save["spot"]))
    save = _arrive(save)
    cost = 1
    if local.tiles[h] == "ford":
        cost = st.FORD_ENERGY_SWIM if levels(save, "splash") >= st.SWIM_LEVELS else st.FORD_ENERGY
    energy = save["trip"]["energy"] - cost
    stats = {**save["stats"], "steps": save["stats"]["steps"] + 1}
    save = {**save, "trip": {**save["trip"], "energy": energy}, "stats": stats}
    return nap(save) if energy <= 0 else save


def _blocked(save: dict, big: Hex, spot: Hex, nbig: Hex, h: Hex) -> str | None:
    """Why you can't step from (big, spot) to the next hex (nbig, h): None
    if you can, "gate" for a gate to try, else words to say."""
    here = local_of(save, big).nooks.get(spot)
    if here and here.doors and (nbig != big or h not in here.doors):
        return "That's solid rock. Go back out the way you came." if here.kind != "glade" else "The trees are too thick that way."
    local = local_of(save, nbig)
    nook = local.nooks.get(h)
    if nook and nook.doors:
        return None if nbig == big and spot in nook.doors else f"The {local.tiles[h]} is in the way."
    if h in local.gates and not cleared(save, local.gates[h]):
        return "gate"
    if not standable(save, local, h):
        return f"The {local.tiles[h].replace('_', ' ')} is in the way."
    return None


def steps(save: dict) -> list[Hex]:
    """The world hexes you can step to (or try a gate at) from here."""
    big, spot = tuple(save["at"]), tuple(save["spot"])
    out = []
    for g in hx.neighbors(lc.to_world(big, spot)):
        nbig, h = lc.owner(g)
        if nbig in world_of(save).hexes and _blocked(save, big, spot, nbig, h) in (None, "gate"):
            out.append(g)
    return out


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
    elif pid in save["clues"].values() and pid not in save["found"]:
        coins = random.randint(*st.CACHE_COINS) + here.ring
        save = {**save, "found": [*save["found"], pid]}
        save = _event(save, kind="coins", amount=coins, text=f"You dig where the clue said... a buried cache! {coins} coins.")
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
    if spot in local.nooks:
        return {"kind": "nook", "region": here.region, "nook": local.nooks[spot]}
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
    if kind == "nook":
        return _nook_screen(save, where["nook"], region, pid)
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
        if not has_levels(save, (region, 1)):
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


def _left(save: dict, nook: lc.Nook, pid: str) -> list[str]:
    """The finds still to take at a nook."""
    used = (save["trip"] or _trip(0))["used"]
    return [f for f in nook.finds
            if (f in st.ONCE_FINDS and f"{pid}:{f}" not in save["found"])
            or (f in st.DAILY_FINDS and f"{pid}:{f}" not in used)]


def _nook_screen(save: dict, nook: lc.Nook, region: str, pid: str) -> dict:
    words = st.NOOKS[nook.kind]
    pick = sum(map(ord, pid))
    lines = [words.text]
    lines += [st.LORE[pick % len(st.LORE)]] if "lore" in nook.finds else []
    lines += [st.TIPS[pick % len(st.TIPS)]] if "tip" in nook.finds else []
    lines += [st.CREATURE_LINE] if "creature" in nook.finds else []
    out = {"title": words.title, "action": None}
    if not has_levels(save, nook.need):
        kind, need = nook.need
        lines.append(words.locked.format(need=need, type=st.TYPE_NAMES[kind], have=levels(save, kind)))
    elif "fish" in _left(save, nook, pid):
        out.update(action="fish", label="Cast a line", line=st.FISH_LINES[pick % len(st.FISH_LINES)])
        lines.append("Type the line to reel one in.")
    elif _left(save, nook, pid):
        out.update(action="search", label=words.search)
    elif any(f in st.ONCE_FINDS + st.DAILY_FINDS for f in nook.finds):
        lines.append("You've found everything here." if not any(f in st.DAILY_FINDS for f in nook.finds)
                     else "Nothing more today. Come back next trip.")
    return {**out, "text": " ".join(lines)}


def _search(save: dict, nook: lc.Nook, region: str, pid: str, accuracy: float) -> dict:
    """Taking what's left at a nook."""
    big, spot = tuple(save["at"]), tuple(save["spot"])
    ring = world_of(save).hexes[big].ring
    for f in _left(save, nook, pid):
        mark = f"{pid}:{f}"
        if f in st.ONCE_FINDS:
            save = {**save, "found": [*save["found"], mark]}
        else:
            save = {**save, "trip": {**save["trip"], "used": [*save["trip"]["used"], mark]}}
        if f == "coins":
            coins = random.randint(*st.NOOK_COINS) + ring
            save = _event(save, kind="coins", amount=coins, text=f"{coins} coins!")
        elif f == "forage":
            save = _give(save, st.FORAGE[region])
            save = _event(save, kind="found", text=f"You found a {st.FORAGE[region]}!")
        elif f == "energy":
            trip = save["trip"]
            save = {**save, "trip": {**trip, "energy": min(trip["max"], trip["energy"] + st.NOOK_ENERGY)}}
            save = _event(save, kind="found", text=f"You feel refreshed. +{st.NOOK_ENERGY} energy.")
        elif f == "fish":
            n = 2 if accuracy >= 1 else 1 if accuracy >= 0.6 else 0
            if n:
                save = _give(save, st.FISH[region], n)
            save = _event(save, kind="found", text=f"You caught {n} {st.FISH[region]}{'s' if n > 1 else ''}!" if n
                          else "It got away! Try again next trip.")
        elif f == "clue":
            far, at = lc.clue_target(save["seed"], big, spot)
            save = {**save, "clues": {**save["clues"], pid: _place_id(far, at)}}
            name = world_of(save).hexes[far].name
            save = _event(save, kind="found", text=f"A clue! It points to something buried in {name}. It's on your map.")
        elif f == "view":
            save = _mark_seen(save, hx.spiral(lc.to_world(big, spot), st.LOOKOUT_RADIUS))
            save = _event(save, kind="found", text="You can see a long way from here!")
    return save


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
    if action in ("search", "fish"):
        return _search(save, place(save)["nook"], region, pid, accuracy)
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


def walk_world(conn, learner_id: int, to: Hex) -> dict:
    """walk(), with `to` a world hex."""
    def step(s: dict) -> dict:
        c = lc.center(tuple(s["at"]))
        return apply_walk(s, (to[0] - c[0], to[1] - c[1]))
    return _write(conn, learner_id, step)


def begin(conn, learner_id: int, from_camp: bool) -> dict:
    return _write(conn, learner_id, lambda s: start_trip(s, from_camp))


def new_day(conn, learner_id: int) -> dict:
    return _write(conn, learner_id, next_day)


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
    # ... and where a clue points.
    marks += [list(_unkey(c.split("|")[0])) for c in save["clues"].values() if c not in save["found"]]
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
    if pid in save["clues"].values() and pid not in save["found"]:
        out["poi"] = "cache"
    return out


VIEW_RADIUS = 7  # small hexes shown around you


def local_view(save: dict) -> dict:
    """What you've seen around you, in world hexes, whichever big hexes
    they're in (so the map just goes on)."""
    world = world_of(save)
    big, spot = tuple(save["at"]), tuple(save["spot"])
    here = world.hexes[big]
    local = local_of(save)
    me = lc.to_world(big, spot)
    seen: dict[Hex, set[Hex]] = {}
    tiles = []
    ocean = []
    for g in hx.spiral(me, VIEW_RADIUS):
        b, h = lc.owner(g)
        if b not in world.hexes:
            ocean.append(g)
            continue
        if b not in seen:
            seen[b] = seen_in(save, b)
        if h not in seen[b]:
            continue
        m = local_of(save, b)
        tile = _tile(save, m, b, h)
        tile.pop("exit", None)
        tiles.append({**tile, "q": g[0], "r": g[1], "biome": m.biome, "big": _key(b)})
    # Past the edge of the world: open sea, once you've seen the shore beside it.
    shore = {(t["q"], t["r"]) for t in tiles if t["kind"] == lc.EDGE_OF_WORLD}
    tiles += [{"q": g[0], "r": g[1], "kind": lc.EDGE_OF_WORLD, "biome": None}
              for g in ocean if any(n in shore for n in hx.neighbors(g))]
    return {
        "big": list(big), "name": here.name, "region": here.region, "biome": here.biome, "special": here.special,
        "radius": VIEW_RADIUS, "spot": list(me), "campfire": list(lc.to_world(big, local.campfire)),
        "tiles": tiles, "steps": [list(g) for g in steps(save)],
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
        "levels": {t: levels(save, t) for t in wd.REGIONS if levels(save, t)},
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
    if spot not in lc.CELL_SET or not (standable(save, local, spot) or spot in local.nooks):
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


def set_party(conn, learner_id: int, party: list[str], level: int | None = None) -> dict:
    """The stand-in party's types and level (until real pets join)."""
    if len(party) > PARTY_SIZE or any(t not in wd.REGIONS for t in party):
        raise WanderError("A party is up to five of ember, splash, leaf, dream, shock.")
    if level is not None and not 1 <= level <= 20:
        raise WanderError("Pick a level from 1 to 20.")
    return _write(conn, learner_id, lambda s: {**s, "party": list(party), "party_level": level or s["party_level"], "events": []})


def reset(conn, learner_id: int, seed: int | None = None) -> dict:
    save = new_save(seed if seed is not None else random.randrange(2**31))
    db.save_wander(conn, learner_id, save)
    return save
