"""Wanderpaw's town shops: what they sell, and how much of it is left.

Big things are bought with coins from typing practice, which keeps them special
for boss fights. Each of the five towns has one shop, with a flavor of its own
(FLAVORS), plus four things every shop has: EVERY_SHOP. An item is used up or
kept (`keep`); `limit` is how many a shop ever has (None: it always restocks).

Befriending takes two steps. Winning a fight and paying mana brings a creature
to Camp (CAMP_SPOTS at most), where it can stay or be asked to leave. Giving it a
Friendship Token makes it a real pet. Five Tokens in all, one a shop; each shop
gets one more after you beat the game (`RESTOCKED`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Item:
    name: str  # also what the bag calls it
    price: int
    about: str
    when: str  # battle: in a fight; walk: on the trip; any: either; pick: on a pet you choose; auto: works by itself; key: Backspace in a fight
    keep: bool = False  # kept for good, bought once
    limit: int | None = None  # how many a shop ever has


MANA_DROP = "Mana Drop"
FULL_MANA = "Full Mana Potion"
WARD = "Ward Potion"
FEATHER = "Mender's Feather"
TONIC = "Energy Tonic"
CLOAK = "Sneak Cloak"
MAP = "Treasure Map"
SATCHEL = "Forager's Satchel"
ROD = "Fine Fishing Rod"
LUCKY = "Lucky Charm"
BOOTS = "Sturdy Boots"
WAY_HOME = "Way-Home Charm"
TOME = "Type Tome"
WEIGHT = "Training Weight"
TOKEN = "Friendship Token"
DO_OVER = "Do-Over Token"

MANA_DROP_AMOUNT = 10
WARD_SHARE = 0.5  # of a pet's full energy
FEATHER_SHARE = 0.3  # of a pet's full energy
LUCKY_LEVELS = 3  # how far short of a gate it can carry you
BOOTS_WALK = 25
CAMP_SPOTS = 5  # friends waiting at Camp
BEFRIEND_EXTRA_MANA = {"": 0, "tough": 2, "champion": 4}  # on top of the creature's level, for each fighter

# What a sleeping mythical was lying on (once each): one of BIG, a pair of one of PAIRS, and coins per level.
LOOT_BIG = (TOME, WEIGHT)
LOOT_PAIRS = (FULL_MANA, FEATHER, WARD)
LOOT_COINS_PER_LEVEL = 100


def loot(rng, level: int) -> tuple[list[tuple[str, int]], int]:
    """A sleeping mythical's hoard: [(item, how many)], and coins."""
    return [(rng.choice(LOOT_BIG), 1), (rng.choice(LOOT_PAIRS), 2)], LOOT_COINS_PER_LEVEL * level


ITEMS: dict[str, Item] = {
    i.name: i
    for i in [
        Item(MANA_DROP, 500, f"Both fighters gain {MANA_DROP_AMOUNT} {{mana}}.", "any"),
        Item(FULL_MANA, 2000, "Fills both fighters' {mana}.", "any"),
        Item(WARD, 800, "Both fighters get extra {energy} for this battle. It's used up first, and whatever's left fades when the battle ends.", "battle"),
        Item(FEATHER, 1200, "Brings a worn-out fighter back into this battle with some {energy}.", "battle"),
        Item(TONIC, 300, "Refills your own walking {energy}. Your pets' stays as it is.", "walk"),
        Item(CLOAK, 200, "Put it on, and you slip past the next plain creature in your way. Tough ones and guardians still see you.", "walk"),
        Item(MAP, 750, "Marks where a temple's key is hidden.", "walk", limit=2),
        Item(LUCKY, 500, f"Gets you past a gate when you're up to {LUCKY_LEVELS} levels short. It works by itself, once.", "auto"),
        Item(SATCHEL, 1500, "Yours for good: one extra find each time you forage.", "auto", keep=True),
        Item(ROD, 1500, "Yours for good: one extra fish whenever you catch any.", "auto", keep=True),
        Item(BOOTS, 2500, f"Yours for good: {BOOTS_WALK} more walking {{energy}} every trip.", "auto", keep=True),
        Item(WAY_HOME, 2000, "Yours for good: takes you to the very center of Camp, whenever you like.", "walk", keep=True),
        Item(TOME, 2000, "One pet gets a level in one of its types, but not a real level.", "pick", limit=3),
        Item(WEIGHT, 2000, "One pet gets +1 to power, speed, {energy} or {mana}.", "pick", limit=3),
        Item(DO_OVER, 15, "In a battle, press Backspace to let go of the word you're typing and clear its slips, so you can start fresh on any word. Each do-over uses one.", "key"),
        Item(TOKEN, 1000, "Give it to a friend waiting at Camp, and they become one of your pets, ready to join your party and level up.", "auto", limit=1),
    ]
}
STATS = ("power", "speed", "energy", "mana")

EVERY_SHOP = (DO_OVER, TOKEN, TOME, WEIGHT)
FLAVORS = {
    "alchemist": ("Alchemist", (MANA_DROP, FULL_MANA, WARD, FEATHER, TONIC)),
    "outfitter": ("Outfitter", (WAY_HOME, BOOTS, MAP, CLOAK, LUCKY, TONIC)),
    "angler": ("Angler & Forager", (ROD, SATCHEL, MAP, TONIC, MANA_DROP)),
    "general": ("General Store", (MANA_DROP, WARD, TONIC, CLOAK, LUCKY, MAP)),
    "curio": ("Curio Shop", (FEATHER, LUCKY, MAP, CLOAK, WAY_HOME)),
}
SHOP_FLAVOR = {"dream": "alchemist", "ember": "outfitter", "splash": "angler", "leaf": "general", "shock": "curio"}
KEEPERS = {
    "dream": "Bottles clink as the alchemist looks up. \"Mana, mending, a little something for the road?\"",
    "ember": "\"Boots, charms, maps! Everything you need to get there and back,\" says the eldest of the Sons.",
    "splash": "\"Fish biting? They will be,\" says Shellby, not looking up from a tangled net.",
    "leaf": "\"Welcome, welcome! A bit of everything, and a hop away from anywhere,\" says the shopkeeper.",
    "shock": "A cat on the counter blinks at you. \"Odd things for odd jobs,\" says the keeper behind it.",
}
RESTOCKED = {TOKEN: 1}  # more of these once you've beaten the game


def limit(item: Item, finished: bool) -> int | None:
    if item.limit is None:
        return None
    return item.limit + (RESTOCKED.get(item.name, 0) if finished else 0)


def stock(region: str, bought: dict, owned: dict, finished: bool) -> list[dict]:
    """A shop's shelves. bought: what you've had from this shop; owned: your bag."""
    _, goods = FLAVORS[SHOP_FLAVOR[region]]
    out = []
    for name in (*goods, *EVERY_SHOP):
        item = ITEMS[name]
        most = limit(item, finished)
        left = None if most is None else max(0, most - bought.get(name, 0))
        out.append({"name": name, "price": item.price, "about": item.about, "left": left, "keep": item.keep,
                    "owned": owned.get(name, 0), "sold_out": left == 0 or (item.keep and owned.get(name, 0) > 0)})
    return out
