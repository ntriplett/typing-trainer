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

Trips: walking needs a trip. A trip has energy: your own WALK_ENERGY for
walking (`walk`), then each pet's (`pets`, by place in the team). Steps
come out of your own first, then the pets' (from whoever has the most, so
it's shared evenly); later, battles take theirs. `energy` / `max` are the
totals. Food and springs top up your own first, then the pets'. Out of energy, you nap and
wake at the nearest campfire you've found; at a campfire you can end a
trip early. The next trip starts where you are, or at Camp.

The party: `party` is the pet ids you picked (None until you pick: then
your first pets, starred first); `team` is what goes on the trip
(pets.member: name, types, levels, energy), empty slots filled with
temporary starters. The team is rebuilt from the pets between trips and
when they level up. What a party can do is counted in levels of a type,
summed over its pets (levels()). XP (quests, temples, caches, the harder
nooks) goes to the team's real pets as `xp` events, which the writer
applies to their records (the wander_pet table).

Gates: walking into a gated exit uses the party's field skill if it has
enough levels of the gate's type (its `level`); a cleared gate stays
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

from app import db, pet_genes
from app.wanderpaw import hexes as hx
from app.wanderpaw import battle as bt
from app.wanderpaw import critters as cr
from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app.wanderpaw import quests as qs
from app.wanderpaw import shop as sh
from app.wanderpaw import story as st
from app.wanderpaw import world as wd
from app.wanderpaw.hexes import Hex

SAVE_VERSION = 5
CAMP: Hex = (0, 0)
PARTY_SIZE = wp.PARTY_SIZE
DEFAULTS = {
    "trip": None, "note": None, "seen": {}, "visited": [], "party": None, "team": wp.team([]), "items": {},
    "found": [], "clues": {}, "log": [], "bridges": {}, "menders": {}, "rumors": [],
    "battle": None, "fighters": None, "combos": [], "camps": [], "levelups": [],
    "bosses": [], "cleared": [], "chests": [], "quests": {}, "temples": [], "buffs": {}, "bought": {}, "camp_friends": [],
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
    elif DEFAULTS.keys() - save.keys():  # a field added since it was saved
        save = {**DEFAULTS, **save}
    return save


def campfires_found(save: dict) -> list[Hex]:
    found = []
    for k in save["seen"]:
        big = _unkey(k)
        if local_of(save, big).campfire in seen_in(save, big):
            found.append(big)
    return sorted(found)


def campfires_rested(save: dict) -> list[Hex]:
    """The campfires you've rested at (Camp always counts): where a new
    day can start."""
    return sorted({CAMP, *(_unkey(k) for k in save["camps"])})


def nearest_campfire(save: dict, big: Hex) -> Hex:
    """The campfire you've rested at fewest big-map steps from big (then
    the nearest as the crow flies)."""
    steps = wd.distances_from(world_of(save), big)
    return min(campfires_rested(save), key=lambda c: (steps.get(c, 999), hx.distance(c, big), c))


# --- gates and standing ---------------------------------------------------------------


def cleared(save: dict, edge: tuple[Hex, Hex]) -> bool:
    return _edge_id(edge) in save["cleared"]


def standable(save: dict, local: lc.LocalMap, h: Hex) -> bool:
    return local.walkable(h) or (h in local.gates and cleared(save, local.gates[h]))


def levels(save: dict, kind: str) -> int:
    """The party's levels of a type, all its pets together."""
    return wp.team_levels(save["team"], kind)


def gate_level(save: dict, base: int) -> int:
    """What a gate takes now: every relic out makes the world harder, gates too."""
    return base + cr.RELIC_LEVELS * relics_out(save)


def has_levels(save: dict, need: tuple[str, int] | None) -> bool:
    return need is None or levels(save, need[0]) >= need[1]


def _cap(s: str) -> str:
    return s[0].upper() + s[1:]


# --- quests: quest-givers, bridges, lost things, keys (quests.py) ------------------------


def _plan(save: dict) -> qs.Plan:
    return qs.plan(save["seed"])


def _npc(g: qs.Giver) -> st.Npc:
    return st.NPCS[(g.region, g.shortcut)]


def _bridge_name(shortcut: str) -> str:
    return st.SHORTCUTS[shortcut].name


def _part(save: dict, shortcut: str, side: Hex) -> str:
    """The bag name of the part waiting by a bridge on one side."""
    parts = st.SHORTCUTS[shortcut].parts
    return f"{parts[0] if world_of(save).hexes[side].region == shortcut else parts[1]} for {_bridge_name(shortcut)}"


def _parts(save: dict, shortcut: str, near: str) -> list[str]:
    """A bridge's two parts, the one on `near`'s side first."""
    sides = list(qs.bridge_sides(world_of(save), shortcut))
    sides.sort(key=lambda b: world_of(save).hexes[b].region != near)
    return [_part(save, shortcut, b) for b in sides]


def _partner(save: dict, g: qs.Giver) -> qs.Giver:
    """The quest-giver about the same bridge, in the town on its other side."""
    return next(o for o in _plan(save).givers.values() if o.shortcut == g.shortcut and o.id != g.id)


def _mends(save: dict, g: qs.Giver) -> bool:
    """g will mend the bridge (the first of the pair you took on), or
    could still (neither yet)."""
    return save["menders"].get(g.shortcut) in (None, g.id)


def _has_lost(save: dict, g: qs.Giver) -> bool:
    return bool(save["items"].get(_npc(g).lost))


def _lost_gone(save: dict, g: qs.Giver) -> bool:
    """Picked up already (or brought back)."""
    return _has_lost(save, g) or save["quests"].get(g.id) == "done"


def _and(words: list[str]) -> str:
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def _place_name(save: dict, big: Hex) -> str:
    return world_of(save).hexes[big].name


def _hint(save: dict, g: qs.Giver) -> str:
    spot = g.lost
    return st.fill(st.FETCH_HINTS[spot.kind], item=_npc(g).lost, place=_place_name(save, spot.big))


def _bump_bridge(save: dict, shortcut: str) -> dict:
    """Walking into a broken shortcut: you can't cross, but you pick up the
    part on your side, and with 3 levels of the far side's type a pet
    brings that side's part across too. Now it's in the journal."""
    world = world_of(save)
    big = tuple(save["at"])
    sides = qs.bridge_sides(world, shortcut)
    far = next(b for b in sides if b != big)
    towns = " or ".join(_place_name(save, world.quests[world.hexes[b].region].town) for b in sides)
    save = {**save, "bridges": {**save["bridges"], shortcut: "found"}}
    texts = [f"{st.SHORTCUTS[shortcut].broken} Someone in {towns} might know how to fix it."]
    if save["quests"].get(save["menders"].get(shortcut)) != "done":
        mine, theirs = _part(save, shortcut, big), _part(save, shortcut, far)
        if not save["items"].get(mine):
            save = _give(save, mine)
            texts.append(f"You pick up the {mine.split(' for ')[0]} on this side.")
        kind = sides[far]
        if not save["items"].get(theirs):
            if has_levels(save, (kind, gate_level(save, qs.FETCH_LEVEL))):
                save = _give(save, theirs)
                texts.append(f"Your {st.TYPE_NAMES[kind]} pet {st.CARRY[kind]} the {theirs.split(' for ')[0]} across from the far side!")
            else:
                texts.append(f"The {theirs.split(' for ')[0]} is on the far side. A pet with {gate_level(save, qs.FETCH_LEVEL)} {st.TYPE_NAMES[kind]} levels could bring it across, or walk around.")
    return _event(save, kind="bridge", text=" ".join(texts))


def _giver_screen(save: dict, g: qs.Giver) -> dict:
    npc, state = _npc(g), save["quests"].get(g.id)
    bridge = _bridge_name(g.shortcut)
    title = npc.name
    if state == "done":
        if g.region not in save["rumors"]:
            return {"title": title, "text": f"{npc.thanks} Oh, and one more thing...", "action": "rumor", "label": "What is it?"}
        key = st.STORIES[g.region].key
        found = save["items"].get(key) or g.region in save["temples"]
        return {"title": title, "text": npc.thanks + ("" if found else f" Good luck finding the {key}."), "action": None}
    if _mends(save, g):
        near, far = _parts(save, g.shortcut, g.region)
        if state != "asked":
            return {"title": title, "action": "ask", "label": "I'll help",
                    "text": f"{npc.hello} {npc.mend} I could {npc.fix}, but I need a favor first. "
                            f"{_hint(save, g)} Bring that back, plus the {near.split(' for ')[0]} from this side of "
                            f"{bridge} and the {far.split(' for ')[0]} from the far side, and it's as good as done."}
        missing = [x for x in (npc.lost, near, far) if not save["items"].get(x)]
        if not missing:
            return {"title": title, "text": f"My {npc.lost}! And everything we need! Let's get to work!", "action": "mend", "label": "Here you go"}
        return {"title": title, "action": None,
                "text": f"I still need the {_and([m.split(' for ')[0] for m in missing])}. " + ("" if _has_lost(save, g) else _hint(save, g))}
    # The partner is mending the bridge: this one trains a pet.
    if state != "asked":
        return {"title": title, "action": "ask", "label": "I'll look",
                "text": f"{npc.hello} Could you help me? {_hint(save, g)} Find it, and {npc.train} A whole level's worth!"}
    if not _has_lost(save, g):
        return {"title": title, "text": f"Any luck finding my {npc.lost}? {_hint(save, g)}", "action": None}
    pets = [m for m in save["team"] if m["id"] and m["level"] < wp.MAX_LEVEL]
    if not pets:
        return {"title": title, "text": f"My {npc.lost}! Bring along one of your own pets with some growing left to do and I'll train it.", "action": None}
    options = [{"action": "train", "arg": m["id"], "label": f"Train {m['name']} (level {m['level']})"} for m in pets]
    return {"title": title, "text": f"My {npc.lost}! Thank you! Which pet should I train?", "options": options,
            "action": "train", "label": options[0]["label"]}


def _quest_finds_here(save: dict) -> list[dict]:
    """Lost things and keys hidden right here, still to take: options."""
    big, spot = tuple(save["at"]), tuple(save["spot"])
    out = []
    for g in _plan(save).givers.values():
        if (g.lost.big, g.lost.at) == (big, spot) and g.lost.check and not _lost_gone(save, g):
            out.append({"action": "fetch", "arg": g.id, "label": f"Get the {_npc(g).lost}", "check": g.lost.check})
    for region, key in _plan(save).keys.items():
        name = st.STORIES[region].key
        if (key.big, key.at) == (big, spot) and not save["items"].get(name) and region not in save["temples"]:
            out.append({"action": "fetch", "arg": f"key:{region}", "label": f"Get the {name}", "check": key.check})
    return out


def _try_gate(save: dict, local: lc.LocalMap, h: Hex) -> dict:
    """Walking into a gate: clear it with a field skill, or say why not."""
    edge = local.gates[h]
    gate = world_of(save).gates[edge]
    what, does = st.FIELD_SKILLS[gate.kind]
    name = st.TYPE_NAMES[gate.kind]
    need = gate_level(save, gate.level)
    short = need - levels(save, gate.kind)
    if 0 < short <= sh.LUCKY_LEVELS and save["items"].get(sh.LUCKY):
        save = _give(save, sh.LUCKY, -1)
        save = _event(save, kind="found", text=f"Your {sh.LUCKY} glows, and it's just enough!")
    elif not has_levels(save, (gate.kind, need)):
        raise WanderError(f"{what} is in the way. It takes {need} {name} levels to get past (you have {levels(save, gate.kind)}).")
    save = _spend(save, st.GATE_ENERGY)
    helpers = [m["name"] for m in save["team"] if gate.kind in m["types"]]
    who = " and ".join(helpers[:2]) + (" work together and" if len(helpers) > 1 else "")
    return {
        **save,
        "cleared": [*save["cleared"], _edge_id(edge)],
        "events": [*save["events"], {"kind": "cleared", "text": f"{who} {does}!"}],
    }


# --- wild creatures and battles (critters.py, battle.py) ----------------------------


def day(save: dict) -> int:
    """Which day it is (a new one every trip): where wanderers turn up."""
    return save["stats"]["trips"]


def relics_out(save: dict) -> int:
    """Relics taken from their temples: every creature grows with each."""
    return len(save["temples"])


def critter_at(save: dict, big: Hex, h: Hex) -> cr.Critter | None:
    """A creature still standing there today (None: none, or beaten)."""
    c = cr.at(save["seed"], big, day(save), relics_out(save)).get(h)
    beaten = (save["trip"] or {}).get("beaten", [])
    return c if c and c.id not in beaten else None


def fighters(save: dict) -> list[int]:
    """The two team places that fight: the ones picked (with energy left),
    then the first others with energy."""
    pets = (save["trip"] or {}).get("pets") or [m["energy"] for m in save["team"]]
    able = [i for i in range(len(save["team"])) if i < len(pets) and pets[i] > 0]
    picked = [i for i in (save.get("fighters") or []) if i in able]
    return (picked + [i for i in able if i not in picked])[:2]


def _critter_by_id(save: dict, cid: str) -> cr.Critter:
    big = tuple(int(v) for v in cid.split(":")[1].split(","))
    if cid.startswith("boss:"):
        return cr.temple_boss(save["seed"], cid.split(":")[2], big, relics_out(save))
    return next(c for c in cr.at(save["seed"], big, day(save), relics_out(save)).values() if c.id == cid)


def _start_battle(save: dict, c: cr.Critter) -> dict:
    who = fighters(save)
    if not who:
        raise WanderError("Your pets are too tired to fight. Rest at a campfire, or go round.")
    used = (save["trip"] or {}).get("reborn", [])
    pets = (save["trip"] or {}).get("pets") or [m["energy"] for m in save["team"]]
    battle = {**bt.start(c, who, bt.bench_keys(save["team"], who)), "start_energy": {str(i): pets[i] for i in who},
              "reborn": [i for i in who if i not in used and bt.has_reborn(save["team"][i])]}
    title = f"{bt.TIERS[c.tier]['name']} " if c.tier else ""
    return _event({**save, "battle": battle}, kind="battle",
                  text=f"A level {c.level} {title.lower()}{c.species.replace('_', ' ')} blocks the way!")


def battle_turn(save: dict, picks: list[dict], rng: random.Random | None = None) -> dict:
    """One round of the battle: picks are each fighter's {move, slips}."""
    b = save.get("battle")
    if not b or b["over"]:
        raise WanderError("There's no battle going on.")
    save = {**save, "events": []}
    rng = rng or random.Random()
    try:
        b, pets, mana = bt.turn(b, _fighting_team(save, b), save["trip"]["pets"], picks, rng, _mana(save))
    except ValueError as exc:
        raise WanderError(str(exc)) from exc
    trip = save["trip"]
    # (once a day: the trip remembers who's been reborn)
    reborn = [*trip.get("reborn", []), *(i for i in b.get("reborn_used", []) if i not in trip.get("reborn", []))]
    save = {**save, "battle": b, "trip": {**trip, "pets": pets, "mana": mana, "energy": trip["walk"] + sum(pets), "reborn": reborn}}
    if b.get("gift_xp"):
        place, amount = b.pop("gift_xp")
        if save["team"][place]["id"]:
            save = _event(save, kind="xp", amount=amount, pets=[save["team"][place]["id"]])
    for line in b["log"]:
        save = _event(save, kind="hit", text=line["text"])
        if line.get("combo") and line["combo"] not in save["combos"]:
            # a combo you've never set off: into the combo book
            save = {**save, "combos": [*save["combos"], line["combo"]]}
            says = next(c.says for c in bt.COMBOS.values() if c.name == line["combo"])
            save = _event(save, kind="combo", text=f"New combo: {line['combo']}! {says}")
            ids = [save["team"][i]["id"] for i in b["fighters"] if save["team"][i]["id"]]
            if ids:
                save = _event(save, kind="xp", amount=bt.COMBO_XP, pets=ids)
    if b["over"] == "won":
        c = _critter_by_id(save, b["critter"])
        save = {**save, "trip": {**save["trip"], "beaten": [*save["trip"].get("beaten", []), c.id]}}
        ids = [save["team"][i]["id"] for i in b["fighters"] if save["team"][i]["id"]]
        gain = bt.xp(b, save["team"])
        if "good_company" in (b.get("bench") or []):
            gain = round(gain * bt.GOOD_COMPANY)
        save = _event(save, kind="won", text=f"You won! The {b['species']} scampers off.")
        if bt.tier_coins(b):
            save = _event(save, kind="coins", amount=bt.tier_coins(b), text=f"It leaves behind {bt.tier_coins(b)} coins.")
        if b.get("tier") == "boss":
            save = {**save, "bosses": [*save["bosses"], b["critter"].split(":")[2]]}
        if b.get("coins"):
            save = _event(save, kind="coins", amount=b["coins"], text=f"Golden Flame! {b['coins']} coins.")
        if ids:
            save = _event(save, kind="xp", amount=gain, pets=ids)
            for i in b["fighters"]:
                me = save["team"][i]
                partner = [save["team"][j] for j in b["fighters"] if j != i]
                if me["id"]:
                    save = _event(save, kind="fought", pet=me["id"], partners=[t for p in partner for t in p["types"]])
    elif b["over"] == "lost":
        save = _event(save, kind="lost", text="Your fighters are worn out. They'll rest till tomorrow.")
    return save


def _ward_fades(save: dict, b: dict) -> dict:
    """A Ward's extra energy lasts only for the battle."""
    bases = b.get("ward_base") or {}
    if not bases:
        return save
    pets = [min(e, bases[str(i)]) if str(i) in bases else e for i, e in enumerate(save["trip"]["pets"])]
    trip = save["trip"]
    return {**save, "trip": {**trip, "pets": pets, "energy": trip["walk"] + sum(pets)}}


def end_battle(save: dict) -> dict:
    """Leave a finished battle: step onto the creature's hex if you won;
    out of pet energy after losing, nap."""
    b = save.get("battle")
    if not b or not b["over"]:
        raise WanderError("The battle isn't over.")
    save = _ward_fades({**save, "battle": None, "events": []}, b)
    if b["over"] == "won" and b.get("tier") == "boss":
        return save  # it stood in the temple's door: you're still there
    if b["over"] == "won":
        c = _critter_by_id(save, b["critter"])
        save = _see({**save, "at": list(c.big), "spot": list(c.at)}, c.big, c.at)
        save = _arrive(save)
    elif not sum(save["trip"]["pets"]):
        return nap(save)
    return save


def flee(save: dict) -> dict:
    """Run away (before it's over): it costs your own walking energy."""
    b = save.get("battle")
    if not b or b["over"]:
        raise WanderError("There's no battle to run from.")
    save = _spend(_ward_fades({**save, "battle": None, "events": []}, b), st.FLEE_ENERGY)
    save = _event(save, kind="fled", text="You back away. Phew!")
    return nap(save) if save["trip"]["energy"] <= 0 else save


def pick_fighters(save: dict, slots: list[int]) -> dict:
    if save.get("battle"):
        raise WanderError("Not in the middle of a battle!")
    if len(slots) > 2 or len(set(slots)) != len(slots) or any(not 0 <= i < len(save["team"]) for i in slots):
        raise WanderError("Pick up to two of your party to fight.")
    return {**save, "fighters": list(slots), "events": []}


def _fighting_team(save: dict, b: dict) -> list[dict]:
    """The team, as a Bright Idea on the bench makes it for this battle."""
    if "bright_idea" not in (b.get("bench") or []):
        return save["team"]
    return [{**m, "bright": True} for m in save["team"]]


def battle_view(save: dict) -> dict | None:
    b = save.get("battle")
    if not b:
        return None
    pets, mana = save["trip"]["pets"], _mana(save)
    team = _fighting_team(save, b)
    keyed = {c.key: c for c in bt.CAPSTONES.values()}
    return {**b, "befriend": _befriend_offer(save, b), "looks": cr_looks(b), "intent": bt.foe_intent(b, team, pets), "bench_helps": [{"name": keyed[k].name, "says": keyed[k].says} for k in b.get("bench") or []], "fighters": [
        {"place": i, "name": save["team"][i]["name"], "species": save["team"][i]["species"], "level": save["team"][i]["level"],
         "types": save["team"][i]["types"], "energy": pets[i], "max": bt.battle_energy(b, save["team"], i),
         "ward": max(0, pets[i] - (b.get("ward_base") or {}).get(str(i), pets[i])),
         "mana": mana[i], "max_mana": save["team"][i]["mana"], "focused": i in b.get("focus", []),
         "genes": save["team"][i].get("genes"), "growth": save["team"][i].get("growth", 10),
         "asleep": bt.asleep_now(b, pets) == i, "marked": str(i) in (b.get("pet_marks") or {}),
         "moves": bt.battle_moves(b, i, team[i], mana[i])}
        for i in b["fighters"]]}


def combo_book(save: dict) -> list[dict]:
    """Every combo, by the mark and the hit: found ones say what they do."""
    return [{"mark": mark, "hit": kind, "name": c.name if c.name in save["combos"] else None,
             "says": c.says if c.name in save["combos"] else None}
            for (mark, kind), c in bt.COMBOS.items()]


def cr_looks(b: dict) -> dict:
    species = b["species"].replace(" ", "_")
    return wp.tier_looks(species, b["seed"], b["tier"]) if b.get("tier") else wp.looks(species, b["seed"])


# --- trips ----------------------------------------------------------------------


WALK_ENERGY = 50  # your own, just for walking: used before the pets'


def walk_max(save: dict) -> int:
    """The most walking energy you can have."""
    return WALK_ENERGY + (sh.BOOTS_WALK if save["items"].get(sh.BOOTS) else 0)


def _forage_count(save: dict) -> int:
    return 2 if save["items"].get(sh.SATCHEL) else 1


def _trip(team: list[dict] | None = None, extra_walk: int = 0) -> dict:
    pets = [m["energy"] for m in team or []]
    walk = WALK_ENERGY + extra_walk if team is not None else 0
    return {"walk": walk, "pets": pets, "energy": walk + sum(pets), "max": walk + sum(pets), "used": [], "side": {},
            "beaten": [], "mana": [m["mana"] for m in team or []]}


def _mana(save: dict) -> list[int]:
    """Each pet's mana left today (full, for a trip from before mana)."""
    return list(save["trip"].get("mana") or [m["mana"] for m in save["team"]])


def _spend(save: dict, n: int) -> dict:
    """Energy for walking: your own first, then the pets', from whoever has the most."""
    trip = save["trip"]
    walk, pets = trip.get("walk", trip["energy"]), list(trip.get("pets", []))
    take = min(walk, n)
    walk -= take
    for _ in range(n - take):
        if pets and max(pets) > 0:
            i = pets.index(max(pets))
            pets[i] -= 1
    return {**save, "trip": {**trip, "walk": walk, "pets": pets, "energy": walk + sum(pets)}}


def _restore(save: dict, n: int) -> dict:
    """Energy back: your own first (up to WALK_ENERGY), then the pets' (the lowest first)."""
    trip = save["trip"]
    walk, pets = trip.get("walk", trip["energy"]), list(trip.get("pets", []))
    most = [m["energy"] for m in save["team"]][: len(pets)]
    add = min(n, max(0, walk_max(save) - walk)) if "walk" in trip else n
    walk += add
    for _ in range(n - add):
        room = [i for i, e in enumerate(pets) if e < most[i]]
        if not room:
            break
        i = min(room, key=lambda i: pets[i])
        pets[i] += 1
    return {**save, "trip": {**trip, "walk": walk, "pets": pets, "energy": walk + sum(pets)}}


def start_trip(save: dict, from_camp: bool = False) -> dict:
    if save["trip"]:
        raise WanderError("You're already out exploring!")
    if from_camp:
        save = {**save, "at": list(CAMP), "spot": [0, 0]}
    stats = {**save["stats"], "trips": save["stats"]["trips"] + 1}
    save = {**save, "trip": _trip(save["team"], walk_max(save) - WALK_ENERGY), "note": None, "events": [], "stats": stats, "battle": None, "fighters": None}
    return _see(save, tuple(save["at"]), tuple(save["spot"]))


def end_trip(save: dict) -> dict:
    """End the day and go home (from wherever you are): the next day starts
    at the nearest campfire you've rested at."""
    if not save["trip"]:
        raise WanderError("You're not on a trip.")
    big = nearest_campfire(save, tuple(save["at"]))
    save = _see({**save, "at": list(big), "spot": list(local_of(save, big).campfire)}, big, local_of(save, big).campfire)
    return {**save, "trip": None, "note": "rested", "events": []}


def nap(save: dict) -> dict:
    """Out of energy: the day's over; wake at the nearest campfire you've rested at."""
    big = nearest_campfire(save, tuple(save["at"]))
    save = {**save, "at": list(big), "spot": list(local_of(save, big).campfire), "trip": None, "note": "napped",
            "events": [*save["events"], {"kind": "nap", "text": "All tired out! You curl up and sleep. Tomorrow you'll wake by the nearest campfire you've rested at."}]}
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
    if save.get("battle"):
        raise WanderError("You're in the middle of a battle!")
    why = _blocked(save, big, spot, nbig, h)
    if why == "critter":
        c = critter_at(save, nbig, h)
        if not save["trip"].get("cloak") or c.tier or c.guardian:
            return _start_battle(save, c)
        trip = save["trip"]
        save = {**save, "trip": {**trip, "cloak": trip["cloak"] - 1, "beaten": [*trip.get("beaten", []), c.id]}}
        save = _event(save, kind="found", text=f"Your {sh.CLOAK} hides you, and you slip past the {c.species.replace('_', ' ')}.")
        why = None
    if why == "gate" and world_of(save).gates[local.gates[h]].kind == "quest":
        return _bump_bridge(save, world_of(save).gates[local.gates[h]].region)
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
    trip = save["trip"]
    if trip.get("free_steps", 0) < bt.TRAIL_RUNNER_STEPS and any(bt.capstone_of(m).key == "trail_runner" for m in save["team"] if bt.capstone_of(m)):
        save = {**save, "trip": {**trip, "free_steps": trip.get("free_steps", 0) + 1}}
        cost = 0
    save = _spend(save, cost)
    save = {**save, "stats": {**save["stats"], "steps": save["stats"]["steps"] + 1}}
    return nap(save) if save["trip"]["energy"] <= 0 else save


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
    if critter_at(save, nbig, h):
        return "critter"
    if not standable(save, local, h):
        return f"The {local.tiles[h].replace('_', ' ')} is in the way."
    return None


# How long the word to step onto a hex is, by what's there: a letter for
# paths and the like, longer for rougher going.
STEP_WORDS = {"path": "letter", "plaza": "letter", "court": "letter", "bridge": "letter", "building": "letter", "campfire": "letter",
              "camp": "letter", "temple": "letter", "stone": "letter", "grass": "short", "flowers": "short",
              "sand": "short", "ford": "medium"}
STEP_WORD_NOOK = "medium"  # going into a cave, glade, ...
STEP_WORD_GATE = "long"


def steps(save: dict) -> list[Hex]:
    """The world hexes you can step to (or try a gate at) from here."""
    big, spot = tuple(save["at"]), tuple(save["spot"])
    out = []
    for g in hx.neighbors(lc.to_world(big, spot)):
        nbig, h = lc.owner(g)
        if nbig in world_of(save).hexes and _blocked(save, big, spot, nbig, h) in (None, "gate", "critter"):
            out.append(g)
    return out


def step_word(save: dict, g: Hex) -> str:
    """The word length for stepping onto world hex g."""
    big, h = lc.owner(g)
    local = local_of(save, big)
    if h in local.gates and not cleared(save, local.gates[h]) or critter_at(save, big, h):
        return STEP_WORD_GATE
    if h in local.nooks and local.nooks[h].doors:
        return STEP_WORD_NOOK
    return STEP_WORDS.get(local.tiles[h], "short")


def _give(save: dict, item: str, n: int = 1) -> dict:
    return {**save, "items": {**save["items"], item: save["items"].get(item, 0) + n}}


def _event(save: dict, **event) -> dict:
    return {**save, "events": [*save["events"], event]}


def _xp(save: dict, amount: int) -> dict:
    """XP for every real pet in the team (the writer saves it)."""
    if not any(m["id"] for m in save["team"]):
        return save
    return _event(save, kind="xp", amount=amount)


def _arrive(save: dict) -> dict:
    """Picking up whatever is where you just stepped."""
    big, spot = tuple(save["at"]), tuple(save["spot"])
    local = local_of(save)
    poi = local.pois.get(spot)
    here = world_of(save).hexes[big]
    pid = _place_id(big, spot)
    if poi == "forage" and pid not in save["trip"]["used"]:
        item = st.FORAGE[here.region]
        save = _give(save, item, _forage_count(save))
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
        save = _xp(save, st.XP_CACHE)
    for g in _plan(save).givers.values():
        if (g.lost.big, g.lost.at) == (big, spot) and not g.lost.check and not _lost_gone(save, g):
            save = _give(save, _npc(g).lost)
            save = _event(save, kind="found", text=f"You found a {_npc(g).lost}! {_npc(g).name} must be missing it.")
    return save


# --- going in: buildings, shrines, temples, the Heartstone ------------------------------


def place(save: dict) -> dict | None:
    """What you can go into where you're standing (None: nothing)."""
    big, spot = tuple(save["at"]), tuple(save["spot"])
    local = local_of(save)
    here = world_of(save).hexes[big]
    tile = local.tiles.get(spot)
    if spot in local.buildings:
        role = local.buildings[spot]
        if role.startswith("quest:"):
            g = next(g for g in _plan(save).givers.values() if g.town == big and g.house == spot)
            return {"kind": "giver", "region": here.region, "giver": g}
        return {"kind": role, "region": here.region}
    if local.pois.get(spot) == "shrine":
        return {"kind": "shrine", "region": here.region}
    if spot in local.nooks:
        return {"kind": "nook", "region": here.region, "nook": local.nooks[spot]}
    if spot == local.campfire:
        return {"kind": "campfire", "region": here.region}
    if tile == "temple":
        return {"kind": "temple", "region": here.region}
    if tile == "stone":
        return {"kind": "heartstone", "region": here.region}
    return None


TOWNSFOLK = ("inn", "shop", "house")


def _townsfolk(kind: str, region: str, pid: str) -> tuple[str, str]:
    """(title, what they say) for an inn, shop or house in a region's town."""
    if kind == "inn":
        return st.INNS.get(region, "Inn"), ""
    if kind == "shop":
        return st.SHOPS.get(region, "Shop"), ""
    houses = st.HOUSES.get(region) or [("A cozy house", "Lovely weather for wandering, isn't it?")]
    return houses[sum(map(ord, pid)) % len(houses)]


def _bridge_to_ask(save: dict, region: str) -> str | None:
    """A broken shortcut on this region's borders you've found and that
    nobody here has taken on yet (its region), or None."""
    if region not in wd.REGIONS:
        return None
    for shortcut in qs.givers_in(region):
        if save["bridges"].get(shortcut) and not save["menders"].get(shortcut):
            return shortcut
    return None


def screen(save: dict) -> dict | None:
    """What going in shows: a title, what's said, and what Enter does."""
    where = place(save)
    if not where:
        return None
    kind, region = where["kind"], where["region"]
    trip = save["trip"] or _trip()
    pid = _place_id(tuple(save["at"]), tuple(save["spot"]))
    if kind == "nook":
        return _nook_screen(save, where["nook"], region, pid)
    if kind == "giver":
        return _giver_screen(save, where["giver"])
    if kind == "campfire":
        known = tuple(save["at"]) in campfires_rested(save)
        shown = {"title": "Campfire", "rest": True, "action": "camp", "label": "Rest by the fire",
                 "text": "A warm, crackly fire." + (" A new day can start here." if known else
                                                    " Rest a while, and a new day can start here.")}
        return {**shown, "friends": True} if tuple(save["at"]) == CAMP else shown
    if kind == "board":
        item = st.FORAGE[region]
        wanted = trip["side"].get(pid)
        have = save["items"].get(item, 0)
        if wanted and have >= st.SIDE_QUEST_COUNT:
            return {"title": "Notice board", "text": f"You have {have} {item}s. Hand in {st.SIDE_QUEST_COUNT} for {st.SIDE_QUEST_COINS} coins?", "action": "board", "label": "Hand them in"}
        if wanted:
            return {"title": "Notice board", "text": f"Wanted: {st.SIDE_QUEST_COUNT} {item}s. You have {have}.", "action": None}
        return {"title": "Notice board", "text": f"Wanted: {st.SIDE_QUEST_COUNT} {item}s, for {st.SIDE_QUEST_COINS} coins.", "action": "board", "label": "Take the job"}
    if kind in TOWNSFOLK and _bridge_to_ask(save, region):
        bridge = _bridge_name(_bridge_to_ask(save, region))
        return {"title": _townsfolk(kind, region, pid)[0], "text": "Hello, traveler! Can I help you?", "action": "ask_bridge", "label": f"Can anyone fix {bridge}?"}
    if kind == "inn":
        title = _townsfolk(kind, region, pid)[0]
        if pid in trip["used"]:
            return {"title": title, "text": "You're full! Come back next trip.", "action": None}
        return {"title": title, "text": f"A warm bowl of soup? (+{st.INN_ENERGY} {{energy}})", "action": "inn", "label": "Yes please"}
    if kind == "shop":
        flavor = sh.FLAVORS[sh.SHOP_FLAVOR[region]][0]
        return {"title": f"{_townsfolk(kind, region, pid)[0]} ({flavor})", "text": sh.KEEPERS[region], "action": "shop", "label": "See what's for sale",
                "stock": sh.stock(region, save["bought"].get(region, {}), save["items"], bool(save["finished"]))}
    if kind == "house":
        title, line = _townsfolk(kind, region, pid)
        return {"title": title, "text": line, "action": None}
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
        if region not in save["bosses"]:
            return {"title": f"{name} Temple", "text": f"The {tale.key} fits, and your {name} pet glows. But something huge stands guard before the relic.", "action": "boss", "label": "Face the guardian"}
        return {"title": f"{name} Temple", "text": f"The guardian is gone. The way to the {tale.relic} is clear.", "action": "temple", "label": "Open the door"}
    if kind == "heartstone":
        if save["finished"]:
            return {"title": "The Heartstone", "text": "The Heartstone hums happily.", "action": "credits", "label": "See the ending"}
        have = len(save["temples"])
        if have < len(wd.REGIONS):
            return {"title": "The Heartstone", "text": f"The great hall is quiet. Five tall pillars ring the Heartstone, one for each type, each with a hollow at the top. {have} of them glow. Bring all five relics home.", "action": None}
        return {"title": "The Heartstone", "text": "Five hollows, five relics. The stone is waiting.", "action": "heartstone", "label": "Place the relics"}
    return None


def _left(save: dict, nook: lc.Nook, pid: str) -> list[str]:
    """The finds still to take at a nook."""
    used = (save["trip"] or _trip())["used"]
    return [f for f in nook.finds
            if (f in st.ONCE_FINDS and f"{pid}:{f}" not in save["found"])
            or (f in st.DAILY_FINDS and f"{pid}:{f}" not in used)]


def _nook_screen(save: dict, nook: lc.Nook, region: str, pid: str) -> dict:
    shown = _plain_nook_screen(save, nook, region, pid)
    finds = _quest_finds_here(save)
    if not finds:
        return shown
    options, lines = [], [shown["text"]]
    for f in finds:
        kind, need = f.pop("check")
        if has_levels(save, (kind, need)):
            options.append(f)
        else:
            lines.append(f"Something glints in here, out of reach. It takes {need} {st.TYPE_NAMES[kind]} levels (you have {levels(save, kind)}).")
    if shown["action"]:
        options.append({"action": shown["action"], "label": shown["label"]})
    out = {**shown, "text": " ".join(lines)}
    if options:
        out.update(options=options, action=options[0]["action"], label=options[0]["label"])
    return out


def _plain_nook_screen(save: dict, nook: lc.Nook, region: str, pid: str) -> dict:
    words = st.NOOKS[nook.kind]
    pick = sum(map(ord, pid))
    lines = [words.text]
    lines += [st.LORE[pick % len(st.LORE)]] if "lore" in nook.finds else []
    lines += [st.TIPS[pick % len(st.TIPS)]] if "tip" in nook.finds else []
    lines += [st.CREATURE_LINE] if "creature" in nook.finds else []
    out = {"title": words.title, "action": None}
    if not has_levels(save, nook.need):
        kind, need = nook.need
        lines.append(st.fill(words.locked, need=need, type=st.TYPE_NAMES[kind], have=levels(save, kind)))
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
    if nook.need and not any(f"{pid}:{f}" in save["found"] for f in nook.finds):
        save = _xp(save, st.XP_HARD_NOOK)
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
            save = _give(save, st.FORAGE[region], _forage_count(save))
            save = _event(save, kind="found", text=f"You found a {st.FORAGE[region]}!")
        elif f == "energy":
            save = _restore(save, st.NOOK_ENERGY)
            save = _event(save, kind="found", text=f"You feel refreshed. +{st.NOOK_ENERGY} {{energy}}.")
        elif f == "fish":
            n = 2 if accuracy >= 1 else 1 if accuracy >= 0.6 else 0
            if n and save["items"].get(sh.ROD):
                n += 1
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


def act(save: dict, action: str, accuracy: float = 1.0, arg=None) -> dict:
    """Doing what the screen offers (its `action`, or one of its `options`
    with its `arg`)."""
    if not save["trip"]:
        raise WanderError("Start a trip first!")
    shown = screen(save)
    offered = shown and (shown.get("options") or [{"action": shown["action"], "arg": None}])
    if not offered or not any(o["action"] == action and o.get("arg") == arg for o in offered):
        raise WanderError("There's nothing to do here.")
    save = {**save, "events": []}
    region = place(save)["region"]
    pid = _place_id(tuple(save["at"]), tuple(save["spot"]))
    trip = save["trip"]
    if action in ("search", "fish"):
        return _search(save, place(save)["nook"], region, pid, accuracy)
    if action == "camp":
        # a new day can start here from now on, however the rest goes
        texts = []
        if tuple(save["at"]) not in campfires_rested(save):
            save = {**save, "camps": [*save["camps"], _key(tuple(save["at"]))]}
            texts.append("A new day can start here now.")
        if trip.get("rested"):
            texts.insert(0, "You've already rested today.")
        elif trip["energy"] > trip["max"] / 2:
            texts.insert(0, "You're not ready to rest yet.")
        else:
            save = _restore({**save, "trip": {**trip, "rested": True}}, st.CAMP_ENERGY)
            texts.insert(0, f"You and your party rest by the fire for a while. +{st.CAMP_ENERGY} {{energy}}.")
        return _event(save, kind="camp", text=" ".join(texts))
    if action == "ask":
        g = place(save)["giver"]
        save = {**save, "quests": {**save["quests"], g.id: "asked"}}
        if not save["menders"].get(g.shortcut):
            save = {**save, "menders": {**save["menders"], g.shortcut: g.id}}
        return _event(save, kind="found", text=f"{_npc(g).name} is counting on you. It's in your journal.")
    if action == "mend":
        g = place(save)["giver"]
        items = {**save["items"], **{x: 0 for x in (_npc(g).lost, *_parts(save, g.shortcut, g.region))}}
        edge = world_of(save).quests[g.shortcut].shortcut
        save = {**save, "items": items, "quests": {**save["quests"], g.id: "done"},
                "cleared": [*save["cleared"], _edge_id(edge)]}
        save = _event(save, kind="found", text=st.SHORTCUTS[g.shortcut].done)
        return _xp(save, st.XP_QUEST)
    if action == "train":
        g = place(save)["giver"]
        pet = next(m for m in save["team"] if m["id"] == arg)
        save = {**save, "items": {**save["items"], _npc(g).lost: 0}, "quests": {**save["quests"], g.id: "done"}}
        trained = _npc(g).trained.format(npc=_npc(g).name, pet=pet["name"])
        return _event(save, kind="train", pet=arg, text=f"{trained} {pet['name']} grew a whole level!")
    if action == "rumor":
        key = _plan(save).keys[region]
        save = {**save, "rumors": [*save["rumors"], region]}
        how = st.KEY_HOW.get(key.kind, "")
        text = st.KEY_RUMOR.format(key=st.STORIES[region].key, place=_place_name(save, key.big), how=how)
        return _event(save, kind="found", text=f"\"{text}\" It's on your map.")
    if action == "ask_bridge":
        shortcut = _bridge_to_ask(save, region)
        g = next(g for g in _plan(save).givers.values() if g.shortcut == shortcut and g.region == region)
        return _event(save, kind="found", text=f"\"{_cap(_bridge_name(shortcut))}? Ask {_npc(g).name}, just over there. They know all about it.\"")
    if action == "fetch":
        if str(arg).startswith("key:"):
            region = arg.split(":")[1]
            key = st.STORIES[region].key
            return _event(_give(save, key), kind="found", text=f"You found the {key}! It must open the {st.TYPE_NAMES[region]} Temple.")
        g = _plan(save).givers[arg]
        save = _xp(_give(save, _npc(g).lost), st.XP_HARD_NOOK)
        return _event(save, kind="found", text=f"You found the {_npc(g).lost}! {_npc(g).name} will be so happy.")
    if action == "board":
        item = st.FORAGE[region]
        if pid in trip["side"]:
            save = {**save, "items": {**save["items"], item: save["items"][item] - st.SIDE_QUEST_COUNT},
                    "trip": {**trip, "side": {k: v for k, v in trip["side"].items() if k != pid}}}
            return _event(save, kind="coins", amount=st.SIDE_QUEST_COINS, text=f"Thanks! {st.SIDE_QUEST_COINS} coins.")
        return {**save, "trip": {**trip, "side": {**trip["side"], pid: item}}}
    if action == "inn":
        save = _restore({**save, "trip": {**trip, "used": [*trip["used"], pid]}}, st.INN_ENERGY)
        return _event(save, kind="found", text="Yum! You feel ready to go.")
    if action == "shrine":
        gain = round(st.SHRINE_ENERGY * max(0.0, min(1.0, accuracy)))
        save = _restore({**save, "trip": {**trip, "used": [*trip["used"], pid]}}, gain)
        return _event(save, kind="found", text=f"The shrine glows. +{gain} {{energy}}.")
    if action == "boss":
        return _start_battle(save, cr.temple_boss(save["seed"], region, tuple(save["at"]), relics_out(save)))
    if action == "temple":
        tale = st.STORIES[region]
        save = {**save, "temples": [*save["temples"], region],
                "buffs": {**save["buffs"], region: tale.buff}}
        save = _xp(_give(save, tale.relic), st.XP_TEMPLE)
        return _event(save, kind="relic", text=f"You found the {tale.relic}! Your {st.TYPE_NAMES[region]} pet becomes {tale.buff}. But the land stirs: every creature and gate grows {cr.RELIC_LEVELS} levels harder.")
    if action == "heartstone":
        return _event({**save, "finished": True}, kind="credits")
    if action == "credits":
        return _event(save, kind="credits")
    raise WanderError("There's nothing to do here.")


# --- writing ------------------------------------------------------------------------


def current(conn, learner_id: int) -> dict:
    """Your save as it stands (between trips, with the team as your pets are now)."""
    save = load(conn, learner_id)
    return save if save["trip"] else {**save, "team": _team(conn, learner_id, save["party"])}


def roster(conn, learner_id: int) -> list[tuple[dict, wp.Record]]:
    """Your pets that can go adventuring (no fish), starred first, with their records."""
    records = db.get_wander_pets(conn, learner_id)
    pets = [(p, wp.record_from(records.get(p["id"]))) for p in db.list_v3_pets(conn, learner_id) if wp.can_go(p["species"])]
    return sorted(pets, key=lambda pr: (not pr[1].starred, pr[0]["id"]))


def _team(conn, learner_id: int, party: list[int] | None) -> list[dict]:
    pets = roster(conn, learner_id)
    by_id = {p["id"]: (p, rec) for p, rec in pets}
    ids = [i for i in party if i in by_id] if party is not None else [p["id"] for p, _ in pets[:PARTY_SIZE]]
    return wp.team([wp.member(*by_id[i]) for i in ids])


def _write(conn, learner_id: int, change) -> dict:
    save = load(conn, learner_id)
    if not save["trip"]:  # between trips the team follows the pets
        save = {**save, "team": _team(conn, learner_id, save["party"])}
    save = change(save)
    for e in save["events"]:
        if e["kind"] == "coins":
            db.add_coins(conn, learner_id, e["amount"], "game", ref="wanderpaw")
    for e in save["events"]:  # first: this battle counts toward the types a new level offers
        if e["kind"] == "fought":
            rec = wp.note_battle(wp.record_from(db.get_wander_pets(conn, learner_id).get(e["pet"])), e["partners"])
            db.save_wander_pet(conn, learner_id, e["pet"], wp.record_json(rec))
    gained = sum(e["amount"] for e in save["events"] if e["kind"] == "xp" and "pets" not in e)
    if gained:
        save = _level_up(conn, learner_id, save, gained)
    for e in save["events"]:
        if e["kind"] == "xp" and "pets" in e:  # a battle's: just the fighters
            for pid in e["pets"]:
                save = _level_up(conn, learner_id, save, e["amount"], only=pid)
    for e in save["events"]:
        if e["kind"] == "bonus":  # a Type Tome or a Training Weight
            pet, rec = _record(conn, learner_id, e["pet"])
            rec = wp.with_bonus(rec, e["bonus"], e["name"])
            db.save_wander_pet(conn, learner_id, e["pet"], wp.record_json(rec))
            save = _refresh_member(save, pet, rec)
    for e in save["events"]:
        if e["kind"] == "train":  # exactly up to the next level
            rec = wp.record_from(db.get_wander_pets(conn, learner_id).get(e["pet"]))
            save = _level_up(conn, learner_id, save, max(0, wp.xp_for(wp.level(rec.xp) + 1) - rec.xp), only=e["pet"])
    save = _logged(save)
    db.save_wander(conn, learner_id, save)
    return save


LOG_SIZE = 10


def _logged(save: dict) -> dict:
    """The last LOG_SIZE things that happened (what the pop-ups said)."""
    texts = [e["text"] for e in save["events"] if e.get("text")]
    return {**save, "log": (save["log"] + texts)[-LOG_SIZE:]} if texts else save


def _level_up(conn, learner_id: int, save: dict, amount: int, only: int | None = None) -> dict:
    """XP to the team's real pets (or `only` one); their new levels join
    the team (energy stays as it is for the trip)."""
    records = db.get_wander_pets(conn, learner_id)
    pets = {p["id"]: p for p in db.list_v3_pets(conn, learner_id)}
    team = []
    for m in save["team"]:
        if m["id"] not in pets or (only is not None and m["id"] != only):
            team.append(m)
            continue
        old = wp.record_from(records.get(m["id"]))
        rec = wp.gain_xp(old, amount)
        db.save_wander_pet(conn, learner_id, m["id"], wp.record_json(rec))
        new = wp.member(pets[m["id"]], rec)
        team.append({**new, "energy": m["energy"]})
        save = _celebrate(save, pets[m["id"]], old, rec)
        if new["level"] > m["level"]:
            save = _event(save, kind="level", text=f"{m['name']} reached level {new['level']}!")
    return {**save, "team": team}


def _celebrate(save: dict, pet: dict, old: wp.Record, rec: wp.Record) -> dict:
    """A pop-up to come for each level gained, shown one at a time after any battle."""
    gained = [_level_entry(pet, rec, lv) for lv in range(wp.level(old.xp) + 1, wp.level(rec.xp) + 1)]
    return {**save, "levelups": [*save["levelups"], *gained]} if gained else save


def _level_entry(pet: dict, rec: wp.Record, lv: int) -> dict:
    """One level's pop-up: what grew, its six moves, and any choice it brings."""
    species, battle = pet["species"], pet["genes"]["battle"]
    stats = lambda n: wp.stats(species, battle, wp.Record(xp=wp.xp_for(n)))  # noqa: E731
    at = wp.at_level(rec, lv)
    member = wp.member(pet, at)
    return {"pet": pet["id"], "name": pet["name"], "species": species, "level": lv, "max": lv == wp.MAX_LEVEL,
            "types": member["types"], "was": stats(lv - 1), "now": stats(lv), "moves": bt.described_moves(member),
            "choose": _level_choice(pet, at, member, lv), "genes": member["genes"], "growth": member["growth"]}


def _level_choice(pet: dict, rec: wp.Record, member: dict, lv: int) -> dict | None:
    """What a pet gets to choose on reaching level lv (None: nothing). Odd
    levels are the ones with choices: a focus, then a second type and what
    its new attack replaces (mythicals are born with the type: just that)."""
    name = pet["name"]
    if lv == wp.FOCUS_LEVEL and not rec.focus:
        return {"kind": "focus", "ask": f"What will {name} focus on?", "options": [bt.focus_option(member, f) for f in bt.FOCUSES]}
    if lv == wp.MIX_LEVEL and len(member["types"]) > 1 and "mix" not in rec.swaps.values():
        return _mix_choice(name, member)
    if lv == wp.UPGRADE_LEVEL:
        return _upgrade_choice(name, rec, member)
    if lv == wp.SEVENTH_SLOT_LEVEL:
        return _seventh_slot_choice(name, rec, member)
    if lv == wp.REVERSE_MIX_LEVEL and len(member["types"]) > 1 and "mix2" not in [*rec.swaps.values(), *rec.extra]:
        return _reverse_mix_choice(name, member)
    if lv == wp.THIRD_TYPE_LEVEL:
        return _third_type_choice(name, pet, rec, member)
    if lv == wp.EIGHTH_SLOT_LEVEL:
        return _eighth_slot_choice(name, rec, member)
    if lv == wp.ANY_MIX_LEVEL:
        return _any_mix_choice(name, rec, member)
    if lv == wp.CAPSTONE_LEVEL and not rec.capstone:
        return _capstone_choice(name, member)
    if lv != wp.SECOND_TYPE_LEVEL:
        return None
    offered = wp.second_choices(pet["seed"], pet["species"], rec)
    if not offered:
        return _attack2_choice(name, member) if "attack2" not in rec.swaps.values() else None
    options = []
    for t in offered:
        beats = " and ".join(wd.tw(x) for x in bt.strong_against(t))
        options.append({"id": t, "type": t, "label": wd.tw(t), "title": "Second type", "note": f"Strong against {beats}.",
                        "moves": bt.described_moves({**member, "types": {**member["types"], t: 1}})})
    return {"kind": "second", "ask": f"{name} can learn a second type!", "options": options}


def _upgrade_choice(name: str, rec: wp.Record, member: dict) -> dict | None:
    """Which move a pet makes "+" (its focus has already grown), or, if it gave
    its focus up, taking that back instead, which then needs a new slot for
    what took its place."""
    own = bt.own_type(member)
    focus_move = bt.FOCUS_MOVES.get(rec.focus)
    if "refocus" in rec.upgrades:
        if "mix" in rec.swaps.values():
            return None
        choice = _mix_choice(name, member)
        where = [o for o in choice["options"] if o["id"] != focus_move]
        return {**choice, "ask": f"{bt.mix_move(member).name} needs a new slot. Which move gets replaced?", "options": where}
    if rec.upgrades:
        return None
    focus_name = bt.FOCUS_NAMES[own][rec.focus] if rec.focus else None
    gave_up = focus_move is not None and focus_move in rec.swaps
    options = []
    for m in bt.described_moves(member):
        if m["id"] in bt.FOCUS_MOVES.values() or (m["id"] == "guard" and bt.focus_plus(member, "guardian")):
            continue
        preview = bt.described_moves({**member, "upgrades": [m["id"]]})
        card = next(p for p in preview if p["id"] == m["id"])
        options.append({**card, "title": "Upgrade", "moves": preview})
    if gave_up:
        back = {**member, "swaps": {k: v for k, v in rec.swaps.items() if k != focus_move}}
        options.append({"id": "refocus", "type": own, "label": f"{focus_name}+", "title": "Take back",
                        "note": f"Returns to its old slot, upgraded. {bt.mix_move(member).name} moves to a new one.", "moves": bt.described_moves(back)})
    ask = f"{name}'s {focus_name}+ grew stronger! Pick a move to upgrade." if rec.focus and not gave_up else f"{name} can upgrade a move!"
    return {"kind": "upgrade", "ask": ask, "options": options}


def _seventh_slot_choice(name: str, rec: wp.Record, member: dict) -> dict | None:
    """Level 11: a 7th slot, for a move it gave up to come back to, then one more upgrade."""
    back = bt.given_up(member)
    if not rec.extra and back:
        options = []
        for move in back:
            preview = bt.described_moves({**member, "extra": [move]})
            options.append({**preview[-1], "title": "Bring back", "moves": preview})
        return {"kind": "slot", "ask": f"{name} opens a 7th slot! Which move comes back?", "options": options}
    if len(rec.upgrades) >= 2:
        return None
    options = []
    for m in bt.can_upgrade(member):
        preview = bt.described_moves({**member, "upgrades": [*rec.upgrades, m["id"]]})
        options.append({**next(p for p in preview if p["id"] == m["id"]), "title": "Upgrade", "moves": preview})
    return {"kind": "upgrade", "ask": f"{name} can upgrade a move!", "options": options} if options else None


def _reverse_mix_choice(name: str, member: dict) -> dict:
    """Level 13: its pair's mix the other way around, in any slot."""
    a, b = list(member["types"])[:2]
    move = bt.mix_move(member, "mix2")
    options = []
    for m in bt.described_moves(member):
        options.append({**m, "title": "Replace", "moves": bt.described_moves(_with_move(member, m["id"], "mix2"))})
    new = {**bt.mix_card(member, None, "mix2"), "note": move.says, "icons": bt.move_icons(member, "mix2")}
    return {"kind": "mix2", "ask": f"{name} learns {move.name}, a mix of {wd.tw(b)} and {wd.tw(a)}! Which move gets replaced?",
            "new": new, "options": options}


def _third_type_choice(name: str, pet: dict, rec: wp.Record, member: dict) -> dict | None:
    """Level 15: a third type, then its upgraded attack, in any slot."""
    offered = wp.third_choices(pet["seed"], pet["species"], rec)
    if offered:
        options = []
        for t in offered:
            beats = " and ".join(wd.tw(x) for x in bt.strong_against(t))
            options.append({"id": t, "type": t, "label": wd.tw(t), "title": "Third type", "note": f"Strong against {beats}.",
                            "moves": bt.described_moves({**member, "types": {**member["types"], t: 1}})})
        return {"kind": "third", "ask": f"{name} can learn a third type!", "options": options}
    if not rec.third or "attack3" in [*rec.swaps.values(), *rec.extra]:
        return None
    plus = {**member, "upgrades": [*rec.upgrades, "attack3"]}
    options = []
    for m in bt.described_moves(member):
        options.append({**m, "title": "Replace", "moves": bt.described_moves(_with_move(plus, m["id"], "attack3"))})
    return {"kind": "attack3", "ask": f"{name} learns a {wd.tw(rec.third)} attack+! Which move gets replaced?", "options": options}


def _eighth_slot_choice(name: str, rec: wp.Record, member: dict) -> dict | None:
    """Level 17: an 8th slot, holding a mix with its third type."""
    if not rec.third or len(rec.extra) >= 2:
        return None
    options = []
    for move in bt.mixes_missing(member, rec.third):
        preview = bt.described_moves({**member, "extra": [*rec.extra, move]})
        options.append({**preview[-1], "id": move, "title": "New mix", "moves": preview})
    return {"kind": "mix_slot", "ask": f"{name} opens an 8th slot! Which mix does it learn?", "options": options} if options else None


def _any_mix_choice(name: str, rec: wp.Record, member: dict) -> dict | None:
    """Level 19: any mix it doesn't have, then the slot it takes, then an upgrade."""
    if rec.pending:
        new = {**bt.mix_card(member, None, rec.pending), "note": bt.mix_move(member, rec.pending).says, "icons": bt.move_icons(member, rec.pending)}
        options = []
        current = {**member, "pending": None}
        for m in bt.described_moves(current):
            options.append({**m, "title": "Replace", "moves": bt.described_moves(_with_move(current, m["id"], rec.pending))})
        return {"kind": "place", "ask": f"{bt.mix_move(member, rec.pending).name} needs a slot. Which move gets replaced?", "new": new, "options": options}
    if "mix19" not in rec.done:
        options = []
        for move in bt.mixes_missing(member):
            card = {**bt.mix_card({**member, "pending": move}, None, move), "note": bt.mix_move(member, move).says}
            options.append({**card, "icons": bt.move_icons(member, move), "title": "New mix", "moves": bt.described_moves(member)})
        if options:
            return {"kind": "pick_mix", "ask": f"{name} can learn any mix of its types!", "options": options}
    if "plus19" not in rec.done:
        options = []
        for m in bt.can_upgrade(member):
            preview = bt.described_moves({**member, "upgrades": [*rec.upgrades, m["id"]]})
            options.append({**next(p for p in preview if p["id"] == m["id"]), "title": "Upgrade", "moves": preview})
        if options:
            return {"kind": "plus19", "ask": f"{name} can upgrade a move!", "options": options}
    return None


def _capstone_choice(name: str, member: dict) -> dict | None:
    """Level 21: a passive for a pair of its types, helping when it isn't fighting."""
    options = []
    for pair in bt.capstone_pairs(member):
        cap = bt.CAPSTONES[pair]
        options.append({"id": f"{pair[0]}:{pair[1]}", "type": pair[0], "type2": pair[1], "label": cap.name, "note": cap.says,
                        "title": "Capstone", "moves": bt.described_moves(member)})
    return {"kind": "capstone", "ask": f"{name} is fully grown! What will it do for the party when it isn't fighting?", "options": options} if options else None


def _with_move(member: dict, gives_up: str, gets: str) -> dict:
    """A team member with a new move in a slot, as wp.learn_move would have it."""
    extra = member.get("extra") or []
    if gives_up in extra:
        return {**member, "extra": [gets if m == gives_up else m for m in extra]}
    return {**member, "swaps": {**(member.get("swaps") or {}), gives_up: gets}}


def _swap_options(member: dict, gives_up: list[dict], gets: str) -> list[dict]:
    """A new move's choices of slot, each showing the six moves it would make."""
    swaps = member.get("swaps") or {}
    return [{**m, "title": "Replace", "moves": bt.described_moves({**member, "swaps": {**swaps, m["id"]: gets}})} for m in gives_up]


def _attack2_choice(name: str, member: dict) -> dict:
    """Which grey move a pet's new second-type attack takes the place of."""
    second = list(member["types"])[1]
    return {"kind": "attack2", "ask": f"{name} learns a {wd.tw(second)} attack! Which move gets replaced?",
            "options": _swap_options(member, bt.grey_moves(member), "attack2")}


def _mix_choice(name: str, member: dict) -> dict:
    """Which of its six moves a pet's new mix of its two types takes the place of."""
    a, b = list(member["types"])[:2]
    move = bt.mix_move(member)
    new = {**bt.mix_card(member), "note": move.says}
    return {"kind": "mix", "ask": f"{name} learns {move.name}, a mix of {wd.tw(a)} and {wd.tw(b)}! Which move gets replaced?",
            "new": new, "options": _swap_options(member, bt.described_moves(member), "mix")}


def _redo_waiting(save: dict, pet: dict, rec: wp.Record) -> dict:
    """A pet changed: its pop-ups still to come show it as it is now."""
    return {**save, "levelups": [_level_entry(pet, rec, e["level"]) if e["pet"] == pet["id"] else e for e in save["levelups"]]}


def _refresh_member(save: dict, pet: dict, rec: wp.Record) -> dict:
    """A pet's new record joins the team (on a trip, its energy stays as it is)."""
    new = wp.member(pet, rec)
    return {**save, "team": [{**new, "energy": m["energy"] if save["trip"] else new["energy"]} if m["id"] == pet["id"] else m
                             for m in save["team"]]}


def finish_levelup(conn, learner_id: int, choice: str | None = None) -> dict:
    """Done with the first pop-up: if it offers a choice, this makes it."""
    save = load(conn, learner_id)
    if not save["levelups"]:
        raise WanderError("Nobody's leveling up right now.")
    first, *rest = save["levelups"]
    save = {**save, "events": [], "note": None}
    pet = next(((p, rec) for p, rec in roster(conn, learner_id) if p["id"] == first["pet"]), None)
    if first["choose"] and pet:
        if choice not in [o["id"] for o in first["choose"]["options"]]:
            raise WanderError("Pick one of the choices.")
        kind = first["choose"]["kind"]
        learn = {"focus": lambda r: wp.learn_focus(r, choice), "second": lambda r: wp.learn_second(r, choice, first["level"]),
                 "attack2": lambda r: wp.learn_swap(r, choice, "attack2"), "mix": lambda r: wp.learn_swap(r, choice, "mix"),
                 "slot": lambda r: wp.learn_slot(r, choice),
                 "third": lambda r: wp.learn_third(r, choice, first["level"]),
                 "capstone": lambda r: wp.learn_capstone(r, choice),
                 "attack3": lambda r: wp.learn_upgrade(wp.learn_move(r, choice, "attack3"), "attack3"),
                 "mix_slot": lambda r: wp.learn_slot(r, choice),
                 "pick_mix": lambda r: wp.pick_move(r, choice, "mix19"),
                 "place": lambda r: wp.place_pending(r, choice),
                 "plus19": lambda r: wp.note_done(wp.learn_upgrade(r, choice), "plus19"),
                 "mix2": lambda r: wp.learn_move(r, choice, "mix2"),
                 "upgrade": lambda r: wp.take_back(r, bt.FOCUS_MOVES[r.focus]) if choice == "refocus" else wp.learn_upgrade(r, choice)}[kind]
        rec = learn(pet[1])
        db.save_wander_pet(conn, learner_id, first["pet"], wp.record_json(rec))
        save = _redo_waiting(_refresh_member(save, pet[0], rec), pet[0], rec)  # one choice can bring the next
        first, *rest = save["levelups"]
    save = {**save, "levelups": [first, *rest] if first["choose"] and pet else rest}
    if not save["trip"]:  # between trips the team follows the pets
        save = {**save, "team": _team(conn, learner_id, save["party"])}
    db.save_wander(conn, learner_id, save)
    return save


def pets_view(conn, learner_id: int) -> list[dict]:
    """Your pets for the party picker."""
    out = []
    for p, rec in roster(conn, learner_id):
        m = wp.member(p, rec)
        out.append({**wp.stats(p["species"], p["genes"]["battle"], rec), **m, "genes": pet_genes.resolve(p["genes"]), "growth": p["growth"],
                    "xp": rec.xp, "next": wp.xp_for(wp.level(rec.xp) + 1), "plus4": wp.xp_for(wp.level(rec.xp) + 4), "starred": rec.starred,
                    "choices": wp.second_choices(p["seed"], p["species"], rec)})
    return out


def set_party(conn, learner_id: int, ids: list[int]) -> dict:
    """Pick who goes (between trips)."""
    mine = {p["id"] for p, _ in roster(conn, learner_id)}
    if len(ids) > PARTY_SIZE or len(set(ids)) != len(ids) or not set(ids) <= mine:
        raise WanderError("Pick up to five of your own pets.")

    def change(s: dict) -> dict:
        if s["trip"]:
            raise WanderError("Pick your party before you set off.")
        return {**s, "party": list(ids), "team": _team(conn, learner_id, ids), "events": []}
    return _write(conn, learner_id, change)


def _record(conn, learner_id: int, pet_id: int) -> tuple[dict, wp.Record]:
    for pet, rec in roster(conn, learner_id):
        if pet["id"] == pet_id:
            return pet, rec
    raise WanderError("That pet can't go adventuring.")


def pick_second(conn, learner_id: int, pet_id: int, kind: str) -> None:
    pet, rec = _record(conn, learner_id, pet_id)
    try:
        rec = wp.pick_second(pet["seed"], pet["species"], rec, kind)
    except ValueError as exc:
        raise WanderError(str(exc)) from exc
    db.save_wander_pet(conn, learner_id, pet_id, wp.record_json(rec))
    save = load(conn, learner_id)  # a pop-up still waiting has nothing left to ask
    db.save_wander(conn, learner_id, _redo_waiting(save, pet, rec))


def star(conn, learner_id: int, pet_id: int) -> None:
    pet, rec = _record(conn, learner_id, pet_id)
    db.save_wander_pet(conn, learner_id, pet_id, wp.record_json(wp.Record(**{**wp.record_json(rec), "starred": not rec.starred})))


def give_xp(conn, learner_id: int, pet_id: int, amount: int) -> None:
    """Lab: XP straight to one pet."""
    pet, rec = _record(conn, learner_id, pet_id)
    new = wp.gain_xp(rec, amount)
    db.save_wander_pet(conn, learner_id, pet_id, wp.record_json(new))
    save = _celebrate(load(conn, learner_id), pet, rec, new)
    db.save_wander(conn, learner_id, _refresh_member(save, pet, new))


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


def fight(conn, learner_id: int, picks: list[dict]) -> dict:
    return _write(conn, learner_id, lambda s: battle_turn(s, picks))


def leave_battle(conn, learner_id: int, run: bool) -> dict:
    return _write(conn, learner_id, flee if run else end_battle)


def set_fighters(conn, learner_id: int, slots: list[int]) -> dict:
    return _write(conn, learner_id, lambda s: pick_fighters(s, slots))


def go_in(conn, learner_id: int, action: str, accuracy: float = 1.0, arg=None) -> dict:
    return _write(conn, learner_id, lambda s: act(s, action, accuracy, arg))


# --- shops and items (shop.py) ---------------------------------------------------


def buy_item(conn, learner_id: int, name: str) -> dict:
    """Buy from the shop you're standing in. The coins come from your balance."""
    item = sh.ITEMS.get(name)
    def change(save: dict) -> dict:
        where = place(save)
        if not where or where["kind"] != "shop":
            raise WanderError("There's no shop here.")
        region = where["region"]
        shelf = next((x for x in sh.stock(region, save["bought"].get(region, {}), save["items"], bool(save["finished"])) if x["name"] == name), None)
        if item is None or shelf is None:
            raise WanderError("They don't sell that here.")
        if shelf["sold_out"]:
            raise WanderError(f"You already have a {name}." if item.keep else f"They're out of {name}s.")
        have = db.get_coin_balance(conn, learner_id)
        if have < item.price:
            raise WanderError(f"You need {item.price - have:,} more coins for the {name}.")
        db.add_coins(conn, learner_id, -item.price, "purchase", ref=f"wanderpaw:{name}")
        bought = {**save["bought"], region: {**save["bought"].get(region, {}), name: save["bought"].get(region, {}).get(name, 0) + 1}}
        return _event(_give({**save, "bought": bought, "events": []}, name), kind="bought", text=f"You bought a {name}.")
    return _write(conn, learner_id, change)


def item_uses(save: dict) -> dict:
    """What each thing in your bag can do right now: {when, ready, why, choices}."""
    out = {}
    for name, n in save["items"].items():
        item = sh.ITEMS.get(name)
        if not n or not item:
            continue
        out[name] = {"when": item.when, "keep": item.keep, "why": _cant_use(save, item)}
        if item.when == "pick":
            out[name]["choices"] = _pick_choices(save, item)
    return out


def _pick_choices(save: dict, item: sh.Item) -> list[dict]:
    real = [m for m in save["team"] if m["id"]]
    if item.name == sh.TOME:
        return [{"arg": f"{m['id']}:{t}", "label": f"{m['name']}: {{{t}}} {n} to {n + 1}"} for m in real for t, n in m["types"].items()]
    return [{"arg": f"{m['id']}:{s}", "label": f"{m['name']}: {s} {m[s]} to {m[s] + 1}"} for m in real for s in sh.STATS]


def _cant_use(save: dict, item: sh.Item) -> str | None:
    """Why you can't use it right now (None: you can)."""
    b = save.get("battle")
    if item.when == "auto":
        return "It works by itself."
    if not save["trip"]:
        return "Set off on a trip first."
    if b and b["over"]:
        return "The battle's over."
    if item.when == "battle" and not b:
        return "It's for the middle of a battle."
    if item.when in ("walk", "pick") and b:
        return "Not in the middle of a battle!"
    who = b["fighters"] if b else fighters(save)
    mana, pets = _mana(save), save["trip"]["pets"]
    if item.name in (sh.MANA_DROP, sh.FULL_MANA) and all(mana[i] >= save["team"][i]["mana"] for i in who):
        return "Their mana is full."
    if item.name == sh.FEATHER and not any(pets[i] <= 0 for i in who):
        return "Nobody's worn out."
    if item.name == sh.TONIC and save["trip"]["walk"] >= walk_max(save):
        return "You're not tired."
    if item.name == sh.MAP and not _map_region(save):
        return "You know where all the keys are."
    if item.when == "pick" and not _pick_choices(save, item):
        return "It needs one of your own pets in the party."
    return None


def _map_region(save: dict) -> str | None:
    """The next temple key you know nothing about."""
    for region in wd.REGIONS:
        if region not in save["rumors"] and region not in save["temples"] and not save["items"].get(st.STORIES[region].key):
            return region
    return None


def use_item(save: dict, name: str, arg: str | None = None) -> dict:
    item = sh.ITEMS.get(name)
    if item is None or not save["items"].get(name):
        raise WanderError("You don't have that.")
    why = _cant_use(save, item)
    if why:
        raise WanderError(why)
    save = {**save, "events": []}
    b = save.get("battle")
    who = b["fighters"] if b else fighters(save)
    trip = save["trip"]
    if name in (sh.MANA_DROP, sh.FULL_MANA):
        mana = _mana(save)
        for i in who:
            most = save["team"][i]["mana"]
            mana[i] = most if name == sh.FULL_MANA else min(most, mana[i] + sh.MANA_DROP_AMOUNT)
        save = {**save, "trip": {**trip, "mana": mana}}
        text = "A sip each, and their {mana} comes flooding back."
    elif name == sh.WARD:
        pets, base, start = list(trip["pets"]), dict(b.get("ward_base") or {}), dict(b["start_energy"])
        for i in who:
            extra = round(save["team"][i]["energy"] * sh.WARD_SHARE)
            base.setdefault(str(i), pets[i])
            pets[i] += extra
            start[str(i)] = start.get(str(i), 0) + extra
        save = {**save, "battle": {**b, "ward_base": base, "start_energy": start}, "trip": {**trip, "pets": pets, "energy": trip["walk"] + sum(pets)}}
        text = "A shimmering ward settles over your fighters."
    elif name == sh.FEATHER:
        pets = list(trip["pets"])
        i = next(i for i in who if pets[i] <= 0)
        pets[i] = max(1, round(save["team"][i]["energy"] * sh.FEATHER_SHARE))
        save = {**save, "trip": {**trip, "pets": pets, "energy": trip["walk"] + sum(pets)}}
        text = f"{save['team'][i]['name']} gets back up!"
    elif name == sh.TONIC:
        walk = walk_max(save)
        save = {**save, "trip": {**trip, "walk": walk, "energy": walk + sum(trip["pets"])}}
        text = "Refreshing! Your own {energy} is full."
    elif name == sh.CLOAK:
        save = {**save, "trip": {**trip, "cloak": trip.get("cloak", 0) + 1}}
        text = "You pull the cloak around you. The next plain creature won't notice you."
    elif name == sh.MAP:
        region = _map_region(save)
        key = _plan(save).keys[region]
        save = {**save, "rumors": [*save["rumors"], region]}
        text = f"The map marks where the {st.STORIES[region].key} is hidden: {world_of(save).hexes[key.big].name}. It's in your journal."
    elif name == sh.WAY_HOME:
        save = _see({**save, "at": list(CAMP), "spot": [0, 0]}, CAMP, (0, 0))
        text = "The charm hums, and you're home at Camp."
    else:  # a Type Tome or a Training Weight
        choice = next((c for c in _pick_choices(save, item) if c["arg"] == arg), None)
        if not choice:
            raise WanderError("Pick a pet to use it on.")
        pet, what = arg.split(":")
        save = _event(save, kind="bonus", pet=int(pet), bonus="type" if name == sh.TOME else "stat", name=what)
        text = f"{choice['label'].split(':')[0]} feels stronger!"
    if not item.keep:
        save = _give(save, name, -1)
    return _event(save, kind="found", text=text)


def use(conn, learner_id: int, name: str, arg: str | None = None) -> dict:
    return _write(conn, learner_id, lambda s: use_item(s, name, arg))


# --- befriending: mana brings them to Camp, a Friendship Token makes them a pet -------


def _befriend_offer(save: dict, b: dict) -> dict | None:
    """What befriending this creature takes (None: it isn't on offer)."""
    if b["over"] != "won" or b.get("tier") == "boss" or b.get("befriended"):
        return None
    cost = b["level"] + sh.BEFRIEND_EXTRA_MANA.get(b.get("tier") or "", 0)
    mana = _mana(save)
    full = len(save["camp_friends"]) >= sh.CAMP_SPOTS
    can_pay = all(mana[i] >= cost for i in b["fighters"])
    why = "Camp is full. Ask a friend to leave first." if full else None if can_pay else "Your fighters don't have enough mana."
    return {"cost": cost, "can": not why, "why": why}


def befriend(save: dict) -> dict:
    """Each fighter's mana, and the creature you just beat waits for you at Camp."""
    b = save.get("battle")
    offer = b and _befriend_offer(save, b)
    if not offer:
        raise WanderError("There's nobody to befriend right now.")
    if not offer["can"]:
        raise WanderError(offer["why"])
    species = b["species"].replace(" ", "_")
    genes = pet_genes.wild_rare(species, b["seed"], wp.TIER_COLORS[b["tier"]]) if b.get("tier") else pet_genes.roll(species, None, None, b["seed"])
    companion = species in pet_genes.COMPANIONS
    name = pet_genes.companion_name(species, b["seed"]) if companion else pet_genes.species_name(species)
    friend = {"id": f"{b['seed']}:{save['stats']['trips']}:{len(save['camp_friends'])}", "species": species, "name": name, "level": b["level"], "genes": genes}
    mana = _mana(save)
    for i in b["fighters"]:
        mana[i] -= offer["cost"]
    save = {**save, "events": [], "battle": {**b, "befriended": True}, "trip": {**save["trip"], "mana": mana}, "camp_friends": [*save["camp_friends"], friend]}
    return _event(save, kind="found", text=f"The {b['species']} follows you home! It'll wait for you at Camp.")


def _at_camp_fire(save: dict) -> bool:
    return tuple(save["at"]) == CAMP and bool(save["trip"]) and (place(save) or {}).get("kind") == "campfire"


def camp_friends_view(save: dict) -> list[dict]:
    return [{"id": f["id"], "species": f["species"], "name": f["name"], "level": f["level"], "genes": pet_genes.resolve(f["genes"]),
             "types": list(t for t in wp.SPECIES_TYPES[f["species"]] if t)} for f in save["camp_friends"]]


def _camp_friend(save: dict, friend_id: str) -> dict:
    if not _at_camp_fire(save):
        raise WanderError("Your friends are waiting at the fire at Camp.")
    friend = next((f for f in save["camp_friends"] if f["id"] == friend_id), None)
    if not friend:
        raise WanderError("That friend isn't here.")
    return friend


def friend_leaves(save: dict, friend_id: str) -> dict:
    friend = _camp_friend(save, friend_id)
    save = {**save, "events": [], "camp_friends": [f for f in save["camp_friends"] if f["id"] != friend_id]}
    return _event(save, kind="found", text=f"{friend['name']} waves goodbye and wanders off.")


def welcome_friend(conn, learner_id: int, friend_id: str) -> dict:
    """A Friendship Token: a friend at Camp becomes one of your pets, at the level
    you found them, with all those levels' choices to make."""
    def change(save: dict) -> dict:
        friend = _camp_friend(save, friend_id)
        if not save["items"].get(sh.TOKEN):
            raise WanderError(f"You need a {sh.TOKEN} to give them. Shops in town have them.")
        pet_id = db.add_v3_pet(conn, learner_id, friend["genes"], friend["name"], "friend", growth=10)
        pet = db.get_v3_pet(conn, learner_id, pet_id)
        rec = wp.gain_xp(wp.Record(), wp.xp_for(friend["level"]))
        db.save_wander_pet(conn, learner_id, pet_id, wp.record_json(rec))
        save = _give({**save, "events": [], "camp_friends": [f for f in save["camp_friends"] if f["id"] != friend_id]}, sh.TOKEN, -1)
        save = _celebrate(save, pet, wp.Record(), rec)
        return _event(save, kind="found", text=f"{friend['name']} is one of your pets now! Add them to your party before your next trip.")
    return _write(conn, learner_id, change)


def befriend_at(conn, learner_id: int) -> dict:
    return _write(conn, learner_id, befriend)


def send_friend_off(conn, learner_id: int, friend_id: str) -> dict:
    return _write(conn, learner_id, lambda s: friend_leaves(s, friend_id))


# --- what the player sees ---------------------------------------------------------


def big_view(save: dict) -> dict:
    world = world_of(save)
    # Only places you've been (the rest of the world is just its shape).
    visited = {tuple(v) for v in save["visited"]}
    hexes = [{**wd.hex_json(world.hexes[h]), "visited": True} for h in sorted(visited)]
    edges = []
    for k, v in world.edges.items():
        if k[0] in visited or k[1] in visited:
            edge = wd.edge_json(k, v, world.gates.get(k))
            if "gate" in edge:
                edge["gate"]["cleared"] = cleared(save, k)
                edge["gate"]["level"] = gate_level(save, edge["gate"]["level"])
            edges.append(edge)
    # Where a quest-giver said to look, and where a rumor says a key is,
    # even before you've been there.
    plan = _plan(save)
    marks = [list(plan.givers[gid].lost.big) for gid, state in save["quests"].items()
             if state == "asked" and not _lost_gone(save, plan.givers[gid])]
    marks += [list(plan.keys[r].big) for r in save["rumors"] if not save["items"].get(st.STORIES[r].key) and r not in save["temples"]]
    # ... and where a clue points.
    marks += [list(_unkey(c.split("|")[0])) for c in save["clues"].values() if c not in save["found"]]
    # The world's shape (just where land is), so the map can show what's left to find.
    shape = [list(h) for h in sorted(world.hexes)]
    return {"at": save["at"], "radius": wd.MAP_RADIUS, "hexes": hexes, "edges": edges, "marks": marks, "shape": shape}


def _tile(save: dict, local: lc.LocalMap, big: Hex, h: Hex) -> dict:
    out = lc.tile_json(local, h)
    if h in local.gates and cleared(save, local.gates[h]):
        out["kind"] = lc.CLEARED_TILES.get(out["kind"], "path")
    poi = out.get("poi")
    pid = _place_id(big, h)
    gone = (
        (poi == "forage" and save["trip"] and pid in save["trip"]["used"])
        or (poi == "chest" and pid in save["chests"])
    )
    if gone:
        del out["poi"]
    for g in _plan(save).givers.values():
        if (g.lost.big, g.lost.at) == (big, h) and not g.lost.check and not _lost_gone(save, g):
            out["poi"] = "lost"
    if pid in save["clues"].values() and pid not in save["found"]:
        out["poi"] = "cache"
    c = critter_at(save, big, h)
    if c:
        out["critter"] = {"species": c.species, "kind": c.kind, "second": c.second, "level": c.level, "guardian": c.guardian, "tier": c.tier, "mythical": c.species in wp.MYTHICAL}
    if out["kind"].startswith("pillar_") and out["kind"][7:] in save["temples"]:
        out["lit"] = True  # its relic is home
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
        "tiles": tiles, "steps": [[*g, step_word(save, g)] for g in steps(save)],
    }


def quests_view(save: dict) -> list[dict]:
    """The journal: quests taken, bridges found, keys heard of. Each has a
    title, what to do now, whether it's done, and big hexes to light up."""
    world, plan = world_of(save), _plan(save)
    out = []
    for gid, state in save["quests"].items():
        g = plan.givers[gid]
        npc, town = _npc(g), _place_name(save, g.town)
        if state == "done":
            text = "Done!"
        elif _mends(save, g):
            near, far = _parts(save, g.shortcut, g.region)
            need = [x.split(" for ")[0] for x in (npc.lost, near, far) if not save["items"].get(x)]
            text = (f"{npc.name} in {town} needs the {_and(need)}." if need else f"Bring it all to {npc.name} in {town}!")
            if not _has_lost(save, g):
                text += f" The {npc.lost} is in {_place_name(save, g.lost.big)}."
        else:
            text = (f"Bring the {npc.lost} to {npc.name} in {town}." if _has_lost(save, g)
                    else f"Find the {npc.lost} in {_place_name(save, g.lost.big)}.")
        title = f"Mend {_bridge_name(g.shortcut)}" if save["menders"].get(g.shortcut) == gid else f"{npc.name}'s {npc.lost}"
        hexes = [list(g.town)] + ([] if _lost_gone(save, g) else [list(g.lost.big)])
        out.append({"title": title, "text": text, "done": state == "done", "hexes": hexes})
    for shortcut in save["bridges"]:
        if save["menders"].get(shortcut):
            continue  # it's someone's quest now
        sides = qs.bridge_sides(world, shortcut)
        towns = [world.quests[world.hexes[b].region].town for b in sides]
        out.append({"title": f"Fix {_bridge_name(shortcut)}", "done": False,
                    "text": f"Someone in {' or '.join(_place_name(save, t) for t in towns)} might know how.",
                    "hexes": [list(t) for t in towns] + [list(b) for b in sides]})
    for region in save["rumors"]:
        key, name = plan.keys[region], st.STORIES[region].key
        got = bool(save["items"].get(name)) or region in save["temples"]
        out.append({"title": f"The {name}", "done": got,
                    "text": "Found!" if got else f"Hidden in {_place_name(save, key.big)}. {st.KEY_HOW.get(key.kind, '')}",
                    "hexes": [] if got else [list(key.big)]})
    return out


def clues_view(save: dict) -> list[dict]:
    """Clues you've read: where they point, and whether you've dug it up."""
    hexes = world_of(save).hexes
    out = []
    for at, to in save["clues"].items():
        big, far = _unkey(at.split("|")[0]), _unkey(to.split("|")[0])
        out.append({"from": hexes[big].name, "to": hexes[far].name, "hex": list(far), "found": to in save["found"]})
    return out


def team_view(save: dict) -> list[dict]:
    """The team for the party book: how far along each is, and its moves."""
    mana = _mana(save) if save["trip"] else [m["mana"] for m in save["team"]]
    out = []
    for i, m in enumerate(save["team"]):
        cap = bt.capstone_of(m)
        card = {"id": "capstone", "type": m["capstone"].split(":")[0], "type2": m["capstone"].split(":")[1], "label": cap.name, "note": cap.says} if cap else None
        out.append({**m, "progress": wp.progress(m["xp"]), "moves": bt.described_moves(m, mana[i]), "capstone_card": card})
    return out


def view(save: dict) -> dict:
    return {
        "big": big_view(save),
        "local": local_view(save),
        "trip": save["trip"],
        "note": save["note"],
        "events": save["events"],
        "screen": screen(save),
        "campfires": len(campfires_rested(save)),
        "at_camp": tuple(save["at"]) == CAMP,
        "team": team_view(save),
        "fighters": fighters(save),
        "combo_book": combo_book(save),
        "battle": battle_view(save),
        "levels": {t: levels(save, t) for t in wd.REGIONS if levels(save, t)},
        "items": {k: v for k, v in sorted(save["items"].items()) if v},
        "about": {k: st.describe(k) for k, v in save["items"].items() if v},
        "item_uses": item_uses(save),
        "clues": clues_view(save),
        "log": save["log"],
        "levelups": save["levelups"],
        "quests": quests_view(save),
        "temples": save["temples"],
        "camp_friends": camp_friends_view(save),
        "camp_spots": sh.CAMP_SPOTS,
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


def to_temple(conn, learner_id: int, region: str) -> dict:
    """The lab's way to a boss: at this temple's door, on a trip, with its key."""
    save = load(conn, learner_id)
    if region not in st.STORIES:
        raise WanderError("There's no temple like that.")
    big = next((h for h, x in world_of(save).hexes.items() if x.special == "temple" and x.region == region), None)
    if big is None:
        raise WanderError("That temple isn't on the map.")
    local = local_of(save, big)
    door = next(spot for spot, tile in local.tiles.items() if tile == "temple")
    save = start_trip(save) if not save["trip"] else save
    save = {**save, "items": {**save["items"], st.STORIES[region].key: 1}, "at": list(big), "spot": list(door), "events": []}
    save = _see(save, big, door)
    db.save_wander(conn, learner_id, save)
    return save


def refill(conn, learner_id: int) -> dict:
    """Full energy (starting a trip where you are if you're not on one)."""
    def change(s: dict) -> dict:
        s = s if s["trip"] else start_trip(s)
        return {**s, "trip": {**_trip(s["team"]), "used": s["trip"]["used"], "side": s["trip"]["side"]}}
    return _write(conn, learner_id, change)


def reset(conn, learner_id: int, seed: int | None = None) -> dict:
    """A new world: pets start over at level 1 (they stay starred)."""
    for pet_id, data in db.get_wander_pets(conn, learner_id).items():
        db.save_wander_pet(conn, learner_id, pet_id, wp.record_json(wp.Record(starred=wp.record_from(data).starred)))
    save = new_save(seed if seed is not None else random.randrange(2**31))
    db.save_wander(conn, learner_id, save)
    return save
