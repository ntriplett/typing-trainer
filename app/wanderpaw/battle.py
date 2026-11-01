"""Wanderpaw battles (PLAN.md 11n, phase 5): two of your pets against a
wild creature, one typed move each per round.

The type ring: a move is very strong (x2) against the next type around
the ring (REGIONS order: Splash -> Ember -> Dream -> Leaf -> Shock ->),
strong (x1.5) against the one after, weak (x2/3) and very weak (x1/2)
against the other two. A pet defends with its first type, and so does a
creature; one with a second type hits with whichever does best.

Each round every fighter with energy picks one of six moves (moves()),
typing its word; each slip takes SLIP off its strength, down to FLOOR:
- attack: damage, with whichever of its types does best here;
- big: a three-word move that costs BIG_MANA: BIG times the damage, and
  it leaves its type's mark on the creature. Big moves go first;
- guard: take the hits meant for its partner this round, at GUARD;
- focus: its next move is FOCUS times as strong;
- cheer: its partner's move this round is CHEER times as strong;
- rest: get back REST_ENERGY of its energy and REST_MANA mana.
Then the rest act fastest first; the creature hits one fighter.

At FOCUS level a pet's focus takes over one of its grey moves, themed by
its first type (FOCUS_NAMES). Some are passive: they fill the slot and just
work, with nothing to type.
- healer (for guard): each round its partner gets energy and mana back;
- elementalist (for cheer): a typed move, MARK_MANA, goes first of all, no
  damage, leaves its type's mark for a hit to set off;
- daredevil (for rest): its type's attack and big do DAREDEVIL times the
  damage, each costing DAREDEVIL_COST of its energy (never its last);
- guardian (for focus): for GUARDIAN_ROUNDS its partner can't be hurt by the
  two types it's strong against; its guard turns its color, and takes hits
  from the type that beats it at GUARD_STRONG.

Marks (MARKS: soaked, glowing, drowsy, static, tangled) last this round
and the next (MARK_ROUNDS). On their own: glowing burns, drowsy may doze
off, tangled acts last and hits softer. A hit on a marked creature can
set off a combo (COMBOS, by mark and the hit's type: 20 of the 25, one
gap in each row and column), which uses up the mark: more damage, lost
turns, weaker hits, burning, or a boost for your pets. Some leave lasting
effects (`effects`: drenched, thorns, confused, burn, popped, doze).

Energy, not HP: battles take it out of each fighter's own trip energy
(mana too, refilled each day). Pacing: a fair fight takes about ROUNDS
rounds and costs each fighter about FAIR_COST of its energy, so creatures
don't share pets' stats: a creature's energy is what two even fighters
take off it in ROUNDS rounds, and its hits are sized to a share of the
target's full energy.

A battle is a plain dict (the save keeps it while it's on):
{critter, species, kind, second, level, seed, energy, max, speed, fighters: [team
places], marks: {mark: rounds}, effects: {effect: rounds}, focus: [places],
skip: turns the creature loses, round, log: [steps], healed: {"place:energy"
or "place:mana": given so far}, over: None | "won" | "lost"}.
A step (for playing the round back): {text, who (a team place or "foe"),
act (hit, rest, guard, focus, cheer, mark, heal, blocked, skip, doze, burn),
target, type, damage, gain, big, combo (its name, if one went off), flash
([place, move id]: a passive move to light up), and everyone's
energy and mana after it: foe, pets {place: energy}, mana {place: mana}}.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.wanderpaw import world as wd

SLIP = 0.1
FLOOR = 0.4
ROUNDS = 3
FAIR_COST = 0.1  # of a fighter's energy, over a fair fight
XP_EVEN = 100  # for a fair fight
XP_RANGE = (25, 250)
TYPICAL_ACCURACY = 0.85  # what a creature's energy is sized for

BIG = 2.2
BIG_MANA = 6
GUARD = 0.5
FOCUS = 1.5
CHEER = 1.5
REST_ENERGY = 0.1  # of its full energy
REST_MANA = 3
MARK_ROUNDS = 2  # this round and the next
DOZE = 0.5  # chance a drowsy creature dozes off
TANGLED_HITS = 0.75
BURN = 0.3  # of an even hit, each round it's glowing (doubled when it's burning)
POP = 1.5  # the hit that pops a bubble (or wakes it from a hammock)
COMBO_XP = 20  # for each fighter, the first time you find a combo
MARKS = {"splash": "soaked", "ember": "glowing", "dream": "drowsy", "shock": "static", "leaf": "tangled"}

FOCUSES = ("healer", "elementalist", "daredevil", "guardian")
FOCUS_TITLES = {"healer": "Healer", "elementalist": "Elementalist", "daredevil": "Daredevil", "guardian": "Guardian"}
FOCUS_REPLACES = {"healer": "guard", "elementalist": "cheer", "daredevil": "rest", "guardian": "focus"}
FOCUS_MOVES = {"healer": "healer", "elementalist": "mark", "daredevil": "daredevil", "guardian": "guardian"}  # its move's id
FOCUS_NAMES = {
    "splash": {"healer": "Healing Spring", "elementalist": "Sprinkle", "daredevil": "Tidal Surge", "guardian": "Bubble Shield"},
    "ember": {"healer": "Cozy Hearth", "elementalist": "Kindle", "daredevil": "Roaring Flames", "guardian": "Flame Wall"},
    "dream": {"healer": "Sweet Lullaby", "elementalist": "Big Yawn", "daredevil": "Wild Imagination", "guardian": "Dream Veil"},
    "leaf": {"healer": "Mending Moss", "elementalist": "Creeping Vine", "daredevil": "Overgrowth", "guardian": "Bramble Wall"},
    "shock": {"healer": "Jump Start", "elementalist": "Static Cling", "daredevil": "Overdrive", "guardian": "Lightning Fence"},
}
GUARD_NAMES = {"splash": "Bubble Guard", "ember": "Flame Guard", "dream": "Dream Guard", "leaf": "Bramble Guard", "shock": "Lightning Guard"}
HEAL_ENERGY = 1  # for the partner, each round ...
HEAL_MANA = 1
HEAL_MAX_ENERGY = 5  # ... up to this in a battle
HEAL_MAX_MANA = 3
MARK_MANA = 1
DAREDEVIL = 2.0
DAREDEVIL_COST = 0.04  # of its full energy
GUARDIAN_ROUNDS = 2
GUARD_STRONG = 0.25


@dataclass(frozen=True, slots=True)
class Combo:
    name: str
    says: str  # what it does (the combo book)
    mult: float = 1.0  # on the hit that sets it off
    skip: int = 0  # turns the creature loses
    effects: tuple[tuple[str, int], ...] = ()  # (effect, rounds) left on the creature
    mark: str | None = None  # a new mark left on it
    keep: int = 0  # the mark stays this many more rounds (else it's used up)
    pets_energy: float = 0  # of each fighter's full energy, back
    pets_mana: int = 0


# (the mark on it, the type of the hit) -> what happens. Rows and columns
# in the order Splash, Ember, Dream, Shock, Leaf; the gaps run just under
# the diagonal (and Soaked/Leaf).
COMBOS = {
    ("soaked", "splash"): Combo("Drenched", "Soaked through: it hits for half, 3 rounds.", effects=(("drenched", 3),)),
    ("soaked", "ember"): Combo("Steam Cloud", "Fire on a wet one: steam! It misses its next attack.", skip=1),
    ("soaked", "dream"): Combo("Bubble Trap", "It floats off in a dream bubble: it loses a turn, and the hit that pops it is stronger.",
                               skip=1, effects=(("popped", 3),)),
    ("soaked", "shock"): Combo("Chain Zap", "Lightning on a wet one: double damage!", mult=2.0),
    ("glowing", "ember"): Combo("Blaze", "More fire on the fire: it burns twice as hard.", effects=(("burn", 2),)),
    ("glowing", "dream"): Combo("Fever Dream", "Hot and dizzy: its next attack hits itself.", effects=(("confused", 3),)),
    ("glowing", "shock"): Combo("Flare", "Lightning on the flames: it flares up for big damage.", mult=1.75),
    ("glowing", "leaf"): Combo("Wildfire", "The fire spreads: it burns twice as hard, for longer.", effects=(("burn", 3),)),
    ("drowsy", "splash"): Combo("Sleepy Rain", "Soft rain keeps it drowsy, and it dozes off for sure.", keep=2,
                                effects=(("doze", 2),)),
    ("drowsy", "dream"): Combo("Fast Asleep", "So sleepy: it falls fast asleep for two turns.", skip=2),
    ("drowsy", "shock"): Combo("Rude Awakening", "A jolt wakes it up: double damage!", mult=2.0),
    ("drowsy", "leaf"): Combo("Meadow Nap", "It naps in the grass, and your pets catch their breath.", skip=1,
                              pets_energy=0.1),
    ("static", "splash"): Combo("Thunderstorm", "Rain and static: double damage, and it's soaked.", mult=2.0, mark="soaked"),
    ("static", "ember"): Combo("Sparkler", "Sparks and fire: fireworks! Stronger, and it's glowing.", mult=1.5, mark="glowing"),
    ("static", "shock"): Combo("Overcharge", "Static and more lightning: huge damage!", mult=2.5),
    ("static", "leaf"): Combo("Lightning Rod", "The leaves ground the static: your pets get mana.", pets_mana=3),
    ("tangled", "splash"): Combo("Thorns", "The vines drink the water and grow thorns: it hurts itself when it attacks.",
                                 effects=(("thorns", 3),)),
    ("tangled", "ember"): Combo("Bonfire", "Fire on the vines: double damage!", mult=2.0),
    ("tangled", "dream"): Combo("Hammock", "The vines make a hammock: it naps, and the hit that wakes it is stronger.",
                                skip=1, effects=(("popped", 3),)),
    ("tangled", "leaf"): Combo("Rooted", "More vines: it's rooted to the spot and loses a turn.", skip=1),
}


def matchup(move: str, target: str) -> float:
    """How strong a move of type `move` is against a `target` type."""
    gap = (wd.REGIONS.index(target) - wd.REGIONS.index(move)) % len(wd.REGIONS)
    return {0: 1.0, 1: 2.0, 2: 1.5, 3: 2 / 3, 4: 0.5}[gap]


def accuracy(slips: int) -> float:
    return max(FLOOR, 1 - SLIP * slips)


def pet_hit(power: int) -> float:
    return 3 + 0.6 * power


def _even_power(level: int) -> int:
    return 5 + level  # a middling pet's power at that level


def start(critter, fighters: list[int]) -> dict:
    """A battle against `critter` (critters.Critter) with these team places."""
    energy = round(2 * ROUNDS * pet_hit(_even_power(critter.level)) * TYPICAL_ACCURACY)
    return {
        "critter": critter.id, "species": critter.species, "kind": critter.kind, "second": critter.second, "level": critter.level,
        "seed": critter.seed, "energy": energy, "max": energy, "speed": 5 + critter.level,
        "fighters": list(fighters), "marks": {}, "effects": {}, "focus": [], "skip": 0, "round": 0, "log": [],
        "over": None,
    }


def foe_type(b: dict, target: str, blocked: tuple[str, ...] = ()) -> str | None:
    """The creature's type that hits a `target` type hardest (None: `blocked` stops them all)."""
    kinds = [t for t in (b["kind"], b.get("second")) if t and t not in blocked]
    return max(kinds, key=lambda t: (matchup(t, target), -kinds.index(t))) if kinds else None


def own_type(member: dict) -> str:
    return next(iter(member["types"]))


def strong_against(kind: str) -> tuple[str, str]:
    i = wd.REGIONS.index(kind)
    return wd.REGIONS[(i + 1) % len(wd.REGIONS)], wd.REGIONS[(i + 2) % len(wd.REGIONS)]


def beaten_by(kind: str) -> str:
    return wd.REGIONS[wd.REGIONS.index(kind) - 1]


def no_combo_with(kind: str) -> str:
    """The partner type whose hits set off nothing on this type's mark."""
    return next(t for t in wd.REGIONS if (MARKS[kind], t) not in COMBOS)


def _doubles(member: dict, kind: str) -> bool:
    return member.get("focus") == "daredevil" and kind == own_type(member)


def best_type(member: dict, foe: str | None) -> str:
    types = list(member["types"])
    return max(types, key=lambda t: (matchup(t, foe) * (DAREDEVIL if _doubles(member, t) else 1) if foe else 0, -types.index(t)))


def described_moves(member: dict, mana: int | None = None) -> list[dict]:
    """A fighter's six moves away from any battle, saying just what each does."""
    hit, types, own = pet_hit(member["power"]), list(member["types"]), own_type(member)
    names = " or ".join(wd.tw(t) for t in types)
    marks = " or ".join(MARKS[t].title() for t in types)
    rest = max(1, round(member["energy"] * REST_ENERGY))
    a, b = (wd.tw(t) for t in strong_against(own))
    beats_it = wd.tw(beaten_by(own))
    double = member.get("focus") == "daredevil"
    twice = f" Double that in {wd.tw(own)}, for {_daredevil_cost(member)} energy." if double else ""
    guard = f"Takes the hits meant for its partner this round, at {GUARD:.0%}."
    says = {
        "attack": (f"{names} attack", f"Hits for about {round(hit)}.{twice}"),
        "big": (f"Big {names}", f"Goes first and hits for about {round(hit * BIG)}. Leaves it {marks}. Costs {BIG_MANA} mana.{twice}"),
        "guard": ("Guard", guard),
        "focus": ("Focus", f"Its next move is {FOCUS}x as strong."),
        "cheer": ("Cheer", f"Its partner's move this round is {CHEER}x as strong."),
        "rest": ("Rest", f"Gets back {rest} energy and {REST_MANA} mana."),
        "healer": (None, f"Each round its partner gets back {HEAL_ENERGY} energy (up to {HEAL_MAX_ENERGY} a battle) and {HEAL_MANA} mana (up to {HEAL_MAX_MANA})."),
        "mark": (None, f"Goes first and leaves it {MARKS[own].title()}, so the next hit can set off a combo. No damage. Costs {MARK_MANA} mana. No combo with {wd.tw(no_combo_with(own))} hits."),
        "daredevil": (None, f"Its {wd.tw(own)} moves do double damage, but each costs {_daredevil_cost(member)} energy."),
        "guardian": (None, f"For the first {GUARDIAN_ROUNDS} rounds of a battle, {a} and {b} can't hurt its partner."),
    }
    if member.get("focus") == "guardian":
        says["guard"] = (GUARD_NAMES[own], f"{guard} Only {GUARD_STRONG:.0%} from {beats_it}, the type that beats it.")
    return [{**m, "label": says[m["id"]][0] or m["label"], "note": says[m["id"]][1]} for m in moves(member, None, mana)]


def _daredevil_cost(member: dict) -> int:
    return max(1, round(member["energy"] * DAREDEVIL_COST))


def focus_option(member: dict, focus: str, mana: int | None = None) -> dict:
    """A focus as a choice: its card, what it replaces, and the six moves it would make."""
    preview = described_moves({**member, "focus": focus}, mana)
    card = next(m for m in preview if m["id"] == FOCUS_MOVES[focus])
    replaces = FOCUS_REPLACES[focus].title()
    return {**card, "id": focus, "title": f"{FOCUS_TITLES[focus]} focus", "replaces": replaces,
            "also": "Its Guard turns its color too." if focus == "guardian" else None, "moves": preview}


def _strength(m: float) -> str:
    return {2.0: " Super strong!", 1.5: " Strong.", 1.0: "", 2 / 3: " Weak.", 0.5: " Very weak."}[m]


def moves(member: dict, foe: str | None = None, mana: int | None = None) -> list[dict]:
    """A fighter's six moves, each with a short reminder of what it does
    (how strong against a `foe` type, if known) and whether it can (mana)."""
    t = best_type(member, foe)
    strength = _strength(matchup(t, foe)).strip() if foe else ""
    out = [
        {"id": "attack", "type": t, "label": f"{wd.tw(t)} attack", "size": "medium",
         "note": strength or "Hit it."},
        {"id": "big", "type": t, "label": f"Big {wd.tw(t)}", "size": "phrase", "cost": BIG_MANA,
         "note": f"First! {MARKS[t].title()}. {BIG_MANA} mana", "can": mana is None or mana >= BIG_MANA},
        {"id": "guard", "type": None, "label": "Guard", "size": "short", "note": "Protect your partner."},
        {"id": "focus", "type": None, "label": "Focus", "size": "short", "note": "Next move is stronger."},
        {"id": "cheer", "type": None, "label": "Cheer", "size": "short", "note": "Help your partner."},
        {"id": "rest", "type": None, "label": "Rest", "size": "short", "note": "Energy and mana back."},
    ]
    return _with_focus(out, member, mana)


def _with_focus(out: list[dict], member: dict, mana: int | None) -> list[dict]:
    """The six moves with its focus in: passive ones have no word to type."""
    focus = member.get("focus")
    if not focus:
        return out
    own = own_type(member)
    a, b = (wd.tw(t) for t in strong_against(own))
    card = {
        "healer": {"passive": True, "note": "Partner heals each round."},
        "elementalist": {"size": "short", "cost": MARK_MANA, "note": f"First! {MARKS[own].title()}. {MARK_MANA} mana",
                         "can": mana is None or mana >= MARK_MANA},
        "daredevil": {"passive": True, "note": f"{wd.tw(own)} x2, costs energy."},
        "guardian": {"passive": True, "note": f"Stops {a} and {b}."},
    }[focus]
    new = {"id": FOCUS_MOVES[focus], "type": own, "label": FOCUS_NAMES[own][focus], **card}
    out = [new if m["id"] == FOCUS_REPLACES[focus] else m for m in out]
    if focus == "guardian":
        out = [{**m, "type": own, "label": GUARD_NAMES[own], "note": f"Best against {wd.tw(beaten_by(own))}."} if m["id"] == "guard" else m for m in out]
    return out


def turn(battle: dict, team: list[dict], energy: list[int], picks: list[dict], rng: random.Random,
         mana: list[int] | None = None) -> tuple[dict, list[int], list[int]]:
    """One round. picks: [{move, slips}] for each fighter that still has
    energy, in order. Returns the battle, the team's energy and mana."""
    if battle["over"]:
        raise ValueError("The battle is over.")
    energy = list(energy)
    mana = list(mana) if mana is not None else [m["mana"] for m in team]
    able = [i for i in battle["fighters"] if energy[i] > 0]
    if len(picks) != len(able):
        raise ValueError("Pick a move for each fighter that can still fight.")
    b = {**battle, "round": battle["round"] + 1, "log": [], "marks": dict(battle.get("marks", {})),
         "effects": dict(battle.get("effects", {})), "skip": battle.get("skip", 0), "healed": dict(battle.get("healed", {}))}
    chosen = {}
    for i, pick in zip(able, picks):
        options = {m["id"]: m for m in moves(team[i], b["kind"], mana[i])}
        if pick["move"] not in options:
            raise ValueError("That's not one of its moves.")
        if options[pick["move"]].get("can") is False:
            raise ValueError("Not enough mana for that.")
        if options[pick["move"]].get("passive"):
            raise ValueError("That one just works: there's nothing to do.")
        chosen[i] = pick
    partner = {i: next((j for j in able if j != i), None) for i in able}
    boost = {i: FOCUS if i in battle.get("focus", []) else 1.0 for i in able}
    for i, pick in chosen.items():
        if pick["move"] == "cheer" and partner[i] is not None:
            boost[partner[i]] *= CHEER
    guards = {partner[i]: i for i, p in chosen.items() if p["move"] == "guard" and partner[i] is not None}
    focus_next = [i for i, p in chosen.items() if p["move"] == "focus"]
    log = []
    name = lambda i: team[i]["name"]  # noqa: E731
    foe = b["species"]

    def step(entry: dict) -> None:
        """A step of the round, with where everyone stands after it."""
        log.append({"target": None, "type": None, "damage": 0, "gain": 0, "big": False, "combo": None, "flash": None, **entry,
                    "foe": b["energy"], "pets": {i: energy[i] for i in b["fighters"]},
                    "mana": {i: mana[i] for i in b["fighters"]}})

    # who goes when: marks first, so a big move can use them; then big moves,
    # then fastest first (a tangled creature last)
    def speed(w):
        if w == "foe":
            return -1 if "tangled" in b["marks"] else b["speed"]
        return team[w]["speed"] + {"mark": 2000, "big": 1000}.get(chosen[w]["move"], 0)

    order = sorted([*able, "foe"], key=lambda w: -speed(w) + rng.random() * 0.1)
    for who in order:
        if b["energy"] <= 0 or not any(energy[i] > 0 for i in b["fighters"]):
            break
        if who == "foe":
            for entry in _foe_acts(b, team, energy, able, guards, rng):
                step(entry)
            continue
        if energy[who] <= 0:
            continue
        move = chosen[who]["move"]
        if move in ("attack", "big"):
            step(_hit(b, team, who, move, accuracy(chosen[who].get("slips", 0)) * boost[who], energy, mana))
        elif move == "mark":
            own = own_type(team[who])
            mana[who] -= MARK_MANA
            b["marks"][MARKS[own]] = MARK_ROUNDS
            step({"who": who, "act": "mark", "target": "foe", "type": own,
                  "text": f"{name(who)}'s {FOCUS_NAMES[own]['elementalist']}: the {foe} is {MARKS[own]}!"})
        elif move == "rest":
            gain = max(1, round(team[who]["energy"] * REST_ENERGY))
            energy[who] = min(team[who]["energy"], energy[who] + gain)
            mana[who] = min(team[who]["mana"], mana[who] + REST_MANA)
            step({"who": who, "act": "rest", "target": who, "gain": gain, "text": f"{name(who)} rests: +{gain} energy, +{REST_MANA} mana."})
        elif move == "guard":
            step({"who": who, "act": "guard", "text": f"{name(who)} stands guard."})
        elif move == "focus":
            step({"who": who, "act": "focus", "text": f"{name(who)} focuses..."})
        elif move == "cheer":
            step({"who": who, "act": "cheer", "target": partner[who],
                  "text": f"{name(who)} cheers on {name(partner[who])}!" if partner[who] is not None else f"{name(who)} cheers!"})
    # it burns at the end of the round (twice as hard after a Blaze or a Wildfire)
    hot = 2 if "burn" in b["effects"] else 1 if "glowing" in b["marks"] else 0
    if b["energy"] > 0 and hot:
        burn = max(1, round(pet_hit(_even_power(b["level"])) * BURN * hot))
        b["energy"] = max(0, b["energy"] - burn)
        step({"who": "foe", "act": "burn", "target": "foe", "type": "ember", "damage": burn, "text": f"The {foe} burns for {burn}."})
    for i in able:  # healers, once the creature's still standing
        p = partner[i]
        if b["energy"] > 0 and team[i].get("focus") == "healer" and p is not None and energy[i] > 0 and energy[p] > 0:
            for entry in _heal(b, team, i, p, energy, mana):
                step(entry)
    # marks and effects wear off
    b["marks"] = {k: r - 1 for k, r in b["marks"].items() if r > 1}
    b["effects"] = {k: r - 1 for k, r in b["effects"].items() if r > 1}
    b["focus"] = focus_next
    b["log"] = log
    if b["energy"] <= 0:
        b["over"] = "won"
    elif not any(energy[i] > 0 for i in b["fighters"]):
        b["over"] = "lost"
    return b, energy, mana


def _heal(b: dict, team: list[dict], i: int, p: int, energy: list[int], mana: list[int]) -> list[dict]:
    """A healer's partner gets some energy and mana back."""
    given = lambda what: b["healed"].get(f"{i}:{what}", 0)  # noqa: E731
    e = min(HEAL_ENERGY, HEAL_MAX_ENERGY - given("energy"), team[p]["energy"] - energy[p])
    m = min(HEAL_MANA, HEAL_MAX_MANA - given("mana"), team[p]["mana"] - mana[p])
    if e <= 0 and m <= 0:
        return []
    e, m = max(0, e), max(0, m)
    energy[p] += e
    mana[p] += m
    b["healed"][f"{i}:energy"] = given("energy") + e
    b["healed"][f"{i}:mana"] = given("mana") + m
    own = own_type(team[i])
    gains = " and ".join(x for x in (f"+{e} energy" if e else "", f"+{m} mana" if m else "") if x)
    return [{"who": i, "act": "heal", "target": p, "type": own, "gain": e or m, "flash": [i, "healer"],
             "text": f"{FOCUS_NAMES[own]['healer']}: {team[p]['name']} {gains}."}]


def _guardian_blocks(b: dict, team: list[dict], energy: list[int], target: int) -> tuple[tuple[str, ...], int | None]:
    """The types a Guardian partner keeps off `target` this round, and which place it is."""
    if b["round"] > GUARDIAN_ROUNDS:
        return (), None
    for i in b["fighters"]:
        if i != target and team[i].get("focus") == "guardian" and energy[i] > 0:
            return strong_against(own_type(team[i])), i
    return (), None


def _hit(b: dict, team: list[dict], who: int, move: str, strength: float, energy: list[int], mana: list[int]) -> dict:
    """A fighter's attack or big move: damage, any combos with the marks on
    it (each uses up its mark), and (a big move) its own mark."""
    foe = b["species"]
    kind = best_type(team[who], b["kind"])
    mult = matchup(kind, b["kind"])
    power = pet_hit(team[who]["power"]) * mult * strength * (BIG if move == "big" else 1)
    extra, found, flash = "", None, None
    if _doubles(team[who], kind):
        power *= DAREDEVIL
        energy[who] = max(1, energy[who] - _daredevil_cost(team[who]))
        extra += f" {FOCUS_NAMES[kind]['daredevil']}: double!"
        flash = [who, "daredevil"]
    if "popped" in b["effects"]:
        power *= POP
        b["effects"].pop("popped")
        extra += " Pop!"
    for mark in list(b["marks"]):
        combo = COMBOS.get((mark, kind))
        if not combo:
            continue
        found = combo.name
        power *= combo.mult
        b["skip"] = max(b["skip"], combo.skip)
        for effect, rounds in combo.effects:
            b["effects"][effect] = max(b["effects"].get(effect, 0), rounds)
        if combo.keep:
            b["marks"][mark] = combo.keep
        else:
            del b["marks"][mark]
        if combo.mark:
            b["marks"][combo.mark] = MARK_ROUNDS
        for i in b["fighters"]:
            if energy[i] > 0:
                energy[i] = min(team[i]["energy"], energy[i] + round(team[i]["energy"] * combo.pets_energy))
                mana[i] = min(team[i]["mana"], mana[i] + combo.pets_mana)
        extra += f" {combo.name}!"
    dmg = max(1, round(power))
    b["energy"] = max(0, b["energy"] - dmg)
    if move == "big":
        mana[who] -= BIG_MANA
        mark = MARKS[kind]
        b["marks"][mark] = MARK_ROUNDS
        extra += f" The {foe} is {mark}."
    what = f"big {wd.tw(kind)} move" if move == "big" else f"{wd.tw(kind)} attack"
    return {"who": who, "act": "hit", "target": "foe", "type": kind, "damage": dmg, "big": move == "big", "combo": found, "flash": flash,
            "text": f"{team[who]['name']}'s {what} does {dmg}.{_strength(mult)}{extra}"}


def _foe_acts(b: dict, team: list[dict], energy: list[int], able: list[int], guards: dict, rng) -> list[dict]:
    """The creature's go: unless it loses the turn (asleep, rooted, steam)
    or dozes off, it hits one fighter (or whoever guards that one), or
    itself when it's confused; thorns hurt it back."""
    foe = b["species"]
    even = pet_hit(_even_power(b["level"]))
    if b["skip"] > 0:
        b["skip"] -= 1
        return [{"who": "foe", "act": "skip", "text": f"The {foe} can't move!"}]
    if "doze" in b["effects"] or ("drowsy" in b["marks"] and rng.random() < DOZE):
        b["effects"].pop("doze", None)
        return [{"who": "foe", "act": "doze", "text": f"The {foe} dozes off..."}]
    if "confused" in b["effects"]:
        b["effects"].pop("confused")
        dmg = max(1, round(even))
        b["energy"] = max(0, b["energy"] - dmg)
        return [{"who": "foe", "act": "hit", "target": "foe", "type": b["kind"], "damage": dmg,
                 "text": f"The {foe} is so dizzy it hits itself for {dmg}!"}]
    targets = [i for i in able if energy[i] > 0]
    if not targets:
        return []
    aim = rng.choice(targets)
    guard = guards.get(aim)
    blocked, guardian = _guardian_blocks(b, team, energy, aim)
    if blocked and foe_type(b, own_type(team[aim]), blocked) is None:
        # nothing it has can get through
        shield = FOCUS_NAMES[own_type(team[guardian])]["guardian"]
        return [{"who": "foe", "act": "blocked", "target": aim, "type": b["kind"], "flash": [guardian, "guardian"],
                 "text": f"{shield} keeps the {foe} off {team[aim]['name']}!"}]
    i = guard if guard is not None and energy[guard] > 0 else aim
    m = team[i]
    ratio = max(0.5, min(2.0, b["level"] / max(1, m["level"])))
    share = FAIR_COST / (ROUNDS / len(b["fighters"]))  # its hits land on two fighters
    defends = own_type(m)
    blocked, guardian = _guardian_blocks(b, team, energy, i)
    kind = foe_type(b, defends, blocked)
    if kind is None:  # it guarded its partner, and a Guardian partner of its own keeps this off it too
        shield = FOCUS_NAMES[own_type(team[guardian])]["guardian"]
        return [{"who": "foe", "act": "blocked", "target": i, "type": b["kind"], "flash": [guardian, "guardian"],
                 "text": f"{shield} keeps the {foe} off {m['name']}!"}]
    mult = matchup(kind, defends)
    hit = m["energy"] * share * mult * ratio
    if i != aim:
        hit *= GUARD_STRONG if m.get("focus") == "guardian" and kind == beaten_by(defends) else GUARD
    if "tangled" in b["marks"]:
        hit *= TANGLED_HITS
    if "drenched" in b["effects"]:
        hit *= 0.5
    dmg = max(1, round(hit))
    energy[i] = max(0, energy[i] - dmg)
    guarded = f" {m['name']} guards {team[aim]['name']}!" if i != aim else ""
    out = [{"who": "foe", "act": "hit", "target": i, "type": kind, "damage": dmg,
            "text": f"The {foe} hits {m['name']} for {dmg}.{_strength(mult)}{guarded}"}]
    if "thorns" in b["effects"]:
        prick = max(1, round(even * 0.5))
        b["energy"] = max(0, b["energy"] - prick)
        out.append({"who": "foe", "act": "burn", "target": "foe", "type": "leaf", "damage": prick,
                    "text": f"Ouch, thorns! The {foe} takes {prick}."})
    return out


def xp(battle: dict, team: list[dict]) -> int:
    """XP for each fighter that won: more for a tougher creature."""
    levels = [team[i]["level"] for i in battle["fighters"]]
    return max(XP_RANGE[0], min(XP_RANGE[1], round(XP_EVEN * battle["level"] / (sum(levels) / len(levels)))))
