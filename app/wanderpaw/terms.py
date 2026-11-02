"""Wanderpaw's game terms: one word for one thing, everywhere the player reads.

New text uses these words and no others for these ideas. Icons' tooltips come
from here and are always the same for the same icon: anything more specific
goes in the move's own text. TERMS could be shown to players later on.

In text, "{ember}" and the like draw a type's name, and {energy}, {mana} and
{xp} draw their icons in place of the word (wander_text.js).

Short is good: say what an icon doesn't, in as few words as it takes.
"""

from __future__ import annotations

TERMS = {
    "You": "The pet using the move. \"Your\" is what's that pet's.",
    "Partner": "The other pet fighting beside you.",
    "Both": "You and Partner.",
    "Enemy": "The wild creature you're fighting.",
    "Gain": "Get energy or mana back, never past the most a pet can have.",
    "Drain": "Take energy from Enemy and gain some of it yourself.",
    "Bounce": "A hit that goes back at Enemy instead of landing on you.",
    "Energy": "What a pet spends on the trip and in battle. Out of it, a pet is worn out.",
    "Mana": "What bigger moves cost. It comes back each day.",
    "XP": "What pets earn toward their next level.",
    "Worn out": "Out of energy: it can't fight until tomorrow.",
    "Round": "Each pet and Enemy acting once.",
    "Fast": "Goes first in the round.",
    "Goes last": "Acts after everyone else in the round.",
    "Damage": "Energy taken off Enemy by a hit: low, medium, high, very high or massive.",
    "Hit": "A move that does damage.",
    "Mark": "What a move leaves on Enemy (Soaked, Glowing, Drowsy, Static or Tangled), for this round and the next.",
    "Combo": "A hit of the right type on a marked Enemy, which uses up the mark.",
    "Burn": "Damage to Enemy at the end of each round.",
    "Doze": "Enemy loses its turn, falling asleep.",
    "Lose a turn": "Enemy doesn't act this round.",
    "Passive": "A move that's always on: it fills a slot, with nothing to type.",
    "Focus": "What a pet specializes in, chosen at level 3.",
    "Mix": "A move mixing a pet's two types, from level 7.",
    "Upgrade": "A stronger version of a move, shown with a +.",
    "Slot": "One of the six places a pet keeps a move.",
}

# The five types. Each is strong against the next two around the ring.
TYPES = {
    "splash": "Water. Strong against {ember} and {dream}.",
    "ember": "Fire. Strong against {dream} and {leaf}.",
    "dream": "Sleep and tricks. Strong against {leaf} and {shock}.",
    "leaf": "Plants. Strong against {shock} and {splash}.",
    "shock": "Lightning. Strong against {splash} and {ember}.",
}

# What a move can leave on Enemy, and what each does on its own. Any can set off a combo.
MARKS = {
    "Soaked": "Wet. Nothing on its own.",
    "Glowing": "Enemy burns at the end of each round.",
    "Drowsy": "Enemy has a 50% chance to doze off.",
    "Static": "Charged up. Nothing on its own.",
    "Tangled": "Enemy goes last and hits 25% softer.",
}

# What else can be going on with Enemy in a battle.
EFFECTS = {
    "Asleep": "Enemy loses its next 2 turns.",
    "Rooted": "Enemy loses its next turn.",
    "Burning": "Enemy burns twice as hard, for a few rounds.",
    "Drenched": "Enemy hits for half, for 3 rounds.",
    "Thorns": "Enemy hurts itself when it attacks, for 3 rounds.",
    "Dizzy": "Enemy's next attack hits itself.",
    "Bubble": "The next hit on Enemy does 1.5x damage.",
    "Sleepy": "Enemy dozes off on its next turn.",
    "Scalded": "Enemy hits 25% softer.",
    "Wired": "Enemy has a 50% chance to lose its turn.",
    "Poppies": "Enemy has a 50% chance to lose its turn.",
    "Brambles": "Enemy burns each round, and the pet that planted them drains half that damage.",
    "Mending": "Both gain 4% energy each round.",
}

# The small map: what each hex is.
TERRAIN = {
    "grass": "Open ground.",
    "flowers": "Open ground, in bloom.",
    "path": "A trail. The easiest walking: one letter a step.",
    "sand": "Open ground by the water.",
    "plaza": "A town's paved square.",
    "court": "The paved floor of a temple or great hall.",
    "bridge": "A way across water.",
    "ford": "Shallow water you can wade across. It costs more energy, unless {splash} helps.",
    "building": "Somewhere in town to go in.",
    "campfire": "Rest here, and start a new day here.",
    "camp": "Home: where it all starts.",
    "temple": "Holds a relic, behind its gate.",
    "stone": "An old stone to look at.",
    "tree": "In the way.",
    "bush": "In the way.",
    "rock": "In the way.",
    "cliff": "In the way.",
    "water": "In the way, without a bridge or a ford.",
    "ocean": "The edge of the world.",
    "colonnade": "The pillars of a great hall.",
    "dark": "A dark tunnel: {ember} lights the way.",
    "flames": "A brush fire: {splash} puts it out.",
    "gap": "A wide gap: {leaf} grows a vine bridge.",
    "old_gate": "An old powered gate: {shock} powers it up.",
    "guardian": "A grumpy guardian: {dream} sings it to sleep.",
    "broken_bridge": "A broken shortcut, until someone in town helps fix it.",
}

# The big map: the land each big hex is.
LANDS = {
    "fields": "Open heartland.", "orchard": "Heartland trees in rows.",
    "meadow": "{leaf}: open grass.", "woods": "{leaf}: patchy forest.", "fern_hollow": "{leaf}: thick, ferny forest.", "deepwood": "{leaf}: deep forest.",
    "brookside": "{splash}: streams to cross.", "marsh": "{splash}: wet ground.", "lakeshore": "{splash}: around a lake.", "isles": "{splash}: islands.",
    "heath": "{ember}: open, rocky land.", "red_rocks": "{ember}: red canyons.", "hot_springs": "{ember}: steaming pools.", "ember_peaks": "{ember}: high mountains.",
    "windy_hills": "{shock}: open, rocky hills.", "mesa": "{shock}: tall flat rocks.", "ridge": "{shock}: long cliffs.", "storm_peaks": "{shock}: high mountains.",
    "glade": "{dream}: open, among trees.", "mushroom_grove": "{dream}: thick with mushrooms.", "mist_vale": "{dream}: misty valleys.", "crystal_hollow": "{dream}: crystal caves.",
}

DAMAGE_WORDS = ("Low", "Medium", "High", "Very high", "Massive")  # by how many circles

FAST_TIP = "Fast: goes first."
MANA_TIP = "Mana cost."
ENERGY_TIP = "Energy cost."


def damage_tip(circles: int) -> str:
    return f"{DAMAGE_WORDS[circles - 1]} damage."


def mark_tip(mark: str) -> str:
    return f"Leaves Enemy {mark.title()}."


def shield_tip(who: str, double: bool, types: list[str] | None = None) -> str:
    """who: you, partner or both; double: can't be hurt at all, not just less."""
    subject = {"you": "You", "partner": "Partner", "both": "Both"}[who]
    plural = who != "partner"
    verb = "can't be hurt" if double else ("take less damage" if plural else "takes less damage")
    source = " or ".join("{" + t + "}" for t in types or [])
    return f"{subject} {verb}{' by ' + source if source and double else ' from ' + source if source else ''}."
