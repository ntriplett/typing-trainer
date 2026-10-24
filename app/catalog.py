"""Every store item (PLAN.md Sections 11c / 11c-2). Rules for buying and
using them live in app/store.py; drawings live in web/static/js/sprites.js,
keyed by the same ids.

`slot` is either a wearable avatar slot (see WEARABLE_SLOTS) or a
non-wearable kind of thing to buy (hair dye, ...). `group` is for store
shelving (e.g. which family of places an item belongs to).

Prices: ~1K coins per 15-minute session and ~100K over ~3 months, so
small things cost a few hundred and big things a few thousand.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.appearance import DYE_HAIR_COLORS, dye_item_id

# Draw order, back to front -- the front-end avatar renderer layers in
# this same order.
WEARABLE_SLOTS = ("background", "shoes", "pants", "shirt", "hat", "pet")
OTHER_KINDS = ("hair_dye", "night")


@dataclass(frozen=True, slots=True)
class StoreItem:
    id: str
    name: str
    slot: str
    price: int
    description: str
    starter: bool = False
    group: str = ""


# Place groups, for store shelving and night unlocks.
PLACE_GROUPS: dict[str, tuple[str, ...]] = {
    "forests": ("meadow", "flower_forest", "autumn_forest", "pine_forest", "cherry_grove", "jungle"),
    "water": ("beach", "river", "waterfall", "under_sea", "swamp"),
    "wild": ("desert", "badlands", "tundra", "mushroom_island"),
    "space": ("space", "moon", "mars"),
}
_GROUP_OF_PLACE = {place: group for group, places in PLACE_GROUPS.items() for place in places}


def _place(place: str, name: str, price: int, description: str) -> list[StoreItem]:
    return [StoreItem(
        f"bg_{place}", name, "background", price, description,
        starter=price == 0, group=_GROUP_OF_PLACE[place],
    )]


def place_group(background_item_id: str) -> str | None:
    return _GROUP_OF_PLACE.get(background_item_id.removeprefix("bg_"))


def night_item_id(group: str) -> str:
    return f"night_{group}"


_DYE_NAMES = {
    "blue": "Ocean Blue", "green": "Leafy Green", "pink": "Bubblegum Pink",
    "purple": "Plum Purple", "silver": "Moonbeam Silver", "cherry": "Cherry Red",
}

ITEMS: list[StoreItem] = [
    # starters (free, not shown in the store)
    StoreItem("shirt_tunic", "Cream Tunic", "shirt", 0, "Plain, comfy, and ready for anything.", starter=True),
    StoreItem("pants_trousers", "Brown Trousers", "pants", 0, "Good for climbing and kneeling.", starter=True),
    StoreItem("shoes_boots", "Leather Boots", "shoes", 0, "Sturdy enough for any trail.", starter=True),
    # hats
    StoreItem("hat_straw", "Straw Hat", "hat", 300, "Keeps the sun out of your eyes."),
    StoreItem("hat_acorn", "Acorn Cap", "hat", 600, "Borrowed from a very large acorn."),
    StoreItem("hat_leaf_crown", "Autumn Leaf Crown", "hat", 1200, "Woven from the brightest fall leaves."),
    # shirts
    StoreItem("shirt_sweater", "Pumpkin Sweater", "shirt", 500, "Cozy, orange, and a little bit itchy."),
    # (overalls cover the legs too, so they live in the shirt slot as a full outfit)
    StoreItem("shirt_overalls", "Garden Overalls", "shirt", 900, "Pockets for seeds and snacks."),
    # pets
    StoreItem("pet_hedgehog", "Hedgehog", "pet", 1500, "Small, spiky, and very loyal."),
    StoreItem("pet_fox", "Fox Kit", "pet", 2500, "Curious about everything you type."),
    # places (backgrounds), by group -- each group has a night unlock below
    *_place("meadow", "Sunny Meadow", 0, "Where every journey starts."),
    *_place("flower_forest", "Flower Forest", 900, "Every tree is blooming."),
    *_place("autumn_forest", "Autumn Forest", 800, "Red and gold trees all around."),
    *_place("pine_forest", "Pine Forest", 1200, "Tall pines and the smell of sap."),
    *_place("cherry_grove", "Cherry Grove", 1800, "Pink petals drifting everywhere."),
    *_place("jungle", "Jungle", 2500, "Vines, giant leaves, and hidden things."),
    *_place("beach", "Sandy Beach", 1000, "Warm sand and gentle waves."),
    *_place("river", "Babbling River", 1100, "A cool stream with stepping stones."),
    *_place("waterfall", "Waterfall", 2200, "Mist, rainbows, and a big splash."),
    *_place("under_sea", "Under the Sea", 3500, "Bubbles, seaweed, and curious fish."),
    *_place("swamp", "Misty Swamp", 1500, "Lily pads and croaking frogs."),
    *_place("desert", "Desert", 1300, "Golden dunes and a lonely cactus."),
    *_place("badlands", "Badlands", 2000, "Striped red cliffs as far as you can see."),
    *_place("tundra", "Snowy Tundra", 1600, "Crunchy snow and frosty pines."),
    *_place("mushroom_island", "Mushroom Island", 3000, "Giant mushrooms on a far-off island."),
    *_place("space", "Outer Space", 4000, "Floating among the stars."),
    *_place("moon", "The Moon", 4500, "Craters, dust, and Earth in the sky."),
    *_place("mars", "Mars", 5000, "The red planet, all to yourself."),
    # night unlocks: one per place group
    *[
        StoreItem(f"night_{group}", name, "night", price, desc, group=group)
        for group, (name, price, desc) in {
            "forests": ("Firefly Jar", 3000, "Nighttime for fields and forests, with fireflies."),
            "water": ("Moonlit Tide", 3000, "Nighttime by the water, under a big moon."),
            "wild": ("Desert Stars", 3000, "Nighttime in the wild lands, full of stars."),
            "space": ("Starlight Visor", 3500, "Deep-space night: darker skies, brighter stars."),
        }.items()
    ],
    # hair dyes (unlock colors in the character designer)
    *[
        StoreItem(dye_item_id(c), _DYE_NAMES[c], "hair_dye", 1500, "A splash of color for your hair.")
        for c in DYE_HAIR_COLORS
    ],
]

CATALOG: dict[str, StoreItem] = {item.id: item for item in ITEMS}

DEFAULT_BACKGROUND = "bg_meadow"
# What a slot falls back to when emptied ("take off" puts these back on).
SLOT_DEFAULTS: dict[str, str] = {
    "background": DEFAULT_BACKGROUND,
    "shirt": "shirt_tunic",
    "pants": "pants_trousers",
    "shoes": "shoes_boots",
}
