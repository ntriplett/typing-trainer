"""Wanderpaw's story (LORE.md): the words Pip and the Keepers say, and their letters.

Nothing here decides anything: save.py holds the rules. A Keeper's lines can't
assume which relics you have, since temples can be done in any order.
"""

from __future__ import annotations

from dataclasses import dataclass


# --- Pip, the retired mail carrier beside Camp ------------------------------------------

PIP = "Pip"
PIP_SPECIES = "goat"
PIP_SEED = 8675309  # his looks

INTRO_PAGES = (
    "Oh! Hello there. I'm Pip. I carried the mail in these parts, a long time ago. I only ever ate the boring ones.",
    "You felt that, didn't you? The Heartstone flickered. It hasn't done that in a hundred years.",
    "Long ago, five friends gave it five relics, and the whole land was happy. Then came the Bad Season. Each friend hurt another by accident.",
    "That very night, they all wrote letters. Then a wizard named Tumble, the last Wanderpaw, set off to carry them. He never arrived.",
    "With no letters, each friend thought the others were still angry. They took their relics home, built temples, and stayed. The stone has been fading ever since.",
    "And this morning, this old bag was sitting by my door. Five sealed letters are inside, with a tag: \"for the next Wanderpaw.\"",
    "It looks like that's you! A Wanderpaw may walk in any land. Find the five Keepers, deliver their letters, and bring the relics home.",
    "It's a long road, and there's no hurry. Let me show you the basics.",
)
BYE_PAGES = (
    "Well done! That creature was only stirred up. A good battle calms them right down.",
    "The land gets wilder the farther you go, so make friends, train your pets, and talk to everyone you meet.",
    "Each temple needs its key, and the townsfolk hear all the rumors. Follow the paths to the nearest town. Your map will fill in as you go.",
    "If you forget anything, I'm right here beside Camp. Off you go, Wanderpaw!",
)

# What Pip says at each step of the tutorial, while you do it.
TUTORIAL_HINTS = {
    "party": "These are the pets coming with you. Up and down look through them, Space adds or takes one off, and Enter sets off.",
    "walk": "See the letters on the ground? Type one to walk there. Try a few steps.",
    "door": "Nicely done! Now walk to my house, right beside the fire. Stand on the door and press Enter to come in.",
    "map": "That's how you go in anywhere. Now press 5 to see your map. Esc closes it.",
    "guide": "Your map fills in as you explore. Now press 6 for the guidebook: it shows which types beat which. Esc closes it.",
    "fight": "Hear that? Something's stirred up, just past my door. Walk up to it by typing its letters.",
    "fighting": "Each pet gets a move. Type the word on a move to pick it. Stuck on what beats what? Press 2 for the guidebook.",
}

PIP_HELLO = "Pip looks up from a pile of old envelopes. \"Well, if it isn't the Wanderpaw! What can I do for you?\""
PIP_DOOR = "\"There you are! Come in, come in. Mind the envelopes.\""
PIP_TALKS = {
    "story": "Tell me the story again",
    "tutorial": "Show me how things work again",
    "next": "What should I do next?",
    "neighbors": "Who else lives around here?",
}
PIP_NEIGHBOR = "\"There's {name}, out in {place}. A real character. Go and say hello. I'll mark it on your map.\""
PIP_NO_NEIGHBORS = "\"You've heard about everyone around here. Out past the heartland, ask the folks in town.\""
PIP_NEXT = (
    "\"Talk to folks in town. They'll have heard where a temple's key is hidden. You'll need a pet of that temple's type too.\"",
    "\"One relic found! Keep at it. I can feel the land stirring, so train up before the next temple.\"",
    "\"Two relics! The creatures out there are getting bolder. Friends and good training will see you through.\"",
    "\"Three! More than halfway. Don't forget the shops have things to help in a big fight.\"",
    "\"Four! Just one more Keeper. I never thought I'd live to see it.\"",
    "\"All five! Take them to the Heartstone, right in the middle of the world. Go on!\"",
)
PIP_ON_KEEPER = {
    "splash": "\"So Nerissa read her letter. She always did feel things deeply.\"",
    "ember": "\"So Solenne finally listened! That's a first.\"",
    "dream": "\"So Lunelle woke up to it all. Good. Good.\"",
    "leaf": "\"So Primrose put down her garden shears long enough to read. I'm glad.\"",
    "shock": "\"So Old Rumble read it. I bet that big old dragon cried.\"",
}


# --- the five Keepers -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Keeper:
    name: str
    from_name: str  # who wrote the letter they get
    letter: tuple[str, ...]  # the lines you type
    refuse: str  # before the fight
    beaten: str  # after it, before the letter
    moved: str  # after hearing the letter
    about: str  # friendly, afterward
    on_friends: str
    on_tumble: str
    keepsake: str
    keepsake_about: str
    kin: str  # the relative who asks to join your Camp
    kin_is: str  # "her little sister"
    kin_asks: str


KEEPERS = {
    "splash": Keeper(
        "Nerissa", "Old Rumble",
        ("My lightning struck your sea.", "I roared when I should have listened.", "It is too quiet up here without you."),
        "\"Go home, little one. If I let go of the Tide Shell, the water rises again. I won't let that happen twice.\"",
        "Nerissa rests on the rocks, breathing hard. \"You're stronger than you look. What's in that old bag?\"",
        "Nerissa wipes her eyes. \"From Old Rumble? He wrote this... that same night? All these years, I thought he hated me.\"",
        "\"I can still hear the sea from here. It's calmer than it used to be. Thank you for that.\"",
        "\"I flooded Solenne's fires. I never meant to. I wonder if they ever forgave me.\"",
        "\"Tumble used to sit right there and tell the worst jokes. We all miss him.\"",
        "Rippling Pearl", "Nerissa's gift. Wading across a ford costs no extra energy.",
        "Coralie", "her little sister",
        "\"Could I come with you? I've never been past the bay!\"",
    ),
    "ember": Keeper(
        "Solenne", "Nerissa",
        ("I never meant to put out your fires.", "The water rose too fast and I was scared.", "Please come home. I miss your light."),
        "\"You've come for the Hearth Flame? I was put out once. I will not be put out twice. Show me what you've got!\"",
        "Solenne lowers their wings, and the fire settles. \"Hm! Not bad. Now, what's that you're carrying?\"",
        "The feathers flicker softly. \"Nerissa wrote this? She was scared? I was so busy being angry, I never asked.\"",
        "\"A fire that burns alone is just a lonely little light. I see that now.\"",
        "\"I scorched Lunelle's glades in my temper. That's the part I can't forget.\"",
        "\"Tumble could walk through my flames without a singe. He had those strange orbs, you know.\"",
        "Warm Ash", "Solenne's gift. Resting by a campfire gives back 15 more energy.",
        "Cinderling", "their young cousin",
        "\"Ooh, you've been outside! Can I come? I promise not to set anything on fire. Probably.\"",
    ),
    "dream": Keeper(
        "Lunelle", "Solenne",
        ("I burned your moonlit glade, and I think of it every day.", "The fire got away from me.", "I would plant it all again if I could."),
        "\"Shh. Everyone is safe while they sleep. Take the Moon Opal, and they'll all wake up to trouble. I can't allow it.\"",
        "Lunelle blinks, wide awake for the first time in years. \"You're very determined. Is that a letter?\"",
        "Lunelle's horn glows softly. \"Solenne thinks of it every day? I've been hiding in dreams, and missed that.\"",
        "\"It's nice to be awake. I'd forgotten how the morning looks.\"",
        "\"My sleep drifted over Primrose's garden. Her flowers stopped opening. I hope she'll let me see them again.\"",
        "\"I dream of Tumble, some nights. He's always holding a tiny light. Isn't that odd?\"",
        "Dream Pillow", "Lunelle's gift. You sleep so well that every day starts with 15 more walking energy.",
        "Starling", "their little cousin",
        "\"I've dreamed of traveling! Is it like the dreams? May I come and see?\"",
    ),
    "leaf": Keeper(
        "Primrose", "Lunelle",
        ("My sleep drifted over your garden.", "I only wanted everyone to rest.", "Your flowers deserve to wake up. I am so sorry."),
        "\"This garden only just grew back, and the Evergreen Leaf keeps it safe. Nobody's taking it. Nobody!\"",
        "Primrose sinks onto a big petal. \"Oh, you're a stubborn one. Well? Why do you keep looking at that bag?\"",
        "Primrose holds very still. \"Lunelle was only trying to help? I've been so cross, for such a long time.\"",
        "\"Have you seen the new buds? They open right up now, every morning.\"",
        "\"My vines choked Old Rumble's machines. He loved those silly things. I should have asked first.\"",
        "\"Tumble brought me seeds from every land. I still have some. I'm saving them for when he comes back.\"",
        "Seed Pouch", "Primrose's gift. Forage spots give you one extra.",
        "Tansy", "her little sister",
        "\"The garden is lovely, but I want to see what's over the hill! May I come along?\"",
    ),
    "shock": Keeper(
        "Old Rumble", "Primrose",
        ("My vines choked your wonderful machines.", "I should have asked first.", "I wish I could hear them hum again."),
        "\"HA! Come for the Storm Feather, have you? They all left, you know. Nobody ever came. So why should I give it up?\"",
        "Old Rumble flops down with a boom. \"Ooof. Nobody's given me a fight like that in a hundred years. What's that bag?\"",
        "Old Rumble sniffs loudly. \"She liked my machines? She called them wonderful? It's just the dust up here, that's all.\"",
        "\"Listen! I fixed the big one. Hear it hum? Sounds better with visitors around.\"",
        "\"My lightning struck Nerissa's sea. I roared at her, too. Old fool, that's me.\"",
        "\"Tumble was the only one who ever beat me at cards. I'd like a rematch.\"",
        "Spark Compass", "Old Rumble's gift. It twitches when you walk into a place with an unopened chest.",
        "Little Grumble", "his nephew",
        "\"Uncle says you're tough. Can I come? I'm nearly as loud as he is!\"",
    ),
}
KEEPSAKES = {k.keepsake: k.keepsake_about for k in KEEPERS.values()}
KEEPER_TALKS = {"about": "How are you?", "friends": "Tell me about your friends", "tumble": "Who was Tumble?"}
LETTER_LABEL = "Read the letter to them"
LETTER_AGAIN = "You've read {done} of {total} lines. {name} is listening."
FAR_RELICS = {
    0: "",
    1: "\"I felt someone lift a relic. The land woke up a little.\"",
    2: "\"I felt two relics lifted. You've been busy.\"",
    3: "\"Three relics, gone from their homes. I feel every one.\"",
    4: "\"Four relics! You're the one. I wasn't sure anyone would ever come.\"",
}
KEEPER_COINS = 1500
KEEPER_XP = 1000
KIN_LEVEL = 13
ASH_ENERGY = 15
PILLOW_WALK = 15
