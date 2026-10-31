"""Wanderpaw's story and things (PLAN.md 11n): the words, not the rules.

Each type region has an elder in its town nearest Camp who lost something
somewhere deep in the region (world.Quest). Bring it back and you get the
key to the region's temple, and the elder's friends repair a shortcut.
The temple wants the key and a pet of its type; inside are the relic, a
befriending charm, and an Elder buff for that type's pets. All five relics
open the Heartstone in the heartland: the end of the story.

Field skills: a gate on a big edge needs GATE_LEVELS[need] levels of its
type (world.Gate); FIELD_SKILLS says what they do.

Nooks (local.Nook): what each kind is called and says (NOOKS), and the
words and numbers for what's found in them.
"""

from __future__ import annotations

from dataclasses import dataclass

TYPE_NAMES = {"ember": "Ember", "splash": "Splash", "leaf": "Leaf", "dream": "Dream", "shock": "Shock"}


@dataclass(frozen=True, slots=True)
class RegionStory:
    elder: str  # "Old Badger"
    lost: str  # the item they lost
    lost_hint: str  # where they think it is
    key: str  # the temple key they give you
    relic: str
    buff: str  # what the pet that opens the temple becomes
    shortcut: str  # what their friends repair


STORIES = {
    "leaf": RegionStory(
        "Old Badger", "Acorn Locket", "I dropped it out past the brambles, I'm sure of it!",
        "Oak Seed", "Evergreen Leaf", "Elder Leaf", "the old rope bridge",
    ),
    "splash": RegionStory(
        "Ferry Otter", "Silver Oar", "The current took it downstream, far from here.",
        "Tide Pearl", "Tide Shell", "Elder Splash", "the stepping-stone ford",
    ),
    "ember": RegionStory(
        "Lamplighter Fox", "Lantern Wick", "I lost it on my rounds, out where the rocks glow.",
        "Sun Ember", "Hearth Flame", "Elder Ember", "the canyon bridge",
    ),
    "dream": RegionStory(
        "Night Owl", "Starglass", "It rolled away into the mist one sleepy night.",
        "Moon Feather", "Moon Opal", "Elder Dream", "the moonlit footbridge",
    ),
    "shock": RegionStory(
        "Bell Goat", "Brass Bell", "The wind blew it off the hill, way up high.",
        "Thunder Key", "Storm Feather", "Elder Shock", "the cliffside ladder",
    ),
}

# What you find at forage spots, by region (refills every trip).
FORAGE = {
    "camp": "clover", "leaf": "acorn", "splash": "river shell", "ember": "warm pebble",
    "dream": "moon petal", "shock": "spark berry",
}

FIELD_SKILLS = {
    # gate kind: (what's in the way, what clearing it looks like)
    "ember": ("A dark tunnel", "lights the way"),
    "splash": ("A brush fire", "puts out the fire"),
    "leaf": ("A wide gap", "grows a vine bridge"),
    "shock": ("An old powered gate", "powers up the gate"),
    "dream": ("A grumpy guardian", "sings it to sleep"),
}

GATE_LEVELS = {1: 3, 2: 8}  # a gate's need (1 or 2) -> the type levels it takes
FORD_ENERGY = 2  # wading across
FORD_ENERGY_SWIM = 1  # ... with a swimmer along
SWIM_LEVELS = 1  # Splash levels that make a swimmer

CHEST_COINS = (5, 20)  # + ring from Camp
SHRINE_ENERGY = 15  # at full accuracy, once per shrine per trip
INN_ENERGY = 25  # a warm meal, once per inn per trip
GATE_ENERGY = 2  # using a field skill
SIDE_QUEST_COUNT = 3
SIDE_QUEST_COINS = 10

SHRINE_LINES = [
    "the wind hums a quiet song over the hills",
    "small steps add up to a long journey",
    "every path is new to someone",
    "listen and the forest will listen back",
    "the moon keeps watch over sleepy travelers",
    "rivers remember every stone they pass",
    "a warm fire waits at the end of the road",
]

HOUSE_LINES = [
    "Lovely weather for wandering, isn't it?",
    "My grandmother says the temples are older than the hills.",
    "If you're tired, a campfire is never far away.",
    "I heard the Heartstone hums when you get close.",
    "Have you tried the forage out past town? Delicious.",
    "Watch out for the gates. Some need two friends to open!",
]

CREDITS = [
    "Wanderpaw",
    "",
    "The five relics are home.",
    "The Heartstone glows, and the whole land hums.",
    "",
    "Thank you for playing!",
]


# --- nooks ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NookWords:
    title: str
    text: str  # what you see
    search: str = "Look around"  # what Enter does
    locked: str = "It needs {need} {type} levels (you have {have})."


NOOKS = {
    "cave": NookWords("Cave", "A cool, quiet cave in the rock.", "Explore",
                      "It's too dark to go deeper. It needs {need} Ember levels to light the way (you have {have})."),
    "tunnel": NookWords("Tunnel", "A long tunnel right through the rock. You can see light at the other end."),
    "glade": NookWords("Hidden glade", "A sunny little clearing, hidden in the trees.", "Look around",
                       "Vines hang thick across the way in. It needs {need} Leaf levels to part them (you have {have})."),
    "fishing": NookWords("Fishing spot", "The water is clear and the fish are jumping."),
    "dive": NookWords("Deep pool", "Something glints far down in the water.", "Dive in",
                      "It's too deep to dive. It needs {need} Splash levels (you have {have})."),
    "buried": NookWords("Buried chest", "A chest corner pokes out of the dirt.", "Dig it up"),
    "lookout": NookWords("Lookout", "A tall rock you can climb to see far away.", "Climb up"),
    "spring": NookWords("Warm spring", "A little spring bubbles up, warm and fresh.", "Take a sip"),
    "ruin": NookWords("Old ruin", "Mossy stones from a house that stood here long ago.", "Search"),
    "nest": NookWords("Big nest", "A huge empty nest, lined with soft feathers.", "Peek in"),
    "berries": NookWords("Berry bushes", "Bushes heavy with ripe berries.", "Pick some"),
    "log": NookWords("Hollow log", "A big hollow log. Something might be inside.", "Reach in"),
    "statue": NookWords("Old statue", "A worn stone statue of a pet you don't know."),
    "traveler": NookWords("A traveler", "A traveler is resting here, happy to chat."),
    "well": NookWords("Old well", "A stone well. The rope still works!", "Pull up the bucket"),
    "rune": NookWords("Rune stone", "A stone covered in sleepy, swirly marks.", "Read the runes",
                      "The runes swim before your eyes. It needs {need} Dream levels to read them (you have {have})."),
    "ring": NookWords("Mushroom ring", "A perfect ring of mushrooms. It hums softly.", "Step inside",
                      "The ring won't let you in. It needs {need} Dream levels (you have {have})."),
    "machine": NookWords("Old machine", "Gears and wires, rusty and still.", "Power it up",
                         "It's dead as a doornail. It needs {need} Shock levels to wake it (you have {have})."),
    "tangle": NookWords("Overgrown nook", "Thorny vines have grown over something.", "Reach in",
                        "The vines are too thick. It needs {need} Leaf levels to part them (you have {have})."),
    "hole": NookWords("Dark burrow", "A deep, dark burrow.", "Crawl in",
                      "It's pitch black inside. It needs {need} Ember levels to light it (you have {have})."),
}
ONCE_FINDS = ("coins", "clue", "view")  # once ever
DAILY_FINDS = ("forage", "energy", "fish")  # once a trip
NOOK_COINS = (5, 15)  # + ring from Camp
CACHE_COINS = (15, 30)  # a buried cache a clue led you to, + ring
NOOK_ENERGY = 10
LOOKOUT_RADIUS = 4

FISH = {"camp": "minnow", "ember": "fire trout", "splash": "silver fish", "leaf": "reed perch",
        "dream": "moon carp", "shock": "zap eel"}
FISH_LINES = [
    "cast the line and wait",
    "a ripple on the water",
    "slow and steady reel",
    "the bobber dips down",
]
CREATURE_LINE = "Something big is curled up asleep in here. Better not wake it yet."
LORE = [
    "Scratched on the wall: the five temples were built by five friends.",
    "An old carving shows pets of every type dancing round a glowing stone.",
    "Faded words: what the river takes, it gives back downstream.",
    "A tiny drawing of a fox with a lantern, lighting the way for others.",
    "Someone wrote: the mist hides the paths only from those in a hurry.",
    "A note says: when the bells ring on the hill, a storm is coming.",
]
TIPS = [
    "\"Wading is slow, but a Splash friend makes it easy.\"",
    "\"Dead ends aren't always empty. Poke around!\"",
    "\"Climb a lookout and the whole land opens up.\"",
    "\"A clue will lead you to treasure. Look for it on your map.\"",
    "\"Five pets of one type can open nearly anything of that type.\"",
]
