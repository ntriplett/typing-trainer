"""Wanderpaw's story and things (PLAN.md 11n): the words, not the rules.

Each type region has an elder in its town nearest Camp who lost something
somewhere deep in the region (world.Quest). Bring it back and you get the
key to the region's temple, and the elder's friends repair a shortcut.
The temple wants the key and a pet of its type; inside are the relic, a
befriending charm, and an Elder buff for that type's pets. All five relics
open the Heartstone in the heartland: the end of the story.

Field skills: a gate on a big edge needs `need` pets of its type
(world.Gate); FIELD_SKILLS says what they do.
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
