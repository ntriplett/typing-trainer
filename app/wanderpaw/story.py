"""Wanderpaw's story and things (PLAN.md 11n): the words, not the rules.

Quests (quests.py): each town has two quest-givers, one for each broken
shortcut on its region's borders (NPCS, by town region and the shortcut's
region; SHORTCUTS: a ferry, a tunnel, a footbridge, a ladder, a lift). For
each shortcut, whichever of its two quest-givers you take on first will
mend it (bring back their lost thing and the part waiting on each side);
the other one trains a pet a level for theirs. Towns are full of their
region's animals (HOUSES, INNS, SHOPS).
Lost things hide in a region's pocket or in a nook that takes 3 levels of
a type (FETCH_HINTS). Finishing either quest in a town gets you a rumor of
where the region's temple key is hidden. The temple wants the key and a
pet of its type; inside are the relic, a befriending charm, and an Elder
buff for that type's pets. All five relics open the Heartstone in the
heartland: the end of the story.

Field skills: a gate on a big edge needs its `level` of its type
(world.Gate); FIELD_SKILLS says what they do.

Nooks (local.Nook): what each kind is called and says (NOOKS), and the
words and numbers for what's found in them.
"""

from __future__ import annotations

from dataclasses import dataclass

TYPE_NAMES = {"ember": "Ember", "splash": "Splash", "leaf": "Leaf", "dream": "Dream", "shock": "Shock"}


@dataclass(frozen=True, slots=True)
class RegionStory:
    key: str  # the temple key, hidden in a nook
    relic: str
    buff: str  # what the pet that opens the temple becomes


STORIES = {
    "leaf": RegionStory("Oak Seed", "Evergreen Leaf", "Elder Leaf"),
    "splash": RegionStory("Tide Pearl", "Tide Shell", "Elder Splash"),
    "ember": RegionStory("Sun Ember", "Hearth Flame", "Elder Ember"),
    "dream": RegionStory("Moon Feather", "Moon Opal", "Elder Dream"),
    "shock": RegionStory("Thunder Key", "Storm Feather", "Elder Shock"),
}


@dataclass(frozen=True, slots=True)
class Shortcut:
    """A region's broken shortcut, to the next region around the ring."""

    name: str  # "the old ferry"
    broken: str  # what you see when you walk into it
    parts: tuple[str, str]  # waiting on (this region's side, the next region's side)
    done: str  # once it's mended


SHORTCUTS = {
    "splash": Shortcut("the old ferry", "The old ferry is stuck on the bank. Its line snapped long ago.",
                       ("ferry rope", "raft planks"),
                       "The old ferry is running again! Hop aboard any time."),
    "ember": Shortcut("the cave-in tunnel", "Rocks have fallen across the old tunnel. It's blocked solid.",
                      ("sturdy shovel", "glow moss"),
                      "The old tunnel is clear, and glowing softly all the way through."),
    "dream": Shortcut("the moonlit footbridge", "Only a few silvery threads are left of the moonlit footbridge.",
                      ("moon-silk thread", "willow planks"),
                      "The moonlit footbridge shimmers back into place."),
    "leaf": Shortcut("the vine ladder", "The vine ladder has withered away. The cliff is too steep to climb.",
                     ("vine seeds", "copper pegs"),
                     "The vine ladder curls up the cliff again!"),
    "shock": Shortcut("the cliffside lift", "The cliffside lift hangs dead and still.",
                      ("gear wheel", "pulley rope"),
                      "The cliffside lift whirs to life. Going up!"),
}


@dataclass(frozen=True, slots=True)
class Npc:
    name: str
    species: str
    lost: str  # the thing they lost
    hello: str  # how they greet you
    mend: str  # why they could fix the shortcut
    fix: str  # how they'd fix it: "I could ..."
    train: str  # what they'll teach a pet
    trained: str  # what happens: {npc}, {pet}
    thanks: str


# (town's region, shortcut's region) -> its quest-giver. Each town has one
# for its own region's shortcut and one for the region before it. Towns
# are full of their region's animals.
NPCS = {
    ("splash", "splash"): Npc(
        "Captain Biscuit", "dog", "Lucky Whistle", "Woof! Ahoy there, matey!",
        "My ferry crossed to the Ember lands every day, till the line snapped.",
        "splice a new line and have her sailing by teatime",
        "I'll teach one of your pets to swim against the tide.",
        "{npc} takes {pet} for laps around the bay.", "Best crew a captain ever had!"),
    ("splash", "shock"): Npc(
        "Grandpa Shellby", "turtle", "Reading Glasses", "Oh... hello there... no need to rush...",
        "The cliffside lift? I helped build it, a hundred years ago. It just needs a little love.",
        "oil every gear by hand, nice and slow, till she hums",
        "I'll teach one of your pets my secret: slow and steady.",
        "{npc} and {pet} practice slow, steady breathing for hours.", "Now I can read the paper again. Thank you, young one."),
    ("ember", "ember"): Npc(
        "Ms. Cinders", "fox", "Lantern Wick", "Evening! Or is it morning? I lose track.",
        "I used to light that old tunnel every night. Shame it caved in.",
        "dig out the rocks and hang my lanterns all the way through",
        "I'll teach one of your pets to glow a little brighter.",
        "{npc} shows {pet} how to keep a flame burning.", "The lamps are lit again, all thanks to you!"),
    ("ember", "splash"): Npc(
        "Sunny Scales", "lizard", "Sun Hat", "Ahh. Lovely and warm today, isn't it?",
        "I used to ride the old ferry across to the beaches. Now it just sits there.",
        "patch her up in the sun and sail her across myself",
        "I'll teach one of your pets to soak up the sun. Builds real strength!",
        "{npc} and {pet} bask on a warm rock all afternoon.", "My nose was getting sunburned. You're a hero."),
    ("dream", "dream"): Npc(
        "Lady Lulla", "llama", "Starglass", "Greetings, wanderer. The stars said you would come.",
        "The moonlit footbridge was woven from dreams. It can be woven again.",
        "spin the moonlight back into a bridge, thread by thread",
        "I'll teach one of your pets to dream big.",
        "{npc} hums {pet} a lullaby full of stars.", "Through the Starglass, everything twinkles again."),
    ("dream", "ember"): Npc(
        "Woolsey", "sheep", "Counting Book", "Mmm... oh! Sorry, I was counting... where was I?",
        "That old tunnel? I fell asleep in it once. Very cozy. I'd love to go back.",
        "dig it out... between naps... and make it extra cozy",
        "I'll teach one of your pets the art of the perfect nap.",
        "{npc} and {pet} take the longest, best nap ever.", "One sheep, two sheep... thank you... zzz..."),
    ("leaf", "leaf"): Npc(
        "Nanny Bramble", "goat", "Garden Shears", "Welcome! Mind the turnips.",
        "That vine ladder grew from my grandmother's seeds. I know just how to grow it again.",
        "plant the seeds at the foot of the cliff and sing them up it",
        "I'll teach one of your pets to climb like a mountain goat.",
        "{npc} has {pet} hopping up and down the rocks all day.", "My hedges will be the talk of the town!"),
    ("leaf", "dream"): Npc(
        "Clover Hop", "bunny", "Golden Spindle", "Hi, hi! Come in, come in!",
        "I wove half of that footbridge myself! Moon-silk is tricky, but I know how.",
        "weave it back together, quick as a hop",
        "I'll teach one of your pets to be quick on its feet!",
        "{npc} races {pet} around the meadow a hundred times.", "Spin, spin, spin! Oh, I'm so happy!"),
    ("shock", "shock"): Npc(
        "Professor Whiskers", "cat", "Spark Wrench", "Ah! A visitor! Mind the wires.",
        "I designed that lift, you know. A gear slipped, that's all.",
        "fit a new gear and give her a jolt",
        "I'll teach one of your pets a little science. Very electrifying.",
        "{npc} shows {pet} how to bottle a spark.", "Eureka! My wrench! Now, where was I..."),
    ("shock", "leaf"): Npc(
        "Zip", "snake", "Brass Bell", "Sssay, hello! Got any letters for me?",
        "I used to zip up that vine ladder with the mail. Now I go the long way round. Sssso slow.",
        "wind the vines up the cliff the way only a snake can",
        "I'll teach one of your pets to be lightning quick.",
        "{npc} and {pet} race the whole mail route, twice.", "Ring-a-ding! The mail will be on time again!"),
}

# How a part gets across with a pet of the far side's type.
CARRY = {"splash": "washes", "ember": "flings", "dream": "floats", "leaf": "swings", "shock": "zaps"}

# Who lives in each region's town: houses (a title and what they say), the
# inn, and the shop. The odd mythical neighbor too.
HOUSES = {
    "splash": [("A dog's house", "Woof! Want to play fetch? No? Okay!"),
               ("A turtle's house", "No need to hurry. The river will still be here tomorrow."),
               ("A dog's house", "I buried a bone by the docks. Don't tell anyone."),
               ("The mermaid's pool", "Sometimes I sing to the fish. They never sing back.")],
    "ember": [("A fox's den", "Lantern light is the best light. Everyone knows that."),
              ("A lizard's house", "Find a warm rock and stay a while."),
              ("A fox's den", "Have you seen the rocks glow at night? Like embers!"),
              ("The phoenix's nest", "Every hundred years I nap in the ashes. Very refreshing.")],
    "dream": [("A llama's house", "Have you counted the stars tonight? I got to a thousand."),
              ("A sheep's house", "I dreamed of a giant carrot. It was delicious."),
              ("A sheep's house", "Shh... the whole town naps after lunch."),
              ("The unicorn's stable", "My horn glows when someone tells the truth. Yours is glowing now.")],
    "leaf": [("A bunny's burrow", "Carrots! Do you have carrots?"),
             ("A goat's house", "I'll eat anything. Except broccoli."),
             ("A bunny's burrow", "Every bunny in town has forty cousins. At least."),
             ("The flower fairy's bloom", "Every flower in town has a name. That one's Gerald.")],
    "shock": [("A cat's house", "I'm not napping. I'm thinking with my eyes closed."),
              ("A snake's house", "Sssome say the wind up here can light a lamp."),
              ("A cat's house", "If the bell rings on the hill, a storm is coming."),
              ("The dragon's den", "Don't mind the sparks. I sneeze when I'm happy.")],
}
INNS = {"splash": "The Soggy Paw", "ember": "The Warm Hearth", "dream": "The Sleepy Llama",
        "leaf": "The Carrot Patch", "shock": "The Spark & Sprocket"}
SHOPS = {"splash": "Shellby's Shells", "ember": "Cinder & Sons", "dream": "Moonlight Goods",
         "leaf": "Hop Shop", "shock": "Whisker Works"}

# Where a lost thing is (by where it hides), with {item}, {place}, {type}.
FETCH_HINTS = {
    "dive": "I dropped my {item} into the deep pool in {place}. I'm no swimmer! It takes 3 Splash levels to dive for it.",
    "cave": "I left my {item} deep in the cave in {place}. It's pitch dark in there; it takes 3 Ember levels to light the way.",
    "glade": "My {item} is in the hidden glade in {place}. The vines are thick; it takes 3 Leaf levels to part them.",
    "hole": "My {item} fell down the dark burrow in {place}. It takes 3 Ember levels to see down there.",
    "grotto": "My {item} is somewhere in the misty grotto in {place}. A stone face sleeps across the door; it takes 3 Dream levels to sing it open.",
    "mine": "I dropped my {item} down the old mine in {place}. The lift needs power; it takes 3 Shock levels to start it.",
    "tangle": "My {item} is caught in the thorny vines in {place}. It takes 3 Leaf levels to reach it.",
    "rune": "I left my {item} by the rune stone in {place}. It's sealed by the runes; it takes 3 Dream levels to read them.",
    "ring": "My {item} is inside the mushroom ring in {place}. It takes 3 Dream levels to get in.",
    "machine": "My {item} is stuck in the old machine in {place}. It takes 3 Shock levels to start it up.",
    "pocket": "My {item} rolled off into {place}, behind a gate. Get past it, and it's right there.",
    "ground": "I dropped my {item} somewhere in {place}.",
}
KEY_RUMOR = "Have you heard? They say the {key} is hidden in {place}. {how}"
KEY_HOW = {k: v.split(". ", 1)[-1].replace("{item}", "it") for k, v in FETCH_HINTS.items()}
TRAIN_LEVELS = 1  # what a trainer's thanks is worth

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

# XP for the party's pets (battles bring the most, later).
XP_QUEST = 150  # bringing an elder's lost thing back
XP_TEMPLE = 300
XP_CACHE = 25  # digging up what a clue pointed to
XP_HARD_NOOK = 20  # the first search of a nook that needed type levels

FORD_ENERGY = 2  # wading across
FORD_ENERGY_SWIM = 1  # ... with a swimmer along
SWIM_LEVELS = 1  # Splash levels that make a swimmer

CHEST_COINS = (5, 20)  # + ring from Camp
SHRINE_ENERGY = 15  # at full accuracy, once per shrine per trip
INN_ENERGY = 25  # a warm meal, once per inn per trip
CAMP_ENERGY = 10  # resting by a campfire: once a day, once your energy is half gone
GATE_ENERGY = 2  # using a field skill
FLEE_ENERGY = 2  # running from a battle (your own walking energy)
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
    "grotto": NookWords("Misty grotto", "A doorway in the rock, full of soft purple mist.", "Explore",
                        "A stone face sleeps across the way in. It takes {need} Dream levels to sing it open (you have {have})."),
    "mine": NookWords("Old mine", "An old mine shaft with a rusty lift.", "Ride down",
                      "The lift is dead. It takes {need} Shock levels to power it up (you have {have})."),
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


# --- what things are (the bag) -----------------------------------------------------------


def describe(item: str) -> str:
    """What an item in the bag is for."""
    for (region, _), npc in NPCS.items():
        if item == npc.lost:
            return f"{npc.name} lost this. Bring it back to them in town."
    for region, tale in STORIES.items():
        name = TYPE_NAMES[region]
        if item == tale.key:
            return f"The key to the {name} Temple. The door also wants a {name} pet."
        if item == tale.relic:
            return "One of the five relics. Bring all five to the Heartstone in the middle of the world."
    for shortcut in SHORTCUTS.values():
        for part in shortcut.parts:
            if item.startswith(part):
                return f"Needed to fix {shortcut.name}. Bring it to whoever is fixing it."
    if item in FORAGE.values():
        return "Found while exploring. Notice boards in town pay coins for these."
    if item in FISH.values():
        return "A fish you caught. Someone in town might want it someday."
    return "Something you found on your travels."
