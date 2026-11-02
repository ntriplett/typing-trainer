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
    "even fight: rounds": (2.5, 3.6),
    "even fight: energy % each": (7, 13),
    "even fight: win %": (90, 100),
    "3-4 levels up: energy % each": (15, 35),
    "favorite: sessions to level 20": (35, 65),  # maxing favorites around the game's end is fine
    "other: sessions to level 20": (65, 130),  # the whole party shouldn't max out with nothing to do
    "other: sessions to level 5": (4, 12),  # the second type should come soon
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
        out.append((lv, pet, total, total / (STEPS_PER_FIGHT + 2 * pet * bt.FAIR_COST)))
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
        "even fight: rounds": statistics.mean(r[1] for r in even),
        "even fight: energy % each": statistics.mean(r[2] for r in even),
        "even fight: win %": min(r[0] for r in even),
        "3-4 levels up: energy % each": statistics.mean(r[2] for r in up),
        "favorite: sessions to level 20": base["favorite", 20],
        "other: sessions to level 20": base["other", 20],
        "other: sessions to level 5": base["other", 5],
        "level 7 moves: most energy saved": plain_cost - mixes[0][2],
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
