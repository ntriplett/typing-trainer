"""Wanderpaw battles (PLAN.md 11n, phase 5): two of your pets against a
wild creature, one typed move each per round.

The type ring: a move is very strong (x2) against the next type around
the ring (REGIONS order: Splash -> Ember -> Dream -> Leaf -> Shock ->),
strong (x1.5) against the one after, weak (x2/3) and very weak (x1/2)
against the other two. A pet defends with its first type, and so does a
creature; one with a second type hits with whichever does best.

Each round every fighter with energy picks one of six moves (moves()),
typing its word; each slip takes SLIP off its strength, down to FLOOR:
- attack: damage, of its first type;
- attack2: the same in its second type, a move it gets at level 5 in place
  of a grey one (`swaps` on a team member: gave up -> got);
- big: a three-word move that costs BIG_MANA: BIG times the damage, of its
  first type, and it leaves that type's mark on the creature. Big moves go
  first;
- guard: take the hits meant for its partner this round, at GUARD;
- focus: its next move is FOCUS times as strong;
- cheer: its partner's move this round is CHEER times as strong;
- rest: costs REST_COST energy (never its last) for REST_MANA mana (upgraded,
  no cost and REST_PLUS_MANA).
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

At level 7 a pet gets a mix of its two types (MIX_MOVES, by first type then
second; each mythical has its own, MYTHICAL_MOVES), taking any slot. All cost
MIX_MANA. A mix hits with whichever of its types does best and can set off a
combo for either. Its first type says how it behaves: SPLASH weakens the
creature and supports, EMBER is raw power with a catch, DREAM plays tricks,
LEAF outlasts it, SHOCK is fast and hits often.

At level 9 a pet's focus grows stronger on its own (focus_plus: FOCUS_PLUS
says how), and it upgrades one other move (`upgrades`): names get a "+".
At level 11 it gets a 7th slot (`extra`), which a move it gave up comes back
to, and one more upgrade. At level 13 it learns its pair's mix the other way
around (mix2: second type first), taking any slot. Each mythical has its own
for this too (MYTHICAL_REVERSE). At level 15 it learns a third type, with an
upgraded attack in it (attack3), taking any slot. At level 17 an 8th slot holds a
mix with that type (a move id "mix:first:second"). At level 19 it learns any
mix of its three types it doesn't have, taking any slot, and upgrades a move.
At level 21 it chooses a capstone (CAPSTONES, for a pair of its types): a
passive that helps the fighters whenever it's on the party and not fighting
(`bench` in a battle: their keys, the same one never twice).

Marks (MARKS: soaked, glowing, drowsy, static, tangled) last this round
and the next (MARK_ROUNDS). On their own: glowing burns, drowsy may doze
off, tangled acts last and hits softer. A hit on a marked creature can
set off a combo (COMBOS, by mark and the hit's type: 20 of the 25, one
gap in each row and column), which uses up the mark: more damage, lost
turns, weaker hits, burning, or a boost for your pets. Some leave lasting
effects (`effects`: drenched, thorns, confused, burn, popped, doze).

A pet's energy going into a battle is the most it can have in that battle
(`start_energy`, its battle energy), so a fight can't be a refill: gains stop
there, and a percentage is of that. Mana can still go up to its full mana.

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
or "place:mana": given so far}, later: [hits still to land: {who, kind, power,
name, at: round, when}], mirror: a place the next hit bounces off, drainer:
the place a Burning Brambles feeds, boost:
{round, mult, first}, once: {"place:move": True} for moves used, reborn: places
that can still come back today, reborn_used: places that have, coins: paid on a
win, gift_xp: [place, XP] for the save to pay, over: None | "won" | "lost"}.
A step (for playing the round back): {text, who (a team place or "foe"),
act (hit, rest, guard, focus, cheer, mark, heal, blocked, skip, doze, burn),
target, type, damage, gain, big, combo (its name, if one went off), flash
([place, move id]: a passive move to light up), and everyone's
energy and mana after it: foe, pets {place: energy}, mana {place: mana}}.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.wanderpaw import pets as wp
from app.wanderpaw import terms
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
REST_COST = 1  # energy
REST_MANA = 3
REST_PLUS_MANA = 4
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
HEAL_MAX_ENERGY = 3  # ... up to this in a battle
HEAL_MAX_MANA = 3
MARK_MANA = 1
DAREDEVIL = 2.0
DAREDEVIL_COST = 0.04  # of its full energy
GUARDIAN_ROUNDS = 2
GUARD_STRONG = 0.25
# level 9
FOCUS_PLUS_LEVEL = 9
HEAL_PLUS_ENERGY = 2
HEAL_PLUS_MANA = 2
HEAL_PLUS_MAX_ENERGY = 6
HEAL_PLUS_MAX_MANA = 6
MARK_PLUS_ENERGY = 0.05  # of its full energy: it leaves both types' marks
GUARDIAN_PLUS_ROUNDS = 3
GUARDIAN_PLUS_SOFTER = 0.75  # what other types' hits on its partner come to, those rounds
ATTACK_PLUS = 1.3
BIG_PLUS = 2.8
BIG_PLUS_MANA = 5
GUARD_PLUS = 0.25
FOCUS_PLUS = 2.0
CHEER_PLUS = 2.0
MIX_PLUS_MANA = 3


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
    ("soaked", "splash"): Combo("Drenched", "Enemy hits for half, 3 rounds.", effects=(("drenched", 3),)),
    ("soaked", "ember"): Combo("Steam Cloud", "Enemy's next attack misses.", skip=1),
    ("soaked", "dream"): Combo("Bubble Trap", "Enemy loses a turn, and the hit that pops it does more damage.",
                               skip=1, effects=(("popped", 3),)),
    ("soaked", "shock"): Combo("Chain Zap", "Double damage.", mult=2.0),
    ("glowing", "ember"): Combo("Blaze", "Enemy burns twice as hard.", effects=(("burn", 2),)),
    ("glowing", "dream"): Combo("Fever Dream", "Enemy's next attack hits itself.", effects=(("confused", 3),)),
    ("glowing", "shock"): Combo("Flare", "1.75x damage.", mult=1.75),
    ("glowing", "leaf"): Combo("Wildfire", "Enemy burns twice as hard, for longer.", effects=(("burn", 3),)),
    ("drowsy", "splash"): Combo("Sleepy Rain", "Enemy stays Drowsy and dozes for sure.", keep=2,
                                effects=(("doze", 2),)),
    ("drowsy", "dream"): Combo("Fast Asleep", "Enemy loses 2 turns.", skip=2),
    ("drowsy", "shock"): Combo("Rude Awakening", "Double damage.", mult=2.0),
    ("drowsy", "leaf"): Combo("Meadow Nap", "Enemy loses a turn. Both gain 5% {energy}.", skip=1,
                              pets_energy=0.05),
    ("static", "splash"): Combo("Thunderstorm", "Double damage, and Enemy is Soaked.", mult=2.0, mark="soaked"),
    ("static", "ember"): Combo("Sparkler", "1.5x damage, and Enemy is Glowing.", mult=1.5, mark="glowing"),
    ("static", "shock"): Combo("Overcharge", "2.5x damage.", mult=2.5),
    ("static", "leaf"): Combo("Lightning Rod", "Both gain 3 {mana}.", pets_mana=3),
    ("tangled", "splash"): Combo("Thorns", "Enemy hurts itself when it attacks, 3 rounds.",
                                 effects=(("thorns", 3),)),
    ("tangled", "ember"): Combo("Bonfire", "Double damage.", mult=2.0),
    ("tangled", "dream"): Combo("Hammock", "Enemy loses a turn, and the hit that wakes it does more damage.",
                                skip=1, effects=(("popped", 3),)),
    ("tangled", "leaf"): Combo("Rooted", "Enemy loses a turn.", skip=1),
}


MARK_TYPES = {mark: kind for kind, mark in MARKS.items()}
MIX_MANA = 4
ATTACKS = ("attack", "attack2", "attack3")
REVIVE = 0.2  # of its battle energy
MENDING = 0.03  # of each pet's battle energy, each round it lasts
BRAMBLES_BURN = 0.35  # of an even hit, each round ...
BRAMBLES_DRAIN = 0.25  # ... of which the caster drains this much
SCALDED_HITS = 0.75
WISP_SELF_HIT = 0.75
WIRED_STOP = 0.5  # the chance to lose its turn, from a Living Wire or a Poppy Patch


@dataclass(frozen=True, slots=True)
class MixMove:
    name: str
    short: str  # for the battle's cards
    says: str  # all of what it does
    line: str = ""  # for the battle's log
    hit: float = 1.0  # of a plain attack; 0: none
    times: int = 1  # hits (only the first can set off a combo)
    first: bool = False  # goes before everything
    marks: tuple[tuple[str, int], ...] = ()
    effects: tuple[tuple[str, int], ...] = ()
    skip: int = 0  # turns the creature loses
    self_energy: float = 0.0  # of its full energy (a cost if below 0)
    team_energy: float = 0.0
    partner_energy: float = 0.0
    team_mana: int = 0
    later: float = 0.0  # one more hit, this strong ...
    later_when: str = "end"  # ... at the end of this round, or the "start" of the next
    mirror: bool = False
    echo: bool = False  # its partner's attack this round happens twice
    drain: bool = False
    lift: float = 0.0  # both pets' strength next round
    lift_first: bool = False  # ... and they go first
    revive: bool = False
    passive: bool = False  # always on: nothing to type, no cost
    once: bool = False  # once a battle
    coins: bool = False  # bonus coins if this hit wins the battle
    split_drain: float = 0.0  # Both drain this much of the damage, split evenly
    partner_xp: float = 0.0  # of what Partner's level takes
    reborn: bool = False  # the first time today it'd be worn out, it comes back
    safe: int = 0  # rounds neither pet can be hurt


REBORN = 1.0  # of its battle energy: back where it started the fight
GOLDEN_COINS = 5  # + Enemy's level


MIX_MOVES = {
    # SPLASH first: weakens the creature and supports
    ("splash", "ember"): MixMove("Steam Veil", "Enemy's next attack misses.", "Enemy's next attack misses.", "Steam hides everyone!", skip=1),
    ("splash", "dream"): MixMove("Moon Tide", "Both gain 2 {mana}.", "Both gain 2 {mana}.", "The tide brings mana.", team_mana=2),
    ("splash", "leaf"): MixMove("Rain Garden", "Both gain 3% {energy}, 3 rounds.", "Both gain 3% {energy} each round, for 3 rounds.", "A garden grows.", hit=0.5, effects=(("mending", 3),)),
    ("splash", "shock"): MixMove("Riptide Zap", "", "", hit=1.5, marks=(("soaked", MARK_ROUNDS),)),
    # EMBER first: raw power, with a catch
    ("ember", "splash"): MixMove("Scald", "Enemy hits softer.", "Enemy hits 25% softer, this round and next.", hit=1.5, effects=(("scalded", 2),)),
    ("ember", "dream"): MixMove("Will-o'-Wisp", "Enemy may hit itself.", "Enemy's next attack has a 75% chance to hit itself.", "A wisp dances by.", effects=(("wisp", 3),)),
    ("ember", "leaf"): MixMove("Fire Seed", "Hits next round.", "Hits at the start of next round.", "A seed glows in the ground.", hit=0.0, later=3.5, later_when="start"),
    ("ember", "shock"): MixMove("Flashfire", "", "", hit=2.5, first=True, self_energy=-0.08),
    # DREAM first: tricks
    ("dream", "splash"): MixMove("Mirror Pool", "Next hit on you bounces.", "The next hit on you bounces back at Enemy.", "A still pool shines.", hit=0.0, first=True, mirror=True),
    ("dream", "ember"): MixMove("Campfire Tale", "Enemy dozes. Both gain {energy}.", "Enemy dozes on its next turn. Both gain 2% {energy}.", "It's such a cozy story.", hit=0.5, effects=(("doze", 2),), team_energy=0.02),
    ("dream", "leaf"): MixMove("Sleep Spores", "Drowsy just this round.", "Drowsy only lasts this round.", hit=0.5, marks=(("drowsy", 1), ("tangled", MARK_ROUNDS))),
    ("dream", "shock"): MixMove("Deja Vu", "Partner's attack hits twice.", "If Partner attacks this round, it hits twice.", "Haven't we done this before?", hit=0.5, first=True, echo=True),
    # LEAF first: outlasts the creature
    ("leaf", "splash"): MixMove("Spring Shower", "Partner gains 15% {energy}.", "Partner gains 15% {energy}.", hit=0.5, partner_energy=0.15),
    ("leaf", "ember"): MixMove("Burning Brambles", "Burns; you drain a quarter.", "Enemy burns for 3 rounds. You drain a quarter of that damage.", hit=0.5, effects=(("brambles", 3),), drain=True),
    ("leaf", "dream"): MixMove("Poppy Patch", "Enemy may lose its turn.", "For 2 rounds, Enemy has a 50% chance to lose its turn.", effects=(("poppies", 2),)),
    ("leaf", "shock"): MixMove("Living Wire", "Enemy may lose its turn.", "For 2 rounds, Enemy has a 50% chance to lose its turn.", effects=(("wired", 2),)),
    # SHOCK first: fast, with lots of small hits
    ("shock", "splash"): MixMove("Thunder Patter", "Three quick hits.", "Three quick hits.", hit=0.6, times=3),
    ("shock", "ember"): MixMove("Ball Lightning", "Hits again this round.", "Hits again at the end of the round.", first=True, later=0.8),
    ("shock", "dream"): MixMove("Lucid Spark", "Next round: both hit 1.25x.", "Next round both hit 1.25x and Enemy goes last.", first=True, lift=1.25, lift_first=True),
    ("shock", "leaf"): MixMove("Power Sprout", "You gain 5% {energy}.", "You gain 5% {energy}.", self_energy=0.05),
}
MYTHICAL_MOVES = {
    "dragon": MixMove("Stormfire Breath", "", "", hit=2.0, first=True, marks=(("static", MARK_ROUNDS), ("glowing", MARK_ROUNDS))),
    "phoenix": MixMove("Rising Ash", "Revives Partner if out.", "Also revives a worn out Partner with 20% {energy}.", hit=2.0, revive=True),
    "unicorn": MixMove("Rainbow Blessing", "Both gain {energy} {mana}, hit 1.25x.", "Both gain 10% {energy} and 2 {mana}, and hit 1.25x next round.", "A rainbow arcs over your pets!", hit=0.0, team_energy=0.1, team_mana=2, lift=1.25),
    "mermaid": MixMove("Siren Song", "Enemy hits itself next.", "Enemy's next attack hits itself.", "It can't help but listen.", hit=0.5, first=True, marks=(("soaked", MARK_ROUNDS),), effects=(("confused", 3),)),
    "flower_fairy": MixMove("Blooming Circle", "Both gain 3% {energy}, 3 rounds.", "Both gain 3% {energy} each round, for 3 rounds.", "Flowers ring your pets.", marks=(("tangled", 3),), effects=(("mending", 3),)),
}

# Level 13: each mythical's second move of its own, its types the other way around.
MYTHICAL_REVERSE = {
    "dragon": MixMove("Golden Flame", "Bonus coins if it wins.", "If this hit wins the battle, you earn bonus coins.", hit=2.0, coins=True),
    "phoenix": MixMove("Reborn", "Back at full, once a day.", "The first time each day you'd be worn out, you come back with all your battle {energy}.", hit=0.0, passive=True, reborn=True),
    "unicorn": MixMove("Sanctuary", "Both safe. Once a battle.", "Both can't be hurt this round or next. Once a battle.", hit=0.0, first=True, safe=2, once=True),
    "mermaid": MixMove("Undertow", "Both drain half the damage.", "Both drain half of the damage, split evenly.", hit=1.5, first=True, split_drain=0.5),
    "flower_fairy": MixMove("Nectar", "Partner gains {xp}. Once a battle.", "Partner gains 10% of a level's {xp}. Once a battle.", partner_xp=0.1, once=True),
}



@dataclass(frozen=True, slots=True)
class Capstone:
    key: str
    name: str
    says: str


# Level 21: helps the fighters while this pet isn't fighting.
CAPSTONES = {
    ("splash", "ember"): Capstone("steam_curtain", "Steam Curtain", "Enemy's first attack each battle misses."),
    ("splash", "dream"): Capstone("tide_pool", "Tide Pool", "Fighters start each battle with +3 {mana}."),
    ("splash", "leaf"): Capstone("clear_spring", "Clear Spring", "Fighters gain 1 {energy} each round (max 3)."),
    ("splash", "shock"): Capstone("wet_ground", "Wet Ground", "Enemy starts each battle Soaked."),
    ("ember", "splash"): Capstone("hot_spring", "Hot Spring", "Enemy hits 10% softer for the first 2 rounds."),
    ("ember", "dream"): Capstone("fever_heat", "Fever Heat", "Enemy starts each battle Glowing."),
    ("ember", "leaf"): Capstone("dry_tinder", "Dry Tinder", "Burns do 50% more damage."),
    ("ember", "shock"): Capstone("battle_cry", "Battle Cry", "Fighters' hits do 10% more damage."),
    ("dream", "splash"): Capstone("calm_waters", "Calm Waters", "Each fighter's first hit taken each battle is halved."),
    ("dream", "ember"): Capstone("campfire_song", "Campfire Song", "Enemy starts each battle Drowsy."),
    ("dream", "leaf"): Capstone("sweet_dreams", "Sweet Dreams", "Enemy has a 10% chance to lose each turn."),
    ("dream", "shock"): Capstone("second_thought", "Second Thought", "Fighters' attacks have a 10% chance to hit twice."),
    ("leaf", "splash"): Capstone("deep_roots", "Deep Roots", "Fighters take 10% less damage."),
    ("leaf", "ember"): Capstone("thorn_hedge", "Thorn Hedge", "Enemy takes a little damage each time it attacks."),
    ("leaf", "dream"): Capstone("good_company", "Good Company", "Fighters earn 10% more {xp}."),
    ("leaf", "shock"): Capstone("steady_growth", "Steady Growth", "Fighters gain 1 {mana} each round (max 3)."),
    ("shock", "splash"): Capstone("charged_air", "Charged Air", "Enemy starts each battle Static."),
    ("shock", "ember"): Capstone("quick_start", "Quick Start", "Fighters go first in rounds 1 and 2."),
    ("shock", "dream"): Capstone("bright_idea", "Bright Idea", "Fighters' Big and mix moves cost 1 less {mana}."),
    ("shock", "leaf"): Capstone("trail_runner", "Trail Runner", "The first 10 steps each day cost no {energy}."),
}
CAPSTONE_STARTS = {"wet_ground": "soaked", "fever_heat": "glowing", "campfire_song": "drowsy", "charged_air": "static"}
TIDE_POOL_MANA = 3
BENCH_MAX = 3  # energy or mana a round's gain adds up to, in a battle
HOT_SPRING = 0.9
DRY_TINDER = 1.5
BATTLE_CRY = 1.1
CALM_WATERS = 0.5
SWEET_DREAMS = 0.1
SECOND_THOUGHT = 0.1
DEEP_ROOTS = 0.9
THORN_HEDGE = 0.25  # of an even hit
GOOD_COMPANY = 1.1
TRAIL_RUNNER_STEPS = 10
QUICK_START_ROUNDS = 2


def capstone_of(member: dict) -> Capstone | None:
    pair = member.get("capstone")
    return CAPSTONES[tuple(pair.split(":"))] if pair else None


def capstone_pairs(member: dict) -> list[tuple[str, str]]:
    """The pairs of its types: earlier-learned first."""
    kinds = list(member["types"])
    return [(kinds[i], kinds[j]) for i in range(len(kinds)) for j in range(i + 1, len(kinds))]


def bench_keys(team: list[dict], fighters: list[int]) -> list[str]:
    """The capstones helping now, the same one never twice."""
    caps = [capstone_of(m) for i, m in enumerate(team) if i not in fighters]
    return list(dict.fromkeys(c.key for c in caps if c))


def spent_now(b: dict, place: int, member: dict, move: str) -> bool:
    """A passive move that's done all it can for this battle, or a once-a-battle one that's used."""
    if used_up(b, place, member, move):
        return True
    if move == "guardian":
        return b["round"] >= guardian_rounds(member)
    if move == "healer":
        energy, mana = heal_amounts(member)[1], heal_amounts(member)[3]
        healed = b.get("healed") or {}
        return healed.get(f"{place}:energy", 0) >= energy and healed.get(f"{place}:mana", 0) >= mana
    if is_mix(move) and mix_move(member, move).reborn:
        return place in (b.get("reborn_used") or [])
    return False


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


def start(critter, fighters: list[int], bench: list[str] | tuple[str, ...] = ()) -> dict:
    """A battle against `critter` (critters.Critter) with these team places."""
    energy = round(2 * ROUNDS * pet_hit(_even_power(critter.level)) * TYPICAL_ACCURACY)
    return {
        "critter": critter.id, "species": critter.species, "kind": critter.kind, "second": critter.second, "level": critter.level,
        "seed": critter.seed, "energy": energy, "max": energy, "speed": 5 + critter.level,
        "fighters": list(fighters), "marks": {}, "effects": {}, "focus": [], "skip": 0, "round": 0, "log": [],
        "over": None, "bench": list(bench),
    }


def foe_type(b: dict, target: str, blocked: tuple[str, ...] = ()) -> str | None:
    """The creature's type that hits a `target` type hardest (None: `blocked` stops them all)."""
    kinds = [t for t in (b["kind"], b.get("second")) if t and t not in blocked]
    return max(kinds, key=lambda t: (matchup(t, target), -kinds.index(t))) if kinds else None


def own_type(member: dict) -> str:
    return next(iter(member["types"]))


def focus_active(member: dict, focus: str) -> bool:
    """It chose this focus and hasn't since given up its move for another."""
    move = FOCUS_MOVES[focus]
    return member.get("focus") == focus and (move not in (member.get("swaps") or {}) or move in (member.get("extra") or []))


def focus_plus(member: dict, focus: str) -> bool:
    return focus_active(member, focus) and member.get("level", 0) >= FOCUS_PLUS_LEVEL


def upgraded(member: dict, move: str) -> bool:
    return move in (member.get("upgrades") or [])


def _plus(member: dict, move: str, label: str) -> str:
    """A move's name, with a "+" once it's been upgraded."""
    focus = member.get("focus")
    grown = bool(focus) and focus_plus(member, focus) and (move == FOCUS_MOVES[focus] or (focus == "guardian" and move == "guard"))
    return f"{label}+" if grown or upgraded(member, move) else label


def big_strength(member: dict) -> float:
    return BIG_PLUS if upgraded(member, "big") else BIG


def big_mana(member: dict) -> int:
    return (BIG_PLUS_MANA if upgraded(member, "big") else BIG_MANA) - (1 if member.get("bright") else 0)


def mix_mana(member: dict, move: str = "mix") -> int:
    return (MIX_PLUS_MANA if upgraded(member, move) else MIX_MANA) - (1 if member.get("bright") else 0)


def attack_strength(member: dict, move: str) -> float:
    return ATTACK_PLUS if move in ATTACKS and upgraded(member, move) else 1.0


def focus_strength(member: dict) -> float:
    return FOCUS_PLUS if upgraded(member, "focus") else FOCUS


def cheer_strength(member: dict) -> float:
    return CHEER_PLUS if upgraded(member, "cheer") else CHEER


def rest_cost(member: dict) -> int:
    return 0 if upgraded(member, "rest") else REST_COST


def rest_mana(member: dict) -> int:
    return REST_PLUS_MANA if upgraded(member, "rest") else REST_MANA


def battle_energy(b: dict, team: list[dict], i: int) -> int:
    """The most a pet can have in this battle: what it came in with."""
    return (b.get("start_energy") or {}).get(str(i), team[i]["energy"])


def _gain(b: dict, team: list[dict], energy: list[int], i: int, amount: int) -> int:
    """Energy back, never past its battle energy. How much it really got."""
    before = energy[i]
    energy[i] = min(battle_energy(b, team, i), before + amount)
    return max(0, energy[i] - before)


def _share(b: dict, team: list[dict], i: int, fraction: float) -> int:
    """A percentage gain: of its battle energy."""
    return round(battle_energy(b, team, i) * fraction)


def guard_share(member: dict, kind: str | None) -> float:
    """Of a hit it takes for its partner."""
    if focus_plus(member, "guardian") or (member.get("focus") == "guardian" and kind == beaten_by(own_type(member))):
        return GUARD_STRONG
    return GUARD_PLUS if upgraded(member, "guard") else GUARD


def guardian_rounds(member: dict) -> int:
    return GUARDIAN_PLUS_ROUNDS if focus_plus(member, "guardian") else GUARDIAN_ROUNDS


def mark_kinds(member: dict) -> list[str]:
    """The types whose marks an Elementalist's move leaves."""
    return list(member["types"])[:2] if focus_plus(member, "elementalist") else [own_type(member)]


def mark_energy(member: dict) -> int:
    return max(1, round(member["energy"] * MARK_PLUS_ENERGY)) if focus_plus(member, "elementalist") else 0


def heal_amounts(member: dict) -> tuple[int, int, int, int]:
    """Energy a round, the most energy a battle, mana a round, the most mana a battle."""
    if focus_plus(member, "healer"):
        return HEAL_PLUS_ENERGY, HEAL_PLUS_MAX_ENERGY, HEAL_PLUS_MANA, HEAL_PLUS_MAX_MANA
    return HEAL_ENERGY, HEAL_MAX_ENERGY, HEAL_MANA, HEAL_MAX_MANA




def strong_against(kind: str) -> tuple[str, str]:
    i = wd.REGIONS.index(kind)
    return wd.REGIONS[(i + 1) % len(wd.REGIONS)], wd.REGIONS[(i + 2) % len(wd.REGIONS)]


def beaten_by(kind: str) -> str:
    return wd.REGIONS[wd.REGIONS.index(kind) - 1]


def _doubles(member: dict, kind: str) -> bool:
    return focus_active(member, "daredevil") and (kind == own_type(member) or focus_plus(member, "daredevil"))


def described_moves(member: dict, mana: int | None = None) -> list[dict]:
    """A fighter's six moves away from any battle, saying just what each does."""
    own = own_type(member)
    a, b = (wd.tw(t) for t in strong_against(own))
    guard = f"Takes Partner's hits this round at {guard_share(member, None):.0%}."
    heal_e, heal_max_e, heal_m, heal_max_m = heal_amounts(member)
    says = {
        "attack": (f"{wd.tw(own)} attack", ""),
        "attack2": (None, ""),
        "attack3": (None, ""),
        **{move: (None, mix_move(member, move).says) for move in learned_mixes(member)},
        "big": (f"Big {wd.tw(own)}", ""),
        "guard": ("Guard", guard),
        "focus": ("Focus", f"Your next move is {focus_strength(member)}x."),
        "cheer": ("Cheer", f"Partner's move this round is {cheer_strength(member)}x."),
        "rest": ("Rest", f"Gain {rest_mana(member)} {{mana}}."),
        "healer": (None, f"Each round, Partner gains {heal_e} {{energy}} (max {heal_max_e}) and {heal_m} {{mana}} (max {heal_max_m})."),
        "mark": (None, ""),
        "daredevil": (None, f"{'All' if focus_plus(member, 'daredevil') else wd.tw(own)} hits 2x, but cost {{energy}}."),
        "guardian": (None, f"For {guardian_rounds(member)} rounds, {a} and {b} can't hurt Partner"
                           + (f", and other types hit Partner {1 - GUARDIAN_PLUS_SOFTER:.0%} softer." if focus_plus(member, "guardian") else ".")),
    }
    if focus_plus(member, "guardian"):
        says["guard"] = (GUARD_NAMES[own], guard)
    elif member.get("focus") == "guardian":
        says["guard"] = (GUARD_NAMES[own], f"{guard} {GUARD_STRONG:.0%} from {wd.tw(beaten_by(own))}.")
    out = []
    for m in moves(member, None, mana):
        label, note = says[m["id"]]
        out.append({**m, "label": _plus(member, m["id"], label) if label else m["label"], "note": note})
    return out


def move_catalog() -> list[dict]:
    """Every move tile there is, in groups, for the move lab: each with how
    it looks in the party book and level-ups (party) and in battle (battle)."""
    def pet(first: str, second: str | None = None, level: int = 7, species: str | None = None, **rest) -> dict:
        base = wp.starter(first, level)
        kinds = {first: level, **({second: max(1, level - 4)} if second else {})}
        return {**base, "types": kinds, **({"species": species} if species else {}), **rest}

    def tile(member: dict, move: str, name: str) -> dict:
        party = next(m for m in described_moves(member) if m["id"] == move)
        battle = next(m for m in moves(member, "dream") if m["id"] == move)
        return {"name": name, "party": party, "battle": battle}

    def both(make, move: str, name: str) -> list[dict]:
        """A move as it is, and with its "+"."""
        return [tile(make(False), move, name), tile(make(True), move, f"{name}+")]

    groups = {"Attacks": [], "Big moves": [], "Grey moves": [], "Daredevil's doubled attacks": [], "Guardian's Guard": [],
              "Focus moves": [], "Mixes": [], "Mythical mixes": []}
    for t in wd.REGIONS:
        groups["Attacks"] += both(lambda plus, t=t: pet(t, upgrades=["attack"] if plus else []), "attack", t.title())
        groups["Big moves"] += both(lambda plus, t=t: pet(t, upgrades=["big"] if plus else []), "big", t.title())
        doubled = pet(t, "leaf" if t != "leaf" else "ember", focus="daredevil")
        groups["Daredevil's doubled attacks"] += [tile(doubled, "attack", t.title()), tile(doubled, "big", t.title())]
        groups["Guardian's Guard"] += both(lambda plus, t=t: pet(t, level=9 if plus else 7, focus="guardian"), "guard", GUARD_NAMES[t])
        for focus in FOCUSES:
            groups["Focus moves"] += both(lambda plus, t=t, focus=focus: pet(t, level=9 if plus else 7, focus=focus), FOCUS_MOVES[focus], FOCUS_NAMES[t][focus])
    for move in ("guard", "focus", "cheer", "rest"):
        groups["Grey moves"] += both(lambda plus, move=move: pet("ember", upgrades=[move] if plus else []), move, move.title())
    for (first, second), mix in MIX_MOVES.items():
        groups["Mixes"] += both(lambda plus, f=first, s=second: pet(f, s, swaps={"rest": "mix"}, upgrades=["mix"] if plus else []), "mix", mix.name)
    for species, mix in MYTHICAL_MOVES.items():
        first, second = wp.SPECIES_TYPES[species]
        groups["Mythical mixes"] += both(lambda plus, f=first, s=second, sp=species: pet(f, s, species=sp, swaps={"rest": "mix"}, upgrades=["mix"] if plus else []), "mix", mix.name)
    for species, mix in MYTHICAL_REVERSE.items():
        first, second = wp.SPECIES_TYPES[species]
        groups["Mythical mixes"] += both(lambda plus, f=first, s=second, sp=species: pet(f, s, species=sp, swaps={"rest": "mix2"}, upgrades=["mix2"] if plus and not mix.passive else []), "mix2", mix.name)
    groups["Capstones"] = []
    for (first, second), cap in CAPSTONES.items():
        card = {"id": "capstone", "type": first, "type2": second, "label": cap.name, "note": cap.says, "icons": {"cost": {}}}
        groups["Capstones"].append({"name": cap.name, "party": card, "battle": card})
    return [{"name": name, "tiles": tiles} for name, tiles in groups.items()]


def _daredevil_cost(member: dict) -> int:
    return max(1, round(member["energy"] * DAREDEVIL_COST))


def focus_option(member: dict, focus: str, mana: int | None = None) -> dict:
    """A focus as a choice: its card, what it replaces, and the six moves it would make."""
    preview = described_moves({**member, "focus": focus}, mana)
    card = next(m for m in preview if m["id"] == FOCUS_MOVES[focus])
    replaces = FOCUS_REPLACES[focus].title()
    return {**card, "id": focus, "title": f"{FOCUS_TITLES[focus]} focus", "replaces": replaces,
            "also": "Upgrades Guard too." if focus == "guardian" else None, "moves": preview}


def _strength(m: float) -> str:
    return {2.0: " Super strong!", 1.5: " Strong.", 1.0: "", 2 / 3: " Weak.", 0.5: " Very weak."}[m]


def moves(member: dict, foe: str | None = None, mana: int | None = None) -> list[dict]:
    """A fighter's six moves, each with a short reminder of what it does
    (how strong against a `foe` type, if known) and whether it can (mana)."""
    own = own_type(member)
    strength = _strength(matchup(own, foe)).strip() if foe else ""
    out = [
        {"id": "attack", "type": own, "label": f"{wd.tw(own)} attack", "size": "medium",
         "note": strength},
        {"id": "big", "type": own, "label": f"Big {wd.tw(own)}", "size": "phrase", "cost": big_mana(member),
         "note": strength, "can": mana is None or mana >= big_mana(member)},
        {"id": "guard", "type": None, "label": "Guard", "size": "short", "note": f"Takes Partner's hits at {guard_share(member, None):.0%}."},
        {"id": "focus", "type": None, "label": "Focus", "size": "short", "note": f"Your next move: {focus_strength(member)}x."},
        {"id": "cheer", "type": None, "label": "Cheer", "size": "short", "note": f"Partner's move: {cheer_strength(member)}x."},
        {"id": "rest", "type": None, "label": "Rest", "size": "short", "note": f"Gain {rest_mana(member)} {{mana}}."},
    ]
    focused = _with_focus(out, member, mana)
    done = _with_swaps(focused, member, foe, mana)
    if member.get("extra"):
        library = {**{m["id"]: m for m in out}, **{m["id"]: m for m in focused}, **_later_moves(member, foe, mana)}
        done = [*done, *(library[move] for move in member["extra"])]
    return [{**m, "label": _plus(member, m["id"], m["label"]), "icons": move_icons(member, m["id"])} for m in done]


def _dots(strength: float) -> int:
    """How many circles a hit this strong shows: one for each half of a plain attack."""
    return max(1, min(5, round(strength / 0.5)))


def move_icons(member: dict, move: str) -> dict:
    """What a move's card shows as icons: haste, hit (circles for how strong),
    marks, shield and its costs (mana, energy). An icon's tooltip is always the
    same for the same icon (terms.py); more than that goes in the move's text."""
    own = own_type(member)
    kinds = list(member["types"])
    second = kinds[1] if len(kinds) > 1 else kinds[0]
    icons: dict = {"cost": {}}

    def hit(strength: float, types: list[str]) -> None:
        count = _dots(strength)
        icons["hit"] = {"count": count, "types": types, "tip": terms.damage_tip(count)}

    def marks(*names: str) -> None:
        icons["marks"] = [{"type": MARK_TYPES[n], "tip": terms.mark_tip(n)} for n in names]

    def haste() -> None:
        icons["haste"] = terms.FAST_TIP

    def shield(who: str, types: list[str] | None = None, double: bool = False) -> None:
        """who: "you", "partner" or "both"; double: immunity, not just softer."""
        icons["shield"] = {"types": types or [], "double": double, "who": who, "tip": terms.shield_tip(who, double, types)}

    doubled = lambda kind: DAREDEVIL if _doubles(member, kind) else 1.0  # noqa: E731
    if move in ATTACKS:
        kind = kinds[ATTACKS.index(move)] if ATTACKS.index(move) < len(kinds) else own
        hit(attack_strength(member, move) * doubled(kind), [kind])
        if _doubles(member, kind):
            icons["cost"]["energy"] = _daredevil_cost(member)
    elif move == "big":
        hit(big_strength(member) * doubled(own), [own])
        haste()
        marks(MARKS[own])
        icons["cost"]["mana"] = big_mana(member)
        if _doubles(member, own):
            icons["cost"]["energy"] = _daredevil_cost(member)
    elif move == "rest":
        if rest_cost(member):
            icons["cost"]["energy"] = rest_cost(member)
    elif move == "guard":
        shield("partner", [beaten_by(own)] if member.get("focus") == "guardian" and not focus_plus(member, "guardian") else None)
    elif move == "mark":
        haste()
        marks(*(MARKS[k] for k in mark_kinds(member)))
        icons["cost"]["mana"] = MARK_MANA
        if mark_energy(member):
            icons["cost"]["energy"] = mark_energy(member)
    elif move == "guardian":
        shield("partner", list(strong_against(own)), double=True)
    elif is_mix(move):
        m = mix_move(member, move)
        total = m.hit * m.times + m.later
        if total:
            hit(total, list(mix_pair(member, move)))
        if m.first:
            haste()
        if m.marks:
            marks(*(mark for mark, _ in m.marks))
        if not m.passive:
            icons["cost"]["mana"] = mix_mana(member, move)
        if m.self_energy < 0:
            icons["cost"]["energy"] = round(member["energy"] * -m.self_energy)
        if m.safe:
            shield("both", double=True)
        elif m.mirror:
            shield("you", double=True)
        elif m.skip:
            shield("both", double=True)
        elif any(e == "scalded" for e, _ in m.effects):
            shield("both")
    return icons


def _later_moves(member: dict, foe: str | None, mana: int | None) -> dict[str, dict]:
    """The moves a pet can have learned at later levels."""
    kinds = list(member["types"])
    second = kinds[1] if len(kinds) > 1 else kinds[0]
    strength = _strength(matchup(second, foe)).strip() if foe else ""
    got = {"attack2": {"id": "attack2", "type": second, "label": f"{wd.tw(second)} attack", "size": "medium", "note": strength}}
    if len(kinds) > 2:
        third = _strength(matchup(kinds[2], foe)).strip() if foe else ""
        got["attack3"] = {"id": "attack3", "type": kinds[2], "label": f"{wd.tw(kinds[2])} attack", "size": "medium", "note": third}
    for move in learned_mixes(member):
        got[move] = mix_card(member, mana, move)
    return got


def is_mix(move: str) -> bool:
    return move in ("mix", "mix2") or move.startswith("mix:")


def learned_mixes(member: dict) -> list[str]:
    """The mixes it has picked up, now or before."""
    return [m for m in dict.fromkeys([*(member.get("swaps") or {}).values(), *(member.get("extra") or []), member.get("pending") or ""]) if is_mix(m)]


def mix_pair(member: dict, move: str = "mix") -> tuple[str, str]:
    """The types a mix mixes, first first."""
    if move.startswith("mix:"):
        _, first, second = move.split(":")
        return first, second
    a, b = list(member["types"])[:2]
    return (b, a) if move == "mix2" else (a, b)


def mix_id(pair: tuple[str, str]) -> str:
    return f"mix:{pair[0]}:{pair[1]}"


def mixes_missing(member: dict, with_type: str | None = None) -> list[str]:
    """Mixes of its types it doesn't have right now (only ones `with_type`, if given)."""
    now = {mix_pair(member, m["id"]) for m in moves(member) if is_mix(m["id"])}
    kinds = list(member["types"])
    pairs = [(a, b) for a in kinds for b in kinds if a != b and (not with_type or with_type in (a, b))]
    return [mix_id(p) for p in pairs if p not in now]


def _with_swaps(out: list[dict], member: dict, foe: str | None, mana: int | None = None) -> list[dict]:
    """The six moves with what it got at later levels in the slots they took
    (a slot can change hands more than once)."""
    swaps = member.get("swaps") or {}
    if not swaps:
        return out
    got = _later_moves(member, foe, mana)
    result = []
    for m in out:
        slot = m["id"]
        while slot in swaps:
            slot = swaps[slot]
        result.append(m if slot == m["id"] else got[slot])
    return result


def given_up(member: dict) -> list[str]:
    """The moves it has had and doesn't now, a slot could bring back."""
    focus = member.get("focus")
    ever = [*([FOCUS_REPLACES[focus]] if focus else []), *(member.get("swaps") or {})]
    now = {m["id"] for m in moves(member)}
    return [m for m in dict.fromkeys(ever) if m not in now]


def can_upgrade(member: dict) -> list[dict]:
    """Its moves with no "+" yet (a passive has nothing to make better)."""
    return [m for m in described_moves(member) if _plus(member, m["id"], "") == "" and not m.get("passive")]


def mix_move(member: dict, move: str = "mix") -> MixMove:
    """The mixed move its two types make (a mythical has its own), or, as
    mix2, the one they make the other way around."""
    kinds = list(member["types"])
    if move.startswith("mix:"):
        return MIX_MOVES[mix_pair(member, move)]
    if move == "mix2":
        return MYTHICAL_REVERSE.get(member.get("species")) or MIX_MOVES[kinds[1], kinds[0]]
    return MYTHICAL_MOVES.get(member.get("species")) or MIX_MOVES[kinds[0], kinds[1]]


def mix_card(member: dict, mana: int | None = None, move: str = "mix") -> dict:
    first, second = mix_pair(member, move)
    m = mix_move(member, move)
    card = {"id": move, "type": first, "type2": second, "label": m.name, "size": "long", "cost": mix_mana(member, move),
            "note": m.short, "says": m.says, "can": mana is None or mana >= mix_mana(member, move)}
    return {**card, "passive": True, "cost": 0, "can": True} if m.passive else card


def grey_moves(member: dict) -> list[dict]:
    """The moves still with no type: a new one can replace any of these."""
    return [m for m in described_moves(member) if m["type"] is None]


def _with_focus(out: list[dict], member: dict, mana: int | None) -> list[dict]:
    """The six moves with its focus in: passive ones have no word to type."""
    focus = member.get("focus")
    if not focus:
        return out
    own = own_type(member)
    a, b = (wd.tw(t) for t in strong_against(own))
    card = {
        "healer": {"passive": True, "note": "Partner heals each round."},
        "elementalist": {"size": "short", "cost": MARK_MANA, "note": "", "can": mana is None or mana >= MARK_MANA},
        "daredevil": {"passive": True, "note": f"{'All' if focus_plus(member, 'daredevil') else wd.tw(own)} hits 2x."},
        "guardian": {"passive": True, "note": f"Stops {a} and {b}."},
    }[focus]
    new = {"id": FOCUS_MOVES[focus], "type": own, "label": FOCUS_NAMES[own][focus], **card}
    out = [new if m["id"] == FOCUS_REPLACES[focus] else m for m in out]
    if focus == "guardian":
        out = [{**m, "type": own, "label": GUARD_NAMES[own], "note": f"Takes Partner's hits at {guard_share(member, None):.0%}." if focus_plus(member, "guardian") else f"{GUARD_STRONG:.0%} from {wd.tw(beaten_by(own))}."} if m["id"] == "guard" else m for m in out]
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
    if battle["round"] == 0 and not battle.get("start_energy"):
        battle = {**battle, "start_energy": {str(i): energy[i] for i in battle["fighters"]}}
    b = {**battle, "round": battle["round"] + 1, "log": [], "marks": dict(battle.get("marks", {})),
         "effects": dict(battle.get("effects", {})), "skip": battle.get("skip", 0), "healed": dict(battle.get("healed", {}))}
    bench = b.get("bench") or []
    if b["round"] == 1:
        for key, mark in CAPSTONE_STARTS.items():
            if key in bench:
                b["marks"][mark] = MARK_ROUNDS
        if "steam_curtain" in bench:
            b["skip"] = max(b["skip"], 1)
        if "hot_spring" in bench:
            b["effects"]["hot_spring"] = 2
        if "tide_pool" in bench:
            for i in able:
                mana[i] = min(team[i]["mana"], mana[i] + TIDE_POOL_MANA)
    chosen = {}
    for i, pick in zip(able, picks):
        options = {m["id"]: m for m in moves(team[i], b["kind"], mana[i])}
        if pick["move"] not in options:
            raise ValueError("That's not one of its moves.")
        if options[pick["move"]].get("can") is False:
            raise ValueError("Not enough mana for that.")
        if options[pick["move"]].get("passive"):
            raise ValueError("That one just works: there's nothing to do.")
        if used_up(b, i, team[i], pick["move"]):
            raise ValueError("That can only be used once a battle.")
        chosen[i] = pick
    partner = {i: next((j for j in able if j != i), None) for i in able}
    lift = battle.get("boost") if (battle.get("boost") or {}).get("round") == b["round"] else None
    boost = {i: (focus_strength(team[i]) if i in battle.get("focus", []) else 1.0) * (lift["mult"] if lift else 1.0) for i in able}
    for i, pick in chosen.items():
        if pick["move"] == "cheer" and partner[i] is not None:
            boost[partner[i]] *= cheer_strength(team[i])
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
        early = {"mark": 2000, "big": 1000}.get(chosen[w]["move"], 0)
        if is_mix(chosen[w]["move"]) and mix_move(team[w], chosen[w]["move"]).first:
            early = 2000
        fast = (lift and lift["first"]) or ("quick_start" in bench and b["round"] <= QUICK_START_ROUNDS)
        return team[w]["speed"] + max(early, 1500 if fast else 0)

    order = sorted([*able, "foe"], key=lambda w: -speed(w) + rng.random() * 0.1)
    for entry in _landing(b, team, "start"):
        step(entry)
    echo = None  # a Deja Vu: whose hit this round happens twice
    for who in order:
        if b["energy"] <= 0 or not any(energy[i] > 0 for i in b["fighters"]):
            break
        if who == "foe":
            for entry in _foe_acts(b, team, energy, able, guards, rng):
                step(entry)
            for entry in _reborn(b, team, energy):
                step(entry)
            continue
        if energy[who] <= 0:
            continue
        move = chosen[who]["move"]
        if move in (*ATTACKS, "big"):
            strength = accuracy(chosen[who].get("slips", 0)) * boost[who]
            step(_hit(b, team, who, move, strength, energy, mana))
            if echo == who and b["energy"] > 0:
                step(_hit(b, team, who, move, strength, energy, mana, free=True, again=True))
            if "second_thought" in bench and b["energy"] > 0 and rng.random() < SECOND_THOUGHT:
                step(_hit(b, team, who, move, strength, energy, mana, free=True, again=True))
        elif is_mix(move):
            if _mix(b, team, who, move, accuracy(chosen[who].get("slips", 0)) * boost[who], energy, mana, step):
                echo = partner[who]
        elif move == "mark":
            own = own_type(team[who])
            mana[who] -= MARK_MANA
            energy[who] = max(1, energy[who] - mark_energy(team[who]))
            kinds = mark_kinds(team[who])
            for kind in kinds:
                b["marks"][MARKS[kind]] = MARK_ROUNDS
            step({"who": who, "act": "mark", "target": "foe", "type": own,
                  "text": f"{name(who)}'s {FOCUS_NAMES[own]['elementalist']}: the {foe} is {' and '.join(MARKS[k] for k in kinds)}!"})
        elif move == "rest":
            energy[who] = max(1, energy[who] - rest_cost(team[who]))
            mana[who] = min(team[who]["mana"], mana[who] + rest_mana(team[who]))
            step({"who": who, "act": "rest", "target": who, "text": f"{name(who)} rests: +{rest_mana(team[who])} {{mana}}."})
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
        burn = max(1, round(pet_hit(_even_power(b["level"])) * BURN * hot * (DRY_TINDER if "dry_tinder" in bench else 1)))
        b["energy"] = max(0, b["energy"] - burn)
        step({"who": "foe", "act": "burn", "target": "foe", "type": "ember", "damage": burn, "text": f"The {foe} burns for {burn}."})
    for entry in _landing(b, team, "end"):
        step(entry)
    if b["energy"] > 0 and "brambles" in b["effects"]:
        burn = max(1, round(pet_hit(_even_power(b["level"])) * BRAMBLES_BURN * (DRY_TINDER if "dry_tinder" in bench else 1)))
        b["energy"] = max(0, b["energy"] - burn)
        who = b.get("drainer")
        gain = 0
        if who is not None and energy[who] > 0:
            gain = _gain(b, team, energy, who, max(1, round(burn * BRAMBLES_DRAIN)))
        step({"who": "foe", "act": "burn", "target": "foe", "type": "leaf", "damage": burn,
              "text": f"The brambles burn the {foe} for {burn}." + (f" {name(who)} drains {gain} {{energy}}." if gain else "")})
    if b["energy"] > 0 and "mending" in b["effects"]:
        gains = {}
        for i in b["fighters"]:
            if energy[i] > 0:
                gains[i] = _gain(b, team, energy, i, max(1, _share(b, team, i, MENDING)))
        if any(gains.values()):
            step({"who": next(iter(gains)), "act": "heal", "target": next(iter(gains)), "type": "leaf", "gain": max(gains.values()),
                  "text": "A gentle mending: " + ", ".join(f"{name(i)} +{g}" for i, g in gains.items() if g) + "."})
    for key, what in (("clear_spring", "energy"), ("steady_growth", "mana")):
        if b["energy"] > 0 and key in bench:
            for i in b["fighters"]:
                given = b["healed"].get(f"{key}:{i}", 0)
                if energy[i] > 0 and given < BENCH_MAX:
                    if what == "energy":
                        gain = _gain(b, team, energy, i, 1)
                    else:
                        gain = min(1, team[i]["mana"] - mana[i])
                        mana[i] += gain
                    b["healed"][f"{key}:{i}"] = given + gain
    for i in able:  # healers, once the creature's still standing
        p = partner[i]
        if b["energy"] > 0 and focus_active(team[i], "healer") and p is not None and energy[i] > 0 and energy[p] > 0:
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
    heal_e, heal_max_e, heal_m, heal_max_m = heal_amounts(team[i])
    e = min(heal_e, heal_max_e - given("energy"), battle_energy(b, team, p) - energy[p])
    m = min(heal_m, heal_max_m - given("mana"), team[p]["mana"] - mana[p])
    if e <= 0 and m <= 0:
        return []
    e, m = max(0, e), max(0, m)
    energy[p] += e
    mana[p] += m
    b["healed"][f"{i}:energy"] = given("energy") + e
    b["healed"][f"{i}:mana"] = given("mana") + m
    own = own_type(team[i])
    gains = " and ".join(x for x in (f"+{e} {{energy}}" if e else "", f"+{m} {{mana}}" if m else "") if x)
    return [{"who": i, "act": "heal", "target": p, "type": own, "gain": e or m, "flash": [i, "healer"],
             "text": f"{FOCUS_NAMES[own]['healer']}: {team[p]['name']} {gains}."}]


def _guardian_blocks(b: dict, team: list[dict], energy: list[int], target: int) -> tuple[tuple[str, ...], int | None]:
    """The types a Guardian partner keeps off `target` this round, and which place it is."""
    for i in b["fighters"]:
        if i != target and focus_active(team[i], "guardian") and energy[i] > 0 and b["round"] <= guardian_rounds(team[i]):
            return strong_against(own_type(team[i])), i
    return (), None


def used_up(b: dict, place: int, member: dict, move: str) -> bool:
    """A move that's once a battle, already used in this one."""
    return is_mix(move) and mix_move(member, move).once and f"{place}:{move}" in (b.get("once") or {})


def battle_moves(b: dict, place: int, member: dict, mana: int) -> list[dict]:
    """A fighter's moves right now: a once-a-battle move it's used can't be picked."""
    out = []
    for m in moves(member, b["kind"], mana):
        spent = spent_now(b, place, member, m["id"])
        out.append({**m, "spent": spent, **({"can": False} if spent and not m.get("passive") else {})})
    return out


def has_reborn(member: dict) -> bool:
    return any(is_mix(m["id"]) and mix_move(member, m["id"]).reborn for m in moves(member))


def _reborn(b: dict, team: list[dict], energy: list[int]) -> list[dict]:
    """A pet that can come back, worn out: the first time today, it does."""
    out = []
    for i in list(b.get("reborn") or []):
        if energy[i] <= 0:
            energy[i] = max(1, _share(b, team, i, REBORN))
            b["reborn"] = [p for p in b["reborn"] if p != i]
            b["reborn_used"] = [*(b.get("reborn_used") or []), i]
            kind = list(team[i]["types"])[1]
            out.append({"who": i, "act": "heal", "target": i, "type": kind, "gain": energy[i], "flash": [i, "mix2"],
                        "text": f"Reborn! {team[i]['name']} rises from the ashes."})
    return out


def _landing(b: dict, team: list[dict], when: str) -> list[dict]:
    """Hits from earlier moves that land now (a Fire Seed, a Ball Lightning)."""
    out, waiting = [], []
    for hit in b.get("later") or []:
        if hit["when"] != when or hit["at"] != b["round"]:
            waiting.append(hit)
        elif b["energy"] > 0:
            dmg = max(1, round(hit["power"]))
            b["energy"] = max(0, b["energy"] - dmg)
            out.append({"who": hit["who"], "act": "hit", "target": "foe", "type": hit["kind"], "damage": dmg, "big": True,
                        "text": f"{team[hit['who']]['name']}'s {hit['name']} bursts for {dmg}!"})
    b["later"] = waiting
    return out


def _mix_kind(member: dict, foe_kind: str, move: str = "mix") -> str:
    kinds = list(mix_pair(member, move))
    return max(kinds, key=lambda t: (matchup(t, foe_kind), -kinds.index(t)))


def _mix(b: dict, team: list[dict], who: int, move: str, strength: float, energy: list[int], mana: list[int], step) -> bool:
    """A fighter's mixed move, step by step. True if it's a Deja Vu."""
    me = team[who]
    m = mix_move(me, move)
    mana[who] -= mix_mana(me, move)
    if m.once:
        b["once"] = {**(b.get("once") or {}), f"{who}:{move}": True}
    other = next((j for j in b["fighters"] if j != who), None)
    if m.revive and other is not None and energy[other] <= 0:
        energy[other] = max(1, _share(b, team, other, REVIVE))
        step({"who": who, "act": "heal", "target": other, "type": _mix_kind(me, b["kind"], move), "gain": energy[other],
              "text": f"{me['name']}'s {m.name}: {team[other]['name']} is back on its feet!"})
    if m.hit:
        for n in range(m.times):
            if b["energy"] > 0:
                landed = _hit(b, team, who, move, strength, energy, mana, scale=m.hit, combos=n == 0, tail=m.line if n == 0 else "")
                if m.split_drain:
                    able = [i for i in b["fighters"] if energy[i] > 0]
                    each = round(landed["damage"] * m.split_drain) // len(able)
                    for i in able:
                        _gain(b, team, energy, i, each)
                    landed = {**landed, "text": f"{landed['text']} Both drain {each} {{energy}}."}
                step(landed)
    else:
        step({"who": who, "act": "mix", "target": "foe", "type": _mix_kind(me, b["kind"], move), "text": f"{me['name']}'s {m.name}! {m.line}"})
    if m.coins and b["energy"] <= 0:
        b["coins"] = GOLDEN_COINS + b["level"]
    if m.partner_xp and other is not None and team[other].get("progress"):
        amount = max(1, round(team[other]["progress"][1] * m.partner_xp))
        b["gift_xp"] = [other, amount]
        step({"who": who, "act": "heal", "target": other, "type": _mix_kind(me, b["kind"], move), "text": f"{team[other]['name']} gains {amount} {{xp}}."})
    if m.safe:
        b["effects"]["sanctuary"] = m.safe
    for mark, rounds in m.marks:
        b["marks"][mark] = rounds
    for effect, rounds in m.effects:
        b["effects"][effect] = max(b["effects"].get(effect, 0), rounds)
    b["skip"] = max(b["skip"], m.skip)
    if m.drain:
        b["drainer"] = who
    if m.mirror:
        b["mirror"] = who
    if m.lift:
        b["boost"] = {"round": b["round"] + 1, "mult": m.lift, "first": m.lift_first}
    if m.later:
        power = pet_hit(me["power"]) * matchup(_mix_kind(me, b["kind"], move), b["kind"]) * strength * m.later
        at = b["round"] + (1 if m.later_when == "start" else 0)
        b["later"] = [*(b.get("later") or []), {"who": who, "kind": _mix_kind(me, b["kind"], move), "power": power, "name": m.name, "at": at, "when": m.later_when}]
    if m.self_energy > 0:
        _gain(b, team, energy, who, _share(b, team, who, m.self_energy))
    elif m.self_energy < 0:
        energy[who] = max(1, energy[who] - round(me["energy"] * -m.self_energy))
    for i in b["fighters"]:
        if energy[i] > 0 and (m.team_energy or m.team_mana):
            _gain(b, team, energy, i, _share(b, team, i, m.team_energy))
            mana[i] = min(team[i]["mana"], mana[i] + m.team_mana)
    if m.partner_energy and other is not None and energy[other] > 0:
        _gain(b, team, energy, other, _share(b, team, other, m.partner_energy))
    return m.echo


def _hit(b: dict, team: list[dict], who: int, move: str, strength: float, energy: list[int], mana: list[int],
         free: bool = False, again: bool = False, scale: float = 1.0, combos: bool = True, tail: str = "") -> dict:
    """A fighter's attack, big or mixed move: damage, any combos with the
    marks on it (each uses up its mark), and (a big move) its own mark.
    free: no mana (a Deja Vu's repeat, `again`); scale: of a plain hit; combos:
    whether this one can set any off; tail: a line to add."""
    foe = b["species"]
    mix = is_mix(move)
    kind = _mix_kind(team[who], b["kind"], move) if mix else next(m["type"] for m in moves(team[who], b["kind"]) if m["id"] == move)
    mult = matchup(kind, b["kind"])
    power = pet_hit(team[who]["power"]) * mult * strength * (big_strength(team[who]) if move == "big" else attack_strength(team[who], move)) * scale
    if "battle_cry" in (b.get("bench") or []):
        power *= BATTLE_CRY
    extra, found, flash = "", None, None
    if _doubles(team[who], kind) and not mix:
        power *= DAREDEVIL
        energy[who] = max(1, energy[who] - _daredevil_cost(team[who]))
        extra += f" {FOCUS_NAMES[kind]['daredevil']}: double!"
        flash = [who, "daredevil"]
    if "popped" in b["effects"]:
        power *= POP
        b["effects"].pop("popped")
        extra += " Pop!"
    both = list(mix_pair(team[who], move)) if mix else [kind]
    for mark in list(b["marks"]) if combos else []:
        combo = next((COMBOS[mark, t] for t in [kind, *both] if (mark, t) in COMBOS), None)
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
                _gain(b, team, energy, i, _share(b, team, i, combo.pets_energy))
                mana[i] = min(team[i]["mana"], mana[i] + combo.pets_mana)
        extra += f" {combo.name}!"
    dmg = max(1, round(power))
    b["energy"] = max(0, b["energy"] - dmg)
    if move == "big":
        mana[who] -= 0 if free else big_mana(team[who])
        mark = MARKS[kind]
        b["marks"][mark] = MARK_ROUNDS
        extra += f" The {foe} is {mark}."
    what = mix_move(team[who], move).name if mix else f"big {wd.tw(kind)} move" if move == "big" else f"{wd.tw(kind)} attack"
    if again:
        what = f"{what} happens again and"
    return {"who": who, "act": "hit", "target": "foe", "type": kind, "damage": dmg, "big": move == "big" or (mix and scale >= BIG), "combo": found, "flash": flash,
            "text": f"{team[who]['name']}'s {what} does {dmg}.{_strength(mult)}{extra}{' ' + tail if tail else ''}"}


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
    bench = b.get("bench") or []
    if "sweet_dreams" in bench and rng.random() < SWEET_DREAMS:
        return [{"who": "foe", "act": "doze", "text": f"The {foe} drifts off to sweet dreams."}]
    if "sanctuary" in b["effects"]:
        return [{"who": "foe", "act": "blocked", "target": "foe", "type": b["kind"], "text": f"The {foe} can't get past the sanctuary!"}]
    if "poppies" in b["effects"] and rng.random() < WIRED_STOP:
        return [{"who": "foe", "act": "doze", "text": f"The poppies get to the {foe}. It dozes off..."}]
    if "wired" in b["effects"] and rng.random() < WIRED_STOP:
        return [{"who": "foe", "act": "skip", "text": f"The live wire holds the {foe} still!"}]
    if "wisp" in b["effects"]:
        b["effects"].pop("wisp")
        if rng.random() < WISP_SELF_HIT:
            dmg = max(1, round(even))
            b["energy"] = max(0, b["energy"] - dmg)
            return [{"who": "foe", "act": "hit", "target": "foe", "type": b["kind"], "damage": dmg,
                     "text": f"The {foe} chases the wisp and hits itself for {dmg}!"}]
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
    if b.get("mirror") == i:
        # a Mirror Pool: it bounces straight back
        b["mirror"] = None
        dmg = max(1, round(even))
        b["energy"] = max(0, b["energy"] - dmg)
        return [{"who": "foe", "act": "hit", "target": "foe", "type": kind, "damage": dmg,
                 "text": f"The hit bounces off {m['name']}'s Mirror Pool! The {foe} takes {dmg}."}]
    hit = m["energy"] * share * mult * ratio
    if "scalded" in b["effects"]:
        hit *= SCALDED_HITS
    softer = (HOT_SPRING if "hot_spring" in b["effects"] else 1) * (DEEP_ROOTS if "deep_roots" in bench else 1)
    hit *= softer
    if "calm_waters" in bench and i not in (b.get("calm") or []):
        hit *= CALM_WATERS
        b["calm"] = [*(b.get("calm") or []), i]
    if guardian is not None and focus_plus(team[guardian], "guardian"):
        hit *= GUARDIAN_PLUS_SOFTER
    if i != aim:
        hit *= guard_share(m, kind)
    if "tangled" in b["marks"]:
        hit *= TANGLED_HITS
    if "drenched" in b["effects"]:
        hit *= 0.5
    dmg = max(1, round(hit))
    if softer < 1:  # a small hit shouldn't round the softening away
        dmg = max(1, min(dmg, round(hit / softer) - 1))
    energy[i] = max(0, energy[i] - dmg)
    guarded = f" {m['name']} guards {team[aim]['name']}!" if i != aim else ""
    out = [{"who": "foe", "act": "hit", "target": i, "type": kind, "damage": dmg,
            "text": f"The {foe} hits {m['name']} for {dmg}.{_strength(mult)}{guarded}"}]
    if "thorn_hedge" in bench:
        prick = max(1, round(even * THORN_HEDGE))
        b["energy"] = max(0, b["energy"] - prick)
        out.append({"who": "foe", "act": "burn", "target": "foe", "type": "leaf", "damage": prick,
                    "text": f"The thorn hedge pricks the {foe} for {prick}."})
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
