#!/usr/bin/env python3
"""Wanderpaw's balance report: how long leveling takes and how fights feel.

Not part of the game or the test suite. Run it around big balance changes
(XP, creature levels, battle numbers, energy) and compare with TARGETS:

    .venv/bin/python tools/wander_balance.py
    .venv/bin/python tools/wander_balance.py --growth 1.05 1.08 1.1
    .venv/bin/python tools/wander_balance.py --fights 5 8 13 --relic-every 10

It exits 1 if a number has left its target, so check whether that's what
you meant, then move the target if it is. It reads the real game code
(worlds, battles, XP), so it follows the rules as they change. What it
can't read is how people play; those guesses are the PLAY constants below.
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from itertools import accumulate
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.wanderpaw import battle as bt  # noqa: E402
from app.wanderpaw import critters as cr  # noqa: E402
from app.wanderpaw import pets as wp  # noqa: E402
from app.wanderpaw import world as wd  # noqa: E402

# PLAY: guesses at how a session goes, not game rules.
FIGHTS = (5, 8, 13)  # a short, ordinary and long session (8: about 10 minutes)
BASE_FIGHTS = 8
STEPS_PER_FIGHT = 10
STORY_XP = 60  # quests and temples, for everyone in the party, each session ...
STORY_SESSIONS = 50  # ... while the story lasts
RELIC_EVERY = 10  # sessions between relics
FIGHT_UP = 2  # the most levels above a pair that anyone picks a fight with
SLIPS = 1  # per move, in simulated fights
PARTY = {"favorite": (2, 2), "other": (3, 1)}  # how many, how often each fights (favorites 2x)

LEVELS = (5, 10, 15, 20)
SEEDS = 8
SIM_RUNS = 30
FIGHT_RUNS = 300
MATCHUPS = ((1, 2), (3, 3), (3, 5), (5, 5), (5, 8), (8, 8), (8, 11), (10, 10), (10, 14), (15, 15), (15, 19), (21, 21), (21, 14), (5, 14))

# What the game should feel like. name -> (low, high)
TARGETS = {
    "even fights from level 7, no mana: rounds": (3, 5.5),
    "even fights from level 7, burning mana: rounds": (1.5, 5),
    "even fights from level 7, no mana: energy %": (8, 25),
    "even fights from level 7, burning mana: energy + mana / 2": (10, 22),
    "even fights: lowest win %": (85, 100),
    "favorite: sessions to level 20": (35, 65),  # maxing favorites around the game's end is fine
    "other: sessions to level 20": (65, 130),  # the whole party shouldn't max out with nothing to do
    "other: sessions to level 5": (4, 12),  # the second type should come soon
    "energy loop: most energy out of a fight (from 20%)": (0, 21),  # a fight is never a refill
    "capstones: most energy saved": (0.5, 16),  # strong ones are fine this late
    "level 9 focus: most energy saved": (1.5, 10),  # (Elementalist+ tops it: fine, long fights cost more)
    "level 9 focus: least energy saved": (0, 5),  # (Daredevil+: a glass cannon, it pays in energy for its speed)
    "level 9 upgrade: most energy saved": (1, 5),  # none the obvious pick
    "level 7 moves: most energy saved": (5, 20),  # roughly equal, none a must-have ...
    "level 7 moves: least energy saved": (-4, 6),  # ... and none a waste of 4 mana
}


def creature_levels(seeds: int = SEEDS) -> tuple[Counter, dict[int, list[int]]]:
    """How common each creature level is (no relics), overall and by ring."""
    pop, rings = Counter(), defaultdict(list)
    for seed in range(1, seeds + 1):
        for big, here in wd.generate(seed).hexes.items():
            for c in cr.at(seed, big, 1).values():
                pop[c.level] += 1
                rings[here.ring].append(c.level)
    return pop, rings


def fight(level: int, foe_level: int, rng: random.Random) -> tuple[bool, int, float, int]:
    """Two even pets against a creature: won, rounds, energy cost each, XP each."""
    team = [wp.starter("splash", level), wp.starter("splash", level)]
    kind = rng.choice(wp.TYPES)
    foe = cr._grown(cr.Critter("x", (0, 0), (0, 0), "dog", kind, foe_level, False, rng.randrange(2**31)), 0)
    b = bt.start(foe, [0, 1])
    energy, mana = [m["energy"] for m in team], [m["mana"] for m in team]
    full, rounds = sum(energy), 0
    while not b["over"] and rounds < 40:
        able = [i for i in range(2) if energy[i] > 0]
        picks = [{"move": "big" if rounds == 0 and n == 0 else "attack", "slips": SLIPS} for n, _ in enumerate(able)]
        b, energy, mana = bt.turn(b, team, energy, picks, rng, mana)
        rounds += 1
    return b["over"] == "won", rounds, (full - sum(energy)) / full, bt.xp(b, team)


def mix_fight(first: str, second: str, species: str | None, level: int, foe_level: int, rng: random.Random, use_it: bool = True) -> tuple[int, float]:
    """A pet using its level 7 move once (the day's mana won't stretch further) beside a plain partner."""
    pet = wp.starter(first, level)
    pet = {**pet, "types": {first: level, second: max(1, level - 4)}, "swaps": {"rest": "mix"}, "species": species or pet["species"]}
    move = bt.mix_move(pet)
    # moves that give energy back wait until there's some to give
    wait = 1 if move.team_energy or move.partner_energy or move.self_energy > 0 or ("mending", 3) in move.effects else 0
    team = [pet, wp.starter(rng.choice(wp.TYPES), level)]
    foe = cr._grown(cr.Critter("x", (0, 0), (0, 0), "dog", rng.choice(wp.TYPES), foe_level, False, rng.randrange(2**31)), 0)
    b = bt.start(foe, [0, 1])
    energy, mana = [m["energy"] for m in team], [m["mana"] for m in team]
    full, rounds, used = sum(energy), 0, False
    while not b["over"] and rounds < 40:
        able = [i for i in range(2) if energy[i] > 0]
        picks = []
        for i in able:
            use = use_it and i == 0 and not used and rounds >= wait and mana[0] >= bt.MIX_MANA
            used = used or use
            picks.append({"move": "mix" if use else "attack", "slips": SLIPS})
        b, energy, mana = bt.turn(b, team, energy, picks, rng, mana)
        rounds += 1
    return rounds, 100 * (full - sum(energy)) / full


def mix_table(level: int = 7, foe_level: int = 10) -> tuple[list[tuple[str, float, float]], float, float]:
    """Every level 7 move: rounds and energy each, and the same for plain attacks."""
    rng = random.Random(1)
    plain = [mix_fight(*rng.sample(wp.TYPES, 2), None, level, foe_level, rng, use_it=False) for _ in range(FIGHT_RUNS * 5)]
    rows = []
    every = [(pair, None, m.name) for pair, m in bt.MIX_MOVES.items()]
    every += [(wp.SPECIES_TYPES[sp], sp, m.name + "*") for sp, m in bt.MYTHICAL_MOVES.items()]
    for (first, second), species, name in every:
        runs = [mix_fight(first, second, species, level, foe_level, rng) for _ in range(FIGHT_RUNS)]
        rows.append((name, statistics.mean(r[0] for r in runs), statistics.mean(r[1] for r in runs)))
    return sorted(rows, key=lambda r: r[2]), statistics.mean(p[0] for p in plain), statistics.mean(p[1] for p in plain)


def _nine_pet(focus: str | None, upgrade: str | None, level: int, rng: random.Random) -> dict:
    """A level 9 pet with two types: its second attack in a grey slot the test isn't about."""
    first, second = rng.sample(wp.TYPES, 2)
    pet = wp.starter(first, level)
    slot = next(m for m in ("cheer", "focus", "rest", "guard") if m != upgrade and m != (bt.FOCUS_REPLACES[focus] if focus else None))
    return {**pet, "types": {first: level, second: level - 4}, "focus": focus, "swaps": {slot: "attack2"}, "upgrades": [upgrade] if upgrade else []}


def _best_attack(pet: dict, foe_kind: str) -> str:
    """Whichever of its two attacks hits this creature harder, doubling and all."""
    own, second = list(pet["types"])[:2]
    power = lambda k: bt.matchup(k, foe_kind) * (bt.DAREDEVIL if bt._doubles(pet, k) else 1)  # noqa: E731
    return "attack" if power(own) >= power(second) else "attack2"


def nine_fight(focus: str | None, upgrade: str | None, level: int, foe_level: int, rng: random.Random) -> tuple[int, float]:
    """A level 9 pet fighting its way, beside a plain partner."""
    pet = _nine_pet(focus, upgrade, level, rng)
    team = [pet, wp.starter(rng.choice(wp.TYPES), level)]
    foe = cr._grown(cr.Critter("x", (0, 0), (0, 0), "dog", rng.choice(wp.TYPES), foe_level, False, rng.randrange(2**31)), 0)
    b = bt.start(foe, [0, 1])
    energy, mana = [m["energy"] for m in team], [m["mana"] for m in team]
    full, rounds = sum(energy), 0
    while not b["over"] and rounds < 40:
        move = _best_attack(pet, foe.kind)
        if focus == "elementalist" and rounds % 2 == 0 and mana[0] >= bt.MARK_MANA:
            move = "mark"
        elif upgrade == "big" and rounds == 0 and mana[0] >= bt.big_mana(pet):
            move = "big"
        elif upgrade in ("guard", "focus", "cheer") and rounds == 0:
            move = upgrade
        elif upgrade == "rest" and energy[0] < pet["energy"] * 0.6:
            move = "rest"
        picks = [{"move": move if i == 0 else "attack", "slips": SLIPS} for i in range(2) if energy[i] > 0]
        b, energy, mana = bt.turn(b, team, energy, picks, rng, mana)
        rounds += 1
    return rounds, 100 * (full - sum(energy)) / full


def nine_table(level: int = 9, foe_level: int = 12) -> list[tuple[str, float, float, float, float]]:
    """Each focus before and after level 9's growth, and each move before and after its "+"."""
    rows = []
    both = lambda f, u, seed: [nine_fight(f, u, level, foe_level, random.Random(seed * 7919 + i)) for i in range(FIGHT_RUNS * 2)]  # noqa: E731
    mean = lambda runs, i: statistics.mean(r[i] for r in runs)  # noqa: E731
    keep = bt.FOCUS_PLUS_LEVEL
    for focus in bt.FOCUSES:
        bt.FOCUS_PLUS_LEVEL = 99
        was = both(focus, None, 1)
        bt.FOCUS_PLUS_LEVEL = keep
        now = both(focus, None, 1)
        rows.append((f"{bt.FOCUS_TITLES[focus]}+", mean(was, 0), mean(was, 1), mean(now, 0), mean(now, 1)))
    bt.FOCUS_PLUS_LEVEL = 99  # the upgrades on their own
    for name, upgrade in (("Attack+", "attack"), ("Big+", "big"), ("Guard+", "guard"), ("Focus+", "focus"), ("Cheer+", "cheer"), ("Rest+", "rest")):
        real = upgrade
        plain = _strip(both, None, upgrade)
        now = both(None, real, 2)
        rows.append((name, mean(plain, 0), mean(plain, 1), mean(now, 0), mean(now, 1)))
    bt.FOCUS_PLUS_LEVEL = keep
    return rows


def _strip(both, focus: str | None, upgrade: str) -> list[tuple[int, float]]:
    """The same fights with the move as it was: its use, without its "+"."""
    keep = bt.upgraded
    bt.upgraded = lambda member, move: False
    runs = both(focus, upgrade, 2)
    bt.upgraded = keep
    return runs


def build_pet(level: int, focus: str | None, first: str, second: str, species: str | None = None) -> dict:
    """A pet as a player would have it at a level: its focus at 3, second attack
    at 5, mix at 7, upgrades at 9 and 11, a move back at 11, the other mix at 13.
    New moves take the grey slots its focus left."""
    pet = wp.starter(first, level)
    grey = [m for m in ("focus", "cheer", "guard") if not focus or m != bt.FOCUS_REPLACES[focus]]
    swaps: dict[str, str] = {}
    if level >= 5 and grey:
        swaps[grey.pop(0)] = "attack2"
    if level >= 7 and grey:
        swaps[grey.pop(0)] = "mix"
    if level >= 13 and grey:
        swaps[grey.pop(0)] = "mix2"
    upgrades = ["attack"] * (level >= 9) + ["big"] * (level >= 11)
    kinds = {first: level, **({second: level - 4} if level >= 5 else {})}
    extra: list[str] = []
    if level >= 15:  # rest, a slot it can spare, goes for the third type's attack+
        third = next(t for t in wp.TYPES if t not in kinds)
        kinds[third] = level - 14
        swaps["rest"] = "attack3"
        upgrades.append("attack3")
    if level >= 17:
        extra.append(bt.mix_id((first, third)))
    if level >= 19:  # guard, or whatever's left, for one more mix
        swaps["guard" if "guard" not in swaps and (not focus or bt.FOCUS_REPLACES[focus] != "guard") else "attack2"] = bt.mix_id((third, first))
    return {**pet, "types": kinds, "focus": focus if level >= 3 else None, "swaps": swaps, "upgrades": upgrades,
            "extra": extra, **({"species": species} if species else {})}


def _smart_pick(pet: dict, foe_kind: str, energy: int, mana: int, used: set[str], b: dict, place: int, round_no: int) -> str:
    """A sensible player: each mix and Big once a fight, an Elementalist's mark on
    odd rounds, otherwise whichever attack hits hardest."""
    ids = {m["id"]: m for m in bt.moves(pet, foe_kind, mana)}
    for move in (*(i for i in ids if bt.is_mix(i)), "big"):
        m = ids.get(move)
        if m and move not in used and m.get("can") is not False and not m.get("passive") and not bt.used_up(b, place, pet, move):
            used.add(move)
            return move
    if "mark" in ids and round_no % 2 == 0 and ids["mark"].get("can") is not False:
        return "mark"
    return _best_attack(pet, foe_kind) if "attack2" in ids else "attack"


def level_fight(level: int, focus: str | None, foe_level: int, rng: random.Random) -> tuple[bool, int, float, int]:
    """A pair at a level: a built pet beside a pet of the same level. Won, rounds, energy %, mana used."""
    a, b_ = rng.sample(wp.TYPES, 2)
    pet = build_pet(level, focus, a, b_)
    other = rng.choice(wp.TYPES)
    friend = build_pet(level, rng.choice(bt.FOCUSES), other, rng.choice([t for t in wp.TYPES if t != other]))
    team = [pet, friend]
    foe = cr._grown(cr.Critter("x", (0, 0), (0, 0), "dog", rng.choice(wp.TYPES), foe_level, False, rng.randrange(2**31)), 0)
    b = bt.start(foe, [0, 1])
    energy, mana = [m["energy"] for m in team], [m["mana"] for m in team]
    full, spent, rounds = sum(energy), sum(mana), 0
    used: list[set[str]] = [set(), set()]
    while not b["over"] and rounds < 60:
        picks = [{"move": _smart_pick(team[i], foe.kind, energy[i], mana[i], used[i], b, i, rounds), "slips": SLIPS} for i in range(2) if energy[i] > 0]
        b, energy, mana = bt.turn(b, team, energy, picks, rng, mana)
        rounds += 1
    return b["over"] == "won", rounds, 100 * (full - sum(energy)) / full, spent - sum(mana)


def level_table() -> list[tuple]:
    """How strong a pair is at each level: against an even creature and one 3 up."""
    rows = []
    for level in (1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21):
        for focus in (None, *bt.FOCUSES) if level >= 3 else (None,):
            if focus is None and level >= 3:
                continue
            rng = random.Random(level)
            even = [level_fight(level, focus, level, rng) for _ in range(FIGHT_RUNS)]
            up = [level_fight(level, focus, min(wp.MAX_LEVEL, level + 3), rng) for _ in range(FIGHT_RUNS)]
            mean = lambda runs, i: statistics.mean(r[i] for r in runs)  # noqa: E731
            rows.append((level, bt.FOCUS_TITLES.get(focus, "none"), mean(even, 1), mean(even, 2), mean(even, 3), 100 * mean(up, 0), mean(up, 1), mean(up, 2), mean(up, 3)))
    return rows


# The energy loop: how much can a pair get back by stalling a fight on purpose?
# Each entry: name, level, its focus, its type pair, a species, its upgrades,
# and the moves it uses to restore or to keep Enemy from hurting anyone.
LOOP_BUILDS = (
    ("Plain pets: Rest, Rest", 3, None, ("ember", "leaf"), None, [], ()),
    ("Plain pets: Rest, Rest", 7, None, ("ember", "leaf"), None, [], ()),
    ("Plain pets: Rest, Rest", 13, None, ("ember", "leaf"), None, [], ()),
    ("Rest+", 9, None, ("ember", "leaf"), None, ["rest"], ()),
    ("Healer+ beside Rest", 9, "healer", ("ember", "leaf"), None, [], ()),
    ("Spring Shower", 7, None, ("leaf", "splash"), None, [], ("mix",)),
    ("Rain Garden", 7, None, ("splash", "leaf"), None, [], ("mix",)),
    ("Burning Brambles", 7, None, ("leaf", "ember"), None, [], ("mix",)),
    ("Power Sprout", 7, None, ("shock", "leaf"), None, [], ("mix",)),
    ("Steam Veil", 7, None, ("splash", "ember"), None, [], ("mix",)),
    ("Campfire Tale", 7, None, ("dream", "ember"), None, [], ("mix",)),
    ("Sleep Spores", 7, None, ("dream", "leaf"), None, [], ("mix",)),
    ("Rainbow Blessing", 7, None, ("dream", "leaf"), "unicorn", [], ("mix",)),
    ("Sanctuary + Rainbow", 13, None, ("dream", "leaf"), "unicorn", [], ("mix2", "mix")),
    ("Moon Tide + Rest+", 9, None, ("splash", "dream"), None, ["rest"], ("mix",)),
)
LOOP_START = 0.2  # of full energy, going in
LOOP_ENOUGH = 0.9  # of full energy: when the player stops stalling and finishes it


def _loop_pet(level: int, focus: str | None, pair: tuple[str, str], species: str | None, upgrades: list[str], moves_used: tuple) -> dict:
    """A pet keeping Rest and Attack, with the moves it needs in other slots."""
    pet = wp.starter(pair[0], level)
    swaps = {}
    free = [m for m in ("focus", "cheer", "guard") if not focus or m != bt.FOCUS_REPLACES[focus]]
    for move in moves_used:
        swaps[free.pop(0)] = move
    kinds = {pair[0]: level, pair[1]: max(1, level - 4)} if level >= 5 or species else {pair[0]: level}
    return {**pet, "types": kinds, "focus": focus, "swaps": swaps, "upgrades": upgrades, "extra": [], **({"species": species} if species else {})}


def energy_loop(build: tuple, foe_level: int, rng: random.Random) -> tuple[bool, int, float, float]:
    """Stall on purpose: restore until both pets are full (the special moves
    first, whenever there's mana), then finish it off. Won, rounds, energy and
    mana going out as a % of full (coming in at LOOP_START of each)."""
    _, level, focus, pair, species, upgrades, moves_used = build
    pet = _loop_pet(level, focus, pair, species, upgrades, moves_used)
    friend = wp.starter(rng.choice(wp.TYPES), level)
    team = [pet, friend]
    foe = cr._grown(cr.Critter("x", (0, 0), (0, 0), "dog", rng.choice(wp.TYPES), foe_level, False, rng.randrange(2**31)), 0)
    b = bt.start(foe, [0, 1])
    fulls = [m["energy"] for m in team]
    energy = [max(1, round(f * LOOP_START)) for f in fulls]
    mana = [m["mana"] for m in team]
    rounds = 0
    while not b["over"] and rounds < 150:
        hurt = any(energy[i] < fulls[i] * LOOP_ENOUGH for i in range(2) if energy[i] > 0)
        picks = []
        for i in range(2):
            if energy[i] <= 0:
                continue
            move = "attack"
            if hurt:
                move = "rest"
                if i == 0:
                    for m in moves_used:
                        card = next(x for x in bt.moves(pet, foe.kind, mana[0]) if x["id"] == m)
                        if card.get("can") is not False and not bt.used_up(b, 0, pet, m) and not card.get("passive"):
                            move = m
                            break
            picks.append({"move": move, "slips": SLIPS})
        b, energy, mana = bt.turn(b, team, energy, picks, rng, mana)
        rounds += 1
    full, have = sum(fulls), sum(energy)
    return b["over"] == "won", rounds, 100 * have / full, 100 * sum(mana) / sum(m["mana"] for m in team)


def loop_table() -> list[tuple]:
    rows = []
    for build in LOOP_BUILDS:
        level = build[1]
        for name, foe_level in (("even", level), ("3 up", level + 3), ("weak", max(1, level - 4))):
            rng = random.Random(level * 31 + foe_level)
            runs = [energy_loop(build, foe_level, rng) for _ in range(FIGHT_RUNS // 3)]
            wins = [r for r in runs if r[0]] or runs  # what a winner walks away with
            rows.append((build[0], level, name, 100 * statistics.mean(r[0] for r in runs), statistics.mean(r[1] for r in wins),
                         statistics.mean(r[2] for r in wins), statistics.mean(r[3] for r in wins)))
    return rows


def capstone_fight(bench: tuple[str, ...], rng: random.Random, level: int = 21, foe_level: int = 21) -> tuple[bool, int, float]:
    """Two full-grown pets, attacks only so a bench's help shows, with these capstones helping."""
    a, c = rng.sample(wp.TYPES, 2)
    team = [build_pet(level, None, a, c), build_pet(level, None, c, a)]
    team = [{**m, "bright": "bright_idea" in bench} for m in team]
    foe = cr._grown(cr.Critter("x", (0, 0), (0, 0), "dog", rng.choice(wp.TYPES), foe_level, False, rng.randrange(2**31)), 0)
    b = bt.start(foe, [0, 1], bench)
    energy, mana = [m["energy"] for m in team], [m["mana"] for m in team]
    full, rounds = sum(energy), 0
    while not b["over"] and rounds < 40:
        picks = [{"move": "attack2" if "attack2" in {m["id"] for m in bt.moves(team[i])} else "attack", "slips": SLIPS} for i in range(2) if energy[i] > 0]
        b, energy, mana = bt.turn(b, team, energy, picks, rng, mana)
        rounds += 1
    return b["over"] == "won", rounds, 100 * (full - sum(energy)) / full


def capstone_table() -> tuple[list[tuple], float, float]:
    """Each capstone against no bench, then three together."""
    runs = lambda bench: [capstone_fight(bench, random.Random(i)) for i in range(FIGHT_RUNS * 2)]  # noqa: E731
    base = runs(())
    r0, c0 = statistics.mean(r[1] for r in base), statistics.mean(r[2] for r in base)
    rows = []
    for cap in bt.CAPSTONES.values():
        now = runs((cap.key,))
        rows.append((cap.name, statistics.mean(r[1] for r in now), statistics.mean(r[2] for r in now)))
    return sorted(rows, key=lambda r: r[2]), r0, c0


# A smart player: knows Enemy's type, brings pets strong against it, and each
# round plays whichever pair of moves does the most damage.
SMART_LEVELS = (1, 3, 5, 7, 9, 12, 14, 17, 19, 21)
SMART_ROUNDS = 5
SMART_BUILDS = (("daredevil", "daredevil"), ("daredevil", "elementalist"), ("elementalist", "guardian"), ("healer", "daredevil"))
SMART_RUNS = 12


def _strong_against(foe_kind: str) -> tuple[str, str]:
    """The types that hit this type hardest: x2, then x1.5."""
    ranked = sorted(wp.TYPES, key=lambda t: -bt.matchup(t, foe_kind))
    return ranked[0], ranked[1]


def _smart_team(level: int, foes: tuple[str | None, str | None], foe_kind: str, rng: random.Random) -> list[dict]:
    best, good = _strong_against(foe_kind)
    others = [t for t in wp.TYPES if t not in (best, good)]
    return [build_pet(level, foes[0], best, good if level >= 5 else rng.choice(others)),
            build_pet(level, foes[1], good, best if level >= 5 else rng.choice(others))]


def _best_round(b: dict, team: list[dict], energy: list[int], mana: list[int], use_mana: bool, rng_seed: int) -> tuple[dict, list[int], list[int]]:
    """Try every pair of moves through the real battle, keep whichever does the most damage."""
    def options(i: int) -> list[str]:
        out = []
        for m in bt.battle_moves(b, i, team[i], mana[i]):
            costs = m["icons"]["cost"].get("mana", 0)
            if m.get("passive") or m.get("can") is False or (costs and not use_mana):
                continue
            if "hit" in m["icons"] or m["icons"].get("marks") or m["id"] == "mark":
                out.append(m["id"])
        return out or ["attack"]
    best = None
    for one in options(0):
        for two in options(1):
            picks = [{"move": one, "slips": SLIPS}, {"move": two, "slips": SLIPS}]
            try:
                result = bt.turn(b, team, energy, picks, random.Random(rng_seed), mana)
            except ValueError:
                continue
            dealt = b["energy"] - result[0]["energy"]
            if best is None or dealt > best[0]:
                best = (dealt, result)
    return best[1]


def smart_fight(level: int, build: tuple, use_mana: bool, seed: int) -> list[tuple[float, int]]:
    """Damage and mana spent each round, against an Enemy that can take it all."""
    rng = random.Random(seed)
    foe_kind = rng.choice(wp.TYPES)
    focuses = build if level >= 3 else (None, None)
    team = _smart_team(level, focuses, foe_kind, rng)
    foe = cr.Critter("x", (0, 0), (0, 0), "dog", foe_kind, level, False, rng.randrange(2**31))
    b = {**bt.start(foe, [0, 1]), "energy": 10**6, "max": 10**6}
    energy, mana = [m["energy"] * 3 for m in team], [m["mana"] for m in team]
    out = []
    for r in range(SMART_ROUNDS):
        before, spent = b["energy"], sum(mana)
        b, energy, mana = _best_round(b, team, energy, mana, use_mana, seed + r)
        out.append((before - b["energy"], spent - sum(mana)))
    return out


def smart_table() -> list[tuple]:
    """By level, for the strongest build: round 1, the average with and without mana."""
    rows = []
    for level in SMART_LEVELS:
        best = None
        for build in SMART_BUILDS:
            burn = [smart_fight(level, build, True, s) for s in range(SMART_RUNS)]
            plain = [smart_fight(level, build, False, s) for s in range(SMART_RUNS)]
            first = statistics.mean(f[0][0] for f in burn)
            peak = max(f[0][0] for f in burn)
            burn_avg = statistics.mean(sum(x[0] for x in f) / SMART_ROUNDS for f in burn)
            plain_avg = statistics.mean(sum(x[0] for x in f) / SMART_ROUNDS for f in plain)
            mana_used = statistics.mean(sum(x[1] for x in f) for f in burn)
            row = (level, "+".join(b[:5] for b in build), first, peak, burn_avg, plain_avg, mana_used)
            if best is None or row[2] > best[2]:
                best = row
        rows.append(best)
    return rows


# Even fights: a pet against a creature of its own level. An even fight should
# cost a pair about 15% as energy + mana / 2, and take about 4 rounds with no
# mana, fewer burning it.
EVEN_LEVELS = (1, 3, 5, 7, 9, 12, 14, 17, 19, 21)
EVEN_RUNS = 40
EVEN_BUILD = ("healer", "daredevil")


def even_fight(level: int, use_mana: bool, seed: int, builds: tuple = EVEN_BUILD, tier: str = "") -> tuple[bool, int, float, float]:
    """A smart pair (it picks the best moves, knowing Enemy's type) in an even fight."""
    rng = random.Random(seed)
    foe = cr.Critter("x", (0, 0), (0, 0), "dog", rng.choice(wp.TYPES), level, False, rng.randrange(2**31), rng.choice(wp.TYPES) if level > 5 else None, tier)
    return _smart_fight(foe, level, use_mana, seed, builds)


def boss_fight(region: str, relics: int, ahead: int, use_mana: bool, seed: int) -> tuple[bool, int, float, float]:
    """A smart pair `ahead` levels above a temple's boss."""
    boss = cr.temple_boss(seed, region, (0, 0), relics)
    return _smart_fight(boss, min(wp.MAX_LEVEL, boss.level + ahead), use_mana, seed)


def _smart_fight(foe, level: int, use_mana: bool, seed: int, builds: tuple = EVEN_BUILD) -> tuple[bool, int, float, float]:
    rng = random.Random(seed)
    team = _smart_team(level, builds if level >= 3 else (None, None), foe.kind, rng)
    b = bt.start(foe, [0, 1])
    energy, mana = [m["energy"] for m in team], [m["mana"] for m in team]
    full, pool, rounds = sum(energy), sum(mana), 0
    while not b["over"] and rounds < 40 and any(energy):
        if all(energy):
            b, energy, mana = _best_round(b, team, energy, mana, use_mana, seed + rounds)
        else:
            picks = [{"move": "attack", "slips": SLIPS} if energy[i] else None for i in range(2)]
            b, energy, mana = bt.turn(b, team, energy, [p for p in picks if p], rng, mana)
        rounds += 1
    return b["over"] == "won", rounds, 100 * (full - sum(energy)) / full, 100 * (pool - sum(mana)) / pool


def even_table() -> list[tuple]:
    rows = []
    for level in EVEN_LEVELS:
        row = [level]
        for use_mana in (True, False):
            runs = [even_fight(level, use_mana, s) for s in range(EVEN_RUNS)]
            row += [100 * statistics.mean(r[0] for r in runs), statistics.mean(r[1] for r in runs), statistics.mean(r[2] for r in runs), statistics.mean(r[3] for r in runs)]
        rows.append(tuple(row))
    return rows


def tier_table() -> list[tuple]:
    """Tough creatures, champions and bosses of a pair's own level, with and without mana."""
    rows = []
    for level in (7, 14, 21):
        for tier in ("", "tough", "champion", "boss"):
            burn = [even_fight(level, True, s, tier=tier) for s in range(EVEN_RUNS // 2)]
            plain = [even_fight(level, False, s, tier=tier) for s in range(EVEN_RUNS // 2)]
            mean = lambda runs, i: statistics.mean(r[i] for r in runs)  # noqa: E731
            rows.append((level, tier or "plain", 100 * mean(burn, 0), mean(burn, 1), mean(burn, 2), mean(burn, 3),
                         100 * mean(plain, 0), mean(plain, 1), mean(plain, 2)))
    return rows


def boss_table(ahead: int = 0, runs: int = EVEN_RUNS // 2) -> list[tuple]:
    """Each boss, as the first to the last temple you'd take on."""
    rows = []
    for relics, region in enumerate(("shock", "ember", "dream", "splash", "leaf")):
        burn = [boss_fight(region, relics, ahead, True, s) for s in range(runs)]
        mean = lambda i: statistics.mean(r[i] for r in burn)  # noqa: E731
        won = [r for r in burn if r[0]]
        left = statistics.mean(r[2] for r in won) if won else 0
        rows.append((region, 13 + 2 * relics, 100 * mean(0), mean(1), mean(2), mean(3), left))
    return rows


def fight_table() -> dict[tuple[int, int], tuple[float, float, float, int]]:
    rng = random.Random(1)
    out = {}
    for level, foe in MATCHUPS:
        runs = [fight(level, foe, rng) for _ in range(FIGHT_RUNS)]
        out[level, foe] = (100 * statistics.mean(r[0] for r in runs), statistics.mean(r[1] for r in runs),
                           100 * statistics.mean(r[2] for r in runs), runs[0][3])
    return out


def _progress(table: tuple[int, ...], pop: Counter, fights: int, relic_every: int, seed: int) -> dict[tuple[str, int], int]:
    """One party's whole career: the session each kind of pet reaches each level."""
    rng = random.Random(seed)
    kinds = [kind for kind, (n, _) in PARTY.items() for _ in range(n)]
    weight = [PARTY[kind][1] for kind in kinds]
    watch = {kind: kinds.index(kind) for kind in PARTY}
    xp, fought, reached = [0] * len(kinds), [0] * len(kinds), {}
    level = lambda x: bisect_right(table, x)  # noqa: E731
    bases = sorted(pop)
    for session in range(1, 501):
        relics = min(5, (session - 1) // relic_every) if relic_every else 0
        foes = [min(wp.MAX_LEVEL, b + cr.RELIC_LEVELS * relics) for b in bases]
        for _ in range(fights):
            pair = sorted(range(len(kinds)), key=lambda i: fought[i] / weight[i] + rng.random() * 0.4)[:2]
            team = [{"level": level(xp[i])} for i in pair]
            mean = (team[0]["level"] + team[1]["level"]) / 2
            fair = [i for i, foe in enumerate(foes) if foe <= mean + FIGHT_UP and (session > 1 or foe <= 2)]
            foe = foes[rng.choices(fair, [pop[bases[i]] for i in fair])[0]] if fair else min(foes)
            gain = bt.xp({"level": foe, "fighters": [0, 1]}, team)
            for i in pair:
                xp[i] += gain
                fought[i] += 1
        if session <= STORY_SESSIONS:
            xp = [x + STORY_XP for x in xp]
        for kind, i in watch.items():
            for lv in LEVELS:
                if level(xp[i]) >= lv:
                    reached.setdefault((kind, lv), session)
        if len(reached) == len(PARTY) * len(LEVELS):
            break
    return reached


def sessions_to_levels(growth: float, pop: Counter, fights: int, relic_every: int) -> dict[tuple[str, int], int]:
    table = (0, *accumulate(wp._level_costs(growth)))
    runs = [_progress(table, pop, fights, relic_every, seed) for seed in range(SIM_RUNS)]
    return {(kind, lv): round(statistics.mean(r.get((kind, lv), 500) for r in runs)) for kind in PARTY for lv in LEVELS}


def energy_table() -> list[tuple[int, int, int, float]]:
    """Level, a pet's energy, a party's trip total, fights it can pay for (even fights)."""
    out = []
    for lv in (1, 5, 10, 15, 20, wp.MAX_LEVEL):
        pet = wp.stats("dog", wp.STARTER_STATS, wp.Record(xp=wp.xp_for(lv)))["energy"]
        total = 50 + wp.PARTY_SIZE * pet
        out.append((lv, pet, total, total / (STEPS_PER_FIGHT + 5 * bt.enemy_hit(lv))))
    return out


def _sessions_row(name: str, numbers: dict[tuple[str, int], int]) -> None:
    for kind in PARTY:
        print(f"  {name:<24}{kind:<10}" + "".join(f"{numbers[kind, lv]:>6}" for lv in LEVELS))


def main() -> int:
    parser = argparse.ArgumentParser(description="Wanderpaw's balance report (see the top of this file).")
    parser.add_argument("--growth", type=float, nargs="*", default=[], help="other XP multipliers to compare")
    parser.add_argument("--fights", type=int, nargs="*", default=list(FIGHTS), help="fights per session to compare")
    parser.add_argument("--relic-every", type=int, default=RELIC_EVERY, help="sessions between relics (0: none)")
    args = parser.parse_args()

    pop, rings = creature_levels()
    print(f"XP: {wp.XP_FIRST_LEVEL} for the first level, x{wp.XP_GROWTH} a level, cap {wp.MAX_LEVEL}")
    print("  total to level " + ", ".join(f"{lv}: {wp.xp_for(lv):,}" for lv in (*LEVELS, wp.MAX_LEVEL)))

    print(f"\nCreature levels by ring (no relics; each relic adds {cr.RELIC_LEVELS}, cap {wp.MAX_LEVEL})")
    for ring, levels in sorted(rings.items()):
        print(f"  ring {ring}: {min(levels):>2}-{max(levels):<2}  average {statistics.mean(levels):>4.1f}  ({len(levels)} creatures)")

    print("\nEnergy (average stamina)\n  level  pet  trip  fights it can pay for")
    for lv, pet, total, fights in energy_table():
        print(f"  {lv:>5}{pet:>5}{total:>6}{fights:>6.0f}")

    table = fight_table()
    print(f"\nFights ({SLIPS} slip a move, {FIGHT_RUNS} each)\n  pets  foe   win%  rounds  energy% each  XP each")
    for (level, foe), (win, rounds, cost, xp) in table.items():
        print(f"  {level:>4}{foe:>5}{win:>7.0f}{rounds:>8.1f}{cost:>14.1f}{xp:>9}")

    mixes, plain_rounds, plain_cost = mix_table()
    print(f"\nLevel 7 moves, used once a fight (level 7 pets, level 10 creature; * mythical)\n  plain attacks: {plain_rounds:.1f} rounds, {plain_cost:.1f}% energy each")
    for name, rounds, cost in mixes:
        print(f"  {name:<20}{rounds:>5.1f} rounds {cost:>6.1f}%  ({cost - plain_cost:+.1f})")

    nines = nine_table()
    print("\nLevel 9 (level 9 pets, level 12 creature): before and after the +")
    print("                  before              after")
    for name, r0, c0, r1, c1 in nines:
        print(f"  {name:<14}{r0:>5.1f} rounds {c0:>5.1f}%   {r1:>5.1f} rounds {c1:>5.1f}%  ({c1 - c0:+.1f})")

    print("\nPower by level: a built pet beside another, each using its mixes and Big once a fight")
    print("                            even creature                  creature 3 levels up")
    print("  level focus           rounds energy% mana     win% rounds energy% mana")
    levels = level_table()
    for level, focus, r0, c0, m0, w1, r1, c1, m1 in levels:
        print(f"  {level:>5} {focus:<14}{r0:>6.1f}{c0:>8.1f}{m0:>5.1f}{w1:>9.0f}{r1:>7.1f}{c1:>8.1f}{m1:>5.1f}")

    loops = loop_table()
    print(f"\nThe energy loop: come in at {LOOP_START:.0%} energy, stall on purpose until full, then finish it")
    print("  (rounds, energy and mana are for the fights it won)")
    print("  build                      level foe     win% rounds  energy out  mana out")
    for name, level, foe, win, rounds, out, mana_out in loops:
        print(f"  {name:<26}{level:>6} {foe:<6}{win:>6.0f}{rounds:>7.1f}{out:>10.0f}%{mana_out:>9.0f}%")

    caps, cap_rounds, cap_cost = capstone_table()
    print(f"\nCapstones (level 21 pets, even creature, plain attacks): none helping: {cap_rounds:.1f} rounds, {cap_cost:.1f}% energy each")
    for name, rounds, cost in caps:
        print(f"  {name:<16}{rounds:>5.1f} rounds {cost:>6.1f}%  ({cost - cap_cost:+.1f})")

    evens = even_table()
    print(f"\nEven fights, a smart {'+'.join(EVEN_BUILD)} pair: energy and mana spent, % of the pair's")
    print("  (target: about 15% as energy + mana / 2, and 3-5 rounds with no mana)")
    print("           burning mana                       no mana")
    print("  level  win% rounds energy% mana% score      win% rounds energy% score")
    for level, w1, r1, e1, m1, w2, r2, e2, m2 in evens:
        print(f"  {level:>5}{w1:>6.0f}{r1:>7.1f}{e1:>8.1f}{m1:>6.1f}{e1 + m1 / 2:>6.1f}{w2:>10.0f}{r2:>7.1f}{e2:>8.1f}{e2 + m2 / 2:>6.1f}")

    print("\nTiers: same-level creatures, the smart pair")
    print("           burning mana                       no mana")
    print("  level tier      win% rounds energy% mana%    win% rounds energy%")
    for level, tier, w1, r1, e1, m1, w2, r2, e2 in tier_table():
        print(f"  {level:>5} {tier:<9}{w1:>5.0f}{r1:>7.1f}{e1:>8.1f}{m1:>6.1f}{w2:>8.0f}{r2:>7.1f}{e2:>8.1f}")

    for ahead in (-2, 0, 2):
        print(f"\nBosses: a smart pair {ahead:+d} levels from the boss, burning mana")
        print("  boss    level  win% rounds energy% mana%  energy% in wins")
        for region, level, win, rounds, energy, mana, left in boss_table(ahead):
            print(f"  {region:<7}{level:>5}{win:>6.0f}{rounds:>7.1f}{energy:>8.1f}{mana:>6.1f}{left:>11.1f}")

    print("\nA smart player's damage a round, by level (the strongest build; Enemy's own energy for scale)")
    print("  level build            round 1  best  burning mana  no mana   mana used  Enemy now")
    for level, build, first, peak, burn_avg, plain_avg, used in smart_table():
        now = bt.start(cr.Critter("x", (0, 0), (0, 0), "dog", "ember", level, False, 1), [0, 1])["energy"]
        print(f"  {level:>5} {build:<17}{first:>6.0f}{peak:>7.0f}{burn_avg:>11.0f}{plain_avg:>10.0f}{used:>10.0f}{now:>10}")

    print(f"\nSessions to reach a level (a party of {' + '.join(f'{n} {k}' for k, (n, _) in PARTY.items())}; favorites fight 2x)")
    print(f"  {'':<34}" + "".join(f"{'L' + str(lv):>6}" for lv in LEVELS))
    base = sessions_to_levels(wp.XP_GROWTH, pop, BASE_FIGHTS, args.relic_every)
    for fights in args.fights:
        numbers = base if fights == BASE_FIGHTS else sessions_to_levels(wp.XP_GROWTH, pop, fights, args.relic_every)
        _sessions_row(f"{fights} fights", numbers)
    for growth in args.growth:
        _sessions_row(f"x{growth}, {BASE_FIGHTS} fights", sessions_to_levels(growth, pop, BASE_FIGHTS, args.relic_every))

    even = [table[lv, lv] for lv, foe in MATCHUPS if lv == foe]
    up = [table[lv, foe] for lv, foe in MATCHUPS if foe - lv in (3, 4)]
    actual = {
        "even fights from level 7, no mana: rounds": statistics.mean(r[6] for r in evens if r[0] >= 7),
        "even fights from level 7, burning mana: rounds": statistics.mean(r[2] for r in evens if r[0] >= 7),
        "even fights from level 7, no mana: energy %": statistics.mean(r[7] for r in evens if r[0] >= 7),
        "even fights from level 7, burning mana: energy + mana / 2": statistics.mean(r[3] + r[4] / 2 for r in evens if r[0] >= 7),
        "even fights: lowest win %": min(min(r[1], r[5]) for r in evens),
        "favorite: sessions to level 20": base["favorite", 20],
        "other: sessions to level 20": base["other", 20],
        "other: sessions to level 5": base["other", 5],
        "level 7 moves: most energy saved": plain_cost - mixes[0][2],
        "energy loop: most energy out of a fight (from 20%)": max(r[5] for r in loops),
        "capstones: most energy saved": cap_cost - caps[0][2],
        "level 9 focus: most energy saved": max(c0 - c1 for _, _, c0, _, c1 in nines[:4]),
        "level 9 focus: least energy saved": min(c0 - c1 for _, _, c0, _, c1 in nines[:4]),
        "level 9 upgrade: most energy saved": max(c0 - c1 for _, _, c0, _, c1 in nines[4:]),
        "level 7 moves: least energy saved": plain_cost - mixes[-1][2],
    }
    print(f"\nTargets ({BASE_FIGHTS} fights a session)")
    off = 0
    for name, (low, high) in TARGETS.items():
        good = low <= actual[name] <= high
        off += not good
        print(f"  {'ok ' if good else 'OFF'} {name:<34}{actual[name]:>7.1f}   wanted {low}-{high}")
    print("\nAll on target." if not off else f"\n{off} off target: check that's what you meant, then move the target if so.")
    return 1 if off else 0


if __name__ == "__main__":
    sys.exit(main())
