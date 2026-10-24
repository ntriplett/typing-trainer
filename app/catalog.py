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
WEARABLE_SLOTS = ("background", "shoes", "pants", "shirt", "accessory", "hat")
OTHER_KINDS = ("hair_dye", "night", "furniture", "wallpaper", "flooring")


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


def group_places(group: str) -> list[str]:
    """Background item ids in a place group, in catalog order."""
    return [f"bg_{place}" for place in PLACE_GROUPS[group]]


# Clothing colors. Ids must match sprites.js's CLOTH_COLORS (it draws
# them); recolorable items are named "<slot>_<style>_<color>".
COLORS = {
    "red": "Red", "orange": "Orange", "yellow": "Sunny", "green": "Green", "blue": "Blue",
    "navy": "Navy", "purple": "Purple", "pink": "Pink", "brown": "Brown", "black": "Black",
    "white": "White", "tan": "Khaki", "gray": "Gray",
}


def _styles(slot: str, style: str, name: str, price: int, description: str, colors: list[str]) -> list[StoreItem]:
    """One store item per color of a style, grouped so the store shows the
    style once with color swatches."""
    return [
        StoreItem(f"{slot}_{style}_{c}", f"{COLORS[c]} {name}", slot, price, description, group=f"{slot}_{style}")
        for c in colors
    ]


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
    *_styles("hat", "beanie", "Beanie", 300, "Warm ears, with a pom-pom.", ["red", "blue", "green"]),
    *_styles("hat", "cap", "Ball Cap", 300, "For sunny days and ball games.", ["red", "blue"]),
    StoreItem("hat_flower", "Flower Clip", "hat", 250, "A daisy tucked in your hair."),
    StoreItem("hat_bunny", "Bunny Ears", "hat", 600, "Hop hop!"),
    StoreItem("hat_chef", "Chef's Hat", "hat", 700, "Ready to cook up some words."),
    StoreItem("hat_cowboy", "Cowboy Hat", "hat", 900, "Yee-haw!"),
    StoreItem("hat_snorkel", "Snorkel Mask", "hat", 1000, "For peeking at fish."),
    StoreItem("hat_headphones", "Headphones", "hat", 1100, "Your favorite songs, on repeat."),
    StoreItem("hat_pirate", "Pirate Hat", "hat", 1200, "Arr! Treasure ahead."),
    StoreItem("hat_wizard", "Wizard Hat", "hat", 1500, "Covered in tiny stars."),
    StoreItem("hat_top", "Top Hat", "hat", 1500, "Very fancy indeed."),
    StoreItem("hat_astronaut", "Astronaut Helmet", "hat", 4000, "Ready for space."),
    StoreItem("hat_crown", "Royal Crown", "hat", 5000, "For the ruler of the keyboard."),
    # shirts (overalls and dresses cover the legs too, so they live in the
    # shirt slot as full outfits)
    StoreItem("shirt_sweater", "Pumpkin Sweater", "shirt", 500, "Cozy, orange, and a little bit itchy."),
    StoreItem("shirt_overalls", "Garden Overalls", "shirt", 900, "Pockets for seeds and snacks."),
    *_styles("shirt", "tee", "T-Shirt", 300, "Soft, simple, with a little star.", ["red", "blue", "green", "yellow", "purple"]),
    *_styles("shirt", "hoodie", "Hoodie", 700, "A comfy hood and a front pocket.", ["orange", "green", "pink", "navy"]),
    *_styles("shirt", "flannel", "Flannel", 650, "Plaid, warm, and ready for camping.", ["red", "blue", "green"]),
    *_styles("shirt", "dress", "Dress", 800, "Twirly, with a ribbon sash.", ["pink", "blue", "yellow", "purple"]),
    # pants
    *_styles("pants", "trousers", "Trousers", 350, "Good for climbing and kneeling.", ["black", "green"]),
    *_styles("pants", "jeans", "Jeans", 400, "Tough enough for any adventure.", ["blue", "black"]),
    *_styles("pants", "shorts", "Shorts", 300, "For hot summer days.", ["tan", "blue", "red"]),
    *_styles("pants", "skirt", "Skirt", 400, "Swishy and fun.", ["red", "purple", "green"]),
    # shoes
    *_styles("shoes", "boots", "Boots", 300, "Sturdy enough for any trail.", ["black"]),
    *_styles("shoes", "sneakers", "Sneakers", 300, "Fast feet, fast fingers.", ["red", "blue", "white"]),
    *_styles("shoes", "rainboots", "Rain Boots", 350, "Puddles, beware!", ["yellow", "green", "red"]),
    *_styles("shoes", "sandals", "Sandals", 200, "Toes out in the sunshine.", ["brown"]),
    # accessories: worn, or carried in your left hand
    *_styles("accessory", "scarf", "Scarf", 400, "Long, striped, and toasty.", ["red", "green", "blue", "yellow"]),
    *_styles("accessory", "mittens", "Mittens", 250, "Warm hands, happy typing.", ["red", "blue"]),
    StoreItem("accessory_necklace", "Gold Necklace", "accessory", 500, "Shiny!"),
    StoreItem("accessory_ball", "Bouncy Ball", "accessory", 300, "Throw it for your pet!"),
    StoreItem("accessory_flowers", "Flower Bouquet", "accessory", 350, "Freshly picked."),
    StoreItem("accessory_book", "Storybook", "accessory", 400, "Full of adventures."),
    *_styles("accessory", "umbrella", "Umbrella", 600, "Rain or shine.", ["red", "blue"]),
    StoreItem("accessory_net", "Butterfly Net", "accessory", 700, "Catch (and release) bugs."),
    StoreItem("accessory_lantern", "Lantern", "accessory", 800, "A warm glow for dark nights."),
    StoreItem("accessory_watering_can", "Watering Can", "accessory", 900, "Help the garden grow."),
    StoreItem("accessory_fishing_rod", "Fishing Rod", "accessory", 1200, "Gone fishing!"),
    StoreItem("accessory_portal_gun", "Portal Gun", "accessory", 3000, "Blue portal, orange portal..."),
    # (pets are adopted, not bought as items -- see app/pets.py)
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
    # bedroom: wallpaper + flooring (group = "surface"), furniture (group =
    # the zone it goes in: "wall" or "floor"). Drawings: room.js.
    StoreItem("wallpaper_cream", "Cream Stripes", "wallpaper", 0, "Simple and cozy.", starter=True, group="surface"),
    StoreItem("wallpaper_floral", "Flower Wallpaper", "wallpaper", 600, "Tiny flowers everywhere.", group="surface"),
    StoreItem("wallpaper_wood", "Log Cabin Walls", "wallpaper", 800, "Like a cabin in the woods.", group="surface"),
    StoreItem("wallpaper_mint", "Mint Polka Dots", "wallpaper", 500, "Fresh and fun.", group="surface"),
    StoreItem("wallpaper_stars", "Starry Night Walls", "wallpaper", 1200, "Glow-in-the-dark stars.", group="surface"),
    StoreItem("wallpaper_ocean", "Ocean Waves", "wallpaper", 1000, "Swirly blue waves.", group="surface"),
    StoreItem("flooring_planks", "Wood Planks", "flooring", 0, "Warm and creaky.", starter=True, group="surface"),
    StoreItem("flooring_checker", "Checker Tiles", "flooring", 500, "Black and white squares.", group="surface"),
    StoreItem("flooring_carpet", "Green Carpet", "flooring", 600, "Soft like grass.", group="surface"),
    StoreItem("flooring_stone", "Stone Floor", "flooring", 700, "Like a castle.", group="surface"),
    StoreItem("flooring_pink", "Pink Carpet", "flooring", 600, "Fluffy and pink.", group="surface"),
    *[
        StoreItem(f"furniture_bed_{c}", f"{COLORS[c]} Bed", "furniture", 1200, "Sweet dreams!", group="floor")
        for c in ("red", "blue", "green", "purple")
    ],
    StoreItem("furniture_rug_round", "Round Rug", "furniture", 400, "Soft under your feet.", group="floor"),
    StoreItem("furniture_rug_rainbow", "Rainbow Rug", "furniture", 700, "Every color at once.", group="floor"),
    StoreItem("furniture_desk", "Desk", "furniture", 800, "A spot for homework (and typing).", group="floor"),
    StoreItem("furniture_chair", "Chair", "furniture", 300, "Sit up straight!", group="floor"),
    StoreItem("furniture_bookshelf", "Bookshelf", "furniture", 900, "Full of favorite stories.", group="floor"),
    StoreItem("furniture_dresser", "Dresser", "furniture", 900, "Room for all your outfits.", group="floor"),
    StoreItem("furniture_toy_chest", "Toy Chest", "furniture", 600, "Where toys go at bedtime.", group="floor"),
    StoreItem("furniture_lamp", "Floor Lamp", "furniture", 400, "A warm reading light.", group="floor"),
    StoreItem("furniture_plant", "Potted Plant", "furniture", 300, "Water it sometimes!", group="floor"),
    StoreItem("furniture_teddy", "Teddy Bear", "furniture", 350, "A very good listener.", group="floor"),
    StoreItem("furniture_beanbag", "Beanbag", "furniture", 500, "Flop!", group="floor"),
    StoreItem("furniture_pet_bed", "Pet Bed", "furniture", 450, "A comfy spot for your pet.", group="floor"),
    StoreItem("furniture_aquarium", "Aquarium", "furniture", 1800, "Little fish say hi.", group="floor"),
    StoreItem("furniture_rocket", "Toy Rocket", "furniture", 700, "3... 2... 1...", group="floor"),
    StoreItem("furniture_train", "Toy Train", "furniture", 800, "Choo choo!", group="floor"),
    StoreItem("furniture_window", "Window", "furniture", 900, "Looks out on your current place.", group="wall"),
    StoreItem("furniture_poster_star", "Star Poster", "furniture", 250, "You're a star typist!", group="wall"),
    StoreItem("furniture_painting", "Landscape Painting", "furniture", 600, "Hills and a little house.", group="wall"),
    StoreItem("furniture_clock", "Wall Clock", "furniture", 400, "Tick tock.", group="wall"),
    StoreItem("furniture_shelf", "Plant Shelf", "furniture", 500, "Little plants in a row.", group="wall"),
    StoreItem("furniture_lights", "String Lights", "furniture", 700, "Twinkly and warm.", group="wall"),
    StoreItem("furniture_map", "Treasure Map", "furniture", 550, "X marks the spot.", group="wall"),
    StoreItem("furniture_pennant", "Pennant Flag", "furniture", 300, "Go team!", group="wall"),
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
