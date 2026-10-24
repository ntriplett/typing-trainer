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
OTHER_KINDS = ("hair_dye",)


@dataclass(frozen=True, slots=True)
class StoreItem:
    id: str
    name: str
    slot: str
    price: int
    description: str
    starter: bool = False
    group: str = ""


_DYE_NAMES = {
    "blue": "Ocean Blue", "green": "Leafy Green", "pink": "Bubblegum Pink",
    "purple": "Plum Purple", "silver": "Moonbeam Silver", "cherry": "Cherry Red",
}

ITEMS: list[StoreItem] = [
    # starters (free, not shown in the store)
    StoreItem("bg_meadow", "Sunny Meadow", "background", 0, "Where every journey starts.", starter=True),
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
    # backgrounds
    StoreItem("bg_autumn_forest", "Autumn Forest", "background", 800, "Red and gold trees all around."),
    StoreItem("bg_beach", "Sandy Beach", "background", 1000, "Warm sand and gentle waves."),
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
