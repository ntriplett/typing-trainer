"""Pet genes: everything rolled when a pet is adopted (looks, personality,
battle stats). Rules for owning and feeding pets live in app/pets.py; the
drawing lives in web/static/js/pet_render.js, which only needs the
resolved genes (hex colors included), never this module's tables.

Every pet has a `seed`. Each stat group rolls from its own Random seeded
with f"{seed}:{group}", so adding a group later gives existing pets a
stable value for it without changing anything they already rolled
(fill_missing). The third color depends on the colors unlocked at
adoption time, so genes are stored, not re-derived.

Colors: COLORS is the shared pool (90). Unlocked colors are one set per
learner, shared by every species (starting_unlocks(): every species'
starter colors), so a color found on any pet can be picked for any pet.
Each species' families and realism weights (SPECIES_COLORS) only steer
which third colors tend to roll for it; a rolled third color the learner
hadn't unlocked yet unlocks it everywhere.
"""

from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass

GENES_VERSION = 1


@dataclass(frozen=True, slots=True)
class PetColor:
    id: str
    name: str
    hex: str
    family: str


FANCIFUL = {"pink", "purple", "blue", "green", "teal", "fancy"}


def mute(hex_: str, family: str) -> str:
    """The cozy version of a color: natural ones lose some saturation and
    drift toward a middle lightness; fanciful ones become soft pastels."""
    r, g, b = (int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, light, sat = colorsys.rgb_to_hls(r, g, b)
    if family in FANCIFUL:
        sat *= 0.5
        light = light * 0.6 + 0.78 * 0.4
    else:
        sat *= 0.6
        light = light * 0.88 + 0.5 * 0.12
    r, g, b = colorsys.hls_to_rgb(h, light, sat)
    return "#" + "".join(f"{round(c * 255):02x}" for c in (r, g, b))


def _family(family: str, *colors: tuple[str, str]) -> list[PetColor]:
    return [PetColor(name.lower().replace(" ", "_"), name, mute(hex_, family), family) for name, hex_ in colors]


COLORS: dict[str, PetColor] = {
    c.id: c
    for c in [
        # --- the natural ones (55) ---
        *_family("white", ("Snow", "#f6f2ea"), ("Ivory", "#f2ead6"), ("Pearl", "#ece6dc"), ("Chalk", "#dedad2"), ("Frost", "#e6eef2")),
        *_family(
            "cream", ("Cream", "#f0dcb0"), ("Buttercream", "#f4e2a8"), ("Oat", "#e2cfa4"), ("Biscuit", "#d8bc8a"),
            ("Fawn", "#d2b48c"), ("Wheat", "#e6c98a"),
        ),
        *_family(
            "tan", ("Sand", "#c8a874"), ("Camel", "#c09060"), ("Caramel", "#b87a3e"), ("Honey", "#d09a48"),
            ("Tawny", "#b88850"), ("Khaki", "#a89870"),
        ),
        *_family(
            "brown", ("Chestnut", "#8a5a2c"), ("Cocoa", "#6e4a30"), ("Chocolate", "#5a3620"), ("Mahogany", "#6a2e1e"),
            ("Hazel", "#8e6a3a"), ("Walnut", "#5e4228"), ("Cinnamon", "#9a5a30"), ("Umber", "#4e3424"),
        ),
        *_family(
            "orange", ("Orange", "#e0882e"), ("Rust", "#b8582a"), ("Copper", "#c06a34"), ("Ginger", "#d27838"),
            ("Flame", "#e46a28"), ("Apricot", "#f0a868"), ("Marmalade", "#e89a3a"),
        ),
        *_family("red", ("Crimson", "#b8303a"), ("Brick", "#9e3a2a"), ("Cherry", "#c8283a"), ("Auburn", "#8e3a24"), ("Ruby", "#a82848")),
        *_family(
            "gold", ("Golden", "#e0b060"), ("Butter", "#f0d470"), ("Mustard", "#c8a030"), ("Amber", "#d89a28"),
            ("Lemon", "#f4e070"), ("Sunflower", "#f0c030"),
        ),
        *_family(
            "gray", ("Silver", "#b0b0b8"), ("Ash", "#9a9aa4"), ("Slate", "#74747e"), ("Smoke", "#8a8890"),
            ("Pewter", "#6a6e78"), ("Dove", "#c8c6cc"), ("Steel", "#5a6270"),
        ),
        *_family("black", ("Black", "#3a3640"), ("Ink", "#24212a"), ("Charcoal", "#4a4650"), ("Licorice", "#2e2a2a"), ("Raven", "#303040")),
        # --- the fanciful ones (35) ---
        *_family(
            "pink", ("Pink", "#f6c0d6"), ("Rose", "#e890b0"), ("Blush", "#f0b0b0"), ("Bubblegum", "#f080b8"),
            ("Salmon", "#f09880"), ("Peony", "#d86898"),
        ),
        *_family("purple", ("Lilac", "#c8a8e0"), ("Lavender", "#b098d8"), ("Plum", "#7a4a8a"), ("Violet", "#8a58c0"), ("Orchid", "#d088d0")),
        *_family(
            "blue", ("Sky", "#9ac8f0"), ("Powder", "#b8d4ec"), ("Cornflower", "#6890d8"), ("Denim", "#4a6aa0"),
            ("Navy", "#2e3a6a"), ("Periwinkle", "#a0a8f0"), ("Ice", "#d0e8f4"),
        ),
        *_family(
            "green", ("Mint", "#a8e0b8"), ("Sage", "#a0b890"), ("Moss", "#6b8e3a"), ("Lime", "#b8e070"),
            ("Fern", "#4a8a4a"), ("Seafoam", "#8ad0b0"), ("Pistachio", "#c0d890"),
        ),
        *_family("teal", ("Teal", "#3a9a9a"), ("Aqua", "#70d0d8"), ("Turquoise", "#40c0b0"), ("Lagoon", "#2a7a8a"), ("Jade", "#3aa070")),
        *_family("fancy", ("Coral", "#f08068"), ("Peach", "#f8c8a8"), ("Mauve", "#b88aa0"), ("Sunset", "#f07850"), ("Berry", "#9a2a6a")),
    ]
}

NATURAL = 1.0
RARE = 0.08

# species -> {family: realism weight}, and the 3 colors unlocked from the start.
SPECIES_COLORS: dict[str, dict[str, float]] = {
    "cat": {"white": NATURAL, "cream": NATURAL, "orange": NATURAL, "brown": NATURAL, "gray": NATURAL, "black": NATURAL, "pink": RARE, "purple": RARE},
    "dog": {"white": NATURAL, "cream": NATURAL, "tan": NATURAL, "brown": NATURAL, "gold": NATURAL, "gray": NATURAL, "black": NATURAL, "blue": RARE},
    "fox": {"white": NATURAL, "cream": NATURAL, "orange": NATURAL, "red": NATURAL, "gold": NATURAL, "gray": NATURAL, "black": NATURAL, "fancy": RARE},
    "bunny": {"white": NATURAL, "cream": NATURAL, "tan": NATURAL, "brown": NATURAL, "gray": NATURAL, "black": NATURAL, "pink": RARE, "blue": RARE},
    "sheep": {"white": NATURAL, "cream": NATURAL, "gray": NATURAL, "black": NATURAL, "pink": 0.25, "purple": RARE, "blue": RARE, "green": RARE},
    "goat": {"white": NATURAL, "cream": NATURAL, "tan": NATURAL, "brown": NATURAL, "gray": NATURAL, "black": NATURAL, "gold": NATURAL, "green": RARE},
    "llama": {"white": NATURAL, "cream": NATURAL, "tan": NATURAL, "brown": NATURAL, "gray": NATURAL, "black": NATURAL, "red": NATURAL, "teal": RARE},
}

STARTER_COLORS: dict[str, tuple[str, str, str]] = {
    "cat": ("orange", "ash", "black"),
    "dog": ("golden", "chestnut", "snow"),
    "fox": ("flame", "snow", "silver"),
    "bunny": ("snow", "chestnut", "ash"),
    "sheep": ("snow", "cream", "charcoal"),
    "goat": ("snow", "chestnut", "sand"),
    "llama": ("ivory", "cocoa", "sand"),
}

# Pet Battles' element per species (web/static/js/pet_battle.js SPECIES_TYPE).
ELEMENTS = {
    "bunny": "leaf", "goat": "leaf", "sheep": "leaf",
    "fox": "ember", "cat": "ember",
    "dog": "splash", "llama": "splash",
}

# How the coat splits: mostly one color with a highlight, sometimes a mix,
# rarely a third accent color.
COAT_STYLES = {"highlight": 0.65, "mix": 0.27, "accent": 0.08}
PATTERNS = {"patches": 3.0, "spots": 2.0, "belly": 2.0, "stripes": 1.5, "points": 1.0}
# Species with their own pattern odds. Dogs: mostly belly and points coats,
# a husky-style mask now and then, spots for dalmatians, stripes (brindle) rare.
SPECIES_PATTERNS = {
    "dog": {"belly": 3.0, "points": 2.5, "patches": 2.0, "mask": 1.5, "spots": 1.0, "stripes": 0.4},
    # bunnies wear real rabbit patterns (painted in web/static/js/pet_render.js paintBunny)
    "bunny": {"self": 30, "agouti": 20, "broken": 20, "dutch": 12, "himalayan": 10, "tan": 5, "english": 3},
    # foxes wear real fox coats (paintFox)
    "fox": {"red": 40, "cross": 15, "silver": 15, "arctic": 15, "marble": 15},
    # sheep: wool color plus the face and leg markings real breeds have (paintSheep)
    "sheep": {"whiteface": 25, "blackface": 25, "self": 15, "speckled": 12, "jacob": 10, "badger": 8, "valais": 5},
}
EYES = {"#2a1c14": 6.0, "#5c3a1a": 3.0, "#c8861e": 2.0, "#3a7a3a": 1.5, "#3a6ab8": 1.0, "#7a3ab8": 0.2}
# Species with their own eye colors (cats: green, amber, copper, gold, blue).
SPECIES_EYES = {
    "cat": {"#7ab84a": 4.0, "#e0a828": 4.0, "#c8702a": 2.0, "#e8d040": 2.0, "#5a9ae0": 1.0},
    "dog": {"#3a2416": 5.0, "#5c3a1a": 4.0, "#8a5a2a": 2.0, "#c8861e": 1.0, "#6aa0d8": 0.4},
    "bunny": {"#2a1810": 6.0, "#4a2a1a": 3.0, "#5a7aa8": 0.6, "#b03040": 0.3},
    "fox": {"#c8861e": 4.0, "#e0a828": 3.0, "#5c3a1a": 2.0, "#8a5a2a": 1.0},
    "sheep": {"#c8902a": 3.0, "#8a5a2a": 3.0, "#3a2416": 2.0},
    "sheep": {"#c8902a": 3.0, "#8a5a2a": 3.0, "#3a2416": 2.0},
}
ODD_EYES_CHANCE = {"cat": 0.03, "dog": 0.01}  # one eye a different color

# Species drawn as a set of breeds: each pet rolls one, and sometimes is a
# mix that borrows one part (its tail or its ears) from another breed.
BREEDS = {
    "dog": ("classic", "hound", "shiba", "dachshund", "husky"),
    "bunny": ("classic", "front", "dwarf", "sidelop", "holland", "halflop", "wild", "dwarfside"),
    "fox": ("red", "sitting", "kit", "curled"),
    "sheep": ("fluffy", "merino", "ram", "ramfront", "longwool"),
}
MIX_CHANCE = 0.25
MIX_PARTS = {"dog": ("tail", "ears"), "bunny": ("ears",), "fox": ("ears", "head"), "sheep": ("ears", "ramHorns", "tuft")}

# Looks only some species have: name -> (low, high, mode) for a triangular
# roll. Cats lean skinny; a dog's snout length; a bunny's roundness.
SHAPE_EXTRAS = {
    "cat": {"weight": (-1.0, 1.0, -0.5)},
    "dog": {"snout": (-1.0, 1.0, 0.0), "legs": (-1.0, 1.0, 0.0)},
    "bunny": {"weight": (-1.0, 1.0, 0.2)},
    "fox": {"snout": (-1.0, 1.0, 0.0), "legs": (-1.0, 1.0, 0.0)},
    "sheep": {"wool": (-1.0, 1.0, 0.2), "legs": (-1.0, 1.0, 0.0)},
    "sheep": {"wool": (-1.0, 1.0, 0.2), "legs": (-1.0, 1.0, 0.0)},
}
VEGGIES = ("carrot", "tomato", "pepper", "zucchini", "corn", "pumpkin", "peas", "radish", "eggplant", "broccoli")

SPARKLE_CHANCE = 0.02
SPLOTCH_RANGE = (0.65, 1.0)  # below ~0.6 the coat looks too busy
MIN_THIRD_SHARE = 0.04  # less than this folds into the secondary
# How fast a third color's chance falls off with distance from unlocked
# colors (0..1 color distance), and the floor so far colors stay possible.
NEAR_SCALE = 0.18
FAR_FLOOR = 0.04


def starting_unlocks() -> set[str]:
    """A new learner's colors: every species' starters, shared by all species."""
    return {c for starters in STARTER_COLORS.values() for c in starters}


def eligible_colors(species: str) -> list[str]:
    families = SPECIES_COLORS[species]
    return [c.id for c in COLORS.values() if c.family in families]


def realism(species: str, color_id: str) -> float:
    return SPECIES_COLORS[species].get(COLORS[color_id].family, 0.0)


def _rgb(color_id: str) -> tuple[int, int, int]:
    h = COLORS[color_id].hex
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def color_distance(a: str, b: str) -> float:
    """0 (same) .. ~1 (black vs white); 'redmean' weighted RGB."""
    (r1, g1, b1), (r2, g2, b2) = _rgb(a), _rgb(b)
    rmean = (r1 + r2) / 2
    dr, dg, db = r1 - r2, g1 - g2, b1 - b2
    d = math.sqrt((2 + rmean / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rmean) / 256) * db * db)
    return d / 765


def third_color_weights(species: str, unlocked: set[str], exclude: set[str]) -> dict[str, float]:
    """Chance weights for the random third color: realism times closeness
    to something already unlocked (with a floor, so nothing is impossible)."""
    weights = {}
    for c in eligible_colors(species):
        if c in exclude:
            continue
        near = min((color_distance(c, u) for u in unlocked), default=1.0)
        weights[c] = realism(species, c) * max(FAR_FLOOR, math.exp(-near / NEAR_SCALE))
    return weights


def _rng(seed: int, group: str) -> random.Random:
    return random.Random(f"{seed}:{group}")


def _pick(rng: random.Random, weights: dict) -> str:
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def _trait(rng: random.Random) -> float:
    """0..1, bunched toward the middle (most pets are a bit of everything)."""
    return round((rng.random() + rng.random()) / 2, 3)


# --- stat groups: name -> roller(seed, species, ctx). New groups go at the end. ---


def _roll_coat(seed: int, species: str, ctx: dict) -> dict:
    rng = _rng(seed, "coat")
    style = _pick(rng, COAT_STYLES)
    if style == "highlight":  # a main color with a small highlight
        primary = round(rng.uniform(0.78, 0.9), 3)
        secondary, third = round(1 - primary, 3), 0.0
    elif style == "mix":  # more of an even mix of two
        primary = round(rng.uniform(0.5, 0.68), 3)
        secondary, third = round(1 - primary, 3), 0.0
    else:  # rarely, a third accent color
        primary = round(rng.uniform(0.5, 0.68), 3)
        secondary = round(min(rng.uniform(0.15, 0.3), 1 - primary - MIN_THIRD_SHARE), 3)
        third = round(1 - primary - secondary, 3)
    third_color = None
    if third:
        weights = third_color_weights(species, ctx["unlocked"], {ctx["primary"], ctx["secondary"]})
        third_color = _pick(rng, weights)
    return {
        "style": style,
        "colors": [ctx["primary"], ctx["secondary"], third_color],
        "shares": [primary, secondary, third],
        "pattern": _pick(rng, SPECIES_PATTERNS.get(species, PATTERNS)),
        "splotch": round(rng.uniform(*SPLOTCH_RANGE), 3),
    }


def _roll_shape(seed: int, species: str, ctx: dict) -> dict:
    rng = _rng(seed, "shape")
    tri = lambda: round(rng.triangular(-3, 3, 0))  # noqa: E731
    shape = {
        "length": tri(),
        "height": tri(),
        "ears": round(rng.uniform(-1, 1), 3),
        "tail": round(rng.uniform(-1, 1), 3),
    }
    for name, (low, high, mode) in SHAPE_EXTRAS.get(species, {}).items():
        shape[name] = round(rng.triangular(low, high, mode), 3)
    if species in BREEDS:
        breeds = BREEDS[species]
        shape["breed"] = rng.choice(breeds)
        shape["mix"] = {}
        if rng.random() < MIX_CHANCE:
            donor = rng.choice([b for b in breeds if b != shape["breed"]])
            shape["mix"] = {rng.choice(MIX_PARTS[species]): donor}
    return shape


def _roll_face(seed: int, species: str, ctx: dict) -> dict:
    rng = _rng(seed, "face")
    palette = SPECIES_EYES.get(species, EYES)
    eyes = _pick(rng, palette)
    face = {"eyes": eyes, "sparkle": rng.random() < SPARKLE_CHANCE}
    if rng.random() < ODD_EYES_CHANCE.get(species, 0):
        face["odd_eye"] = _pick(rng, {c: w for c, w in palette.items() if c != eyes})
    return face


def _roll_personality(seed: int, species: str, ctx: dict) -> dict:
    rng = _rng(seed, "personality")
    return {
        "energy": _trait(rng),
        "friendly": _trait(rng),
        "curious": _trait(rng),
        "sleepy": _trait(rng),
        "favorite": rng.choice(VEGGIES),
    }


def _roll_battle(seed: int, species: str, ctx: dict) -> dict:
    """Not used yet: hooks for Pet Battles and other games."""
    rng = _rng(seed, "battle")
    stat = lambda: sum(rng.randint(1, 4) for _ in range(3)) - 2  # noqa: E731  1..10, mostly 4-7
    return {"strength": stat(), "speed": stat(), "stamina": stat(), "element": ELEMENTS[species], "level": 1, "xp": 0}


ROLLERS = {
    "coat": _roll_coat,
    "shape": _roll_shape,
    "face": _roll_face,
    "personality": _roll_personality,
    "battle": _roll_battle,
}


class GeneError(ValueError):
    """Kid-readable, like PetError."""


def new_seed(rng: random.Random | None = None) -> int:
    return (rng or random).randrange(1, 2**31)


def roll(species: str, primary: str, secondary: str, seed: int, unlocked: set[str] | None = None) -> dict:
    """A new pet's genes. `unlocked` is this learner's colors for the species
    (shared by every species; starting_unlocks() if None); primary and
    secondary must be among them."""
    if species not in SPECIES_COLORS:
        raise GeneError("There's no pet like that.")
    unlocked = set(unlocked) if unlocked is not None else starting_unlocks()
    if primary == secondary:
        raise GeneError("Pick two different colors.")
    if primary not in unlocked or secondary not in unlocked:
        raise GeneError("You haven't unlocked that color yet.")
    genes = {"version": GENES_VERSION, "species": species, "seed": seed}
    return fill_missing(genes, {"primary": primary, "secondary": secondary, "unlocked": unlocked})


def fill_missing(genes: dict, ctx: dict | None = None) -> dict:
    """Roll any stat group these genes don't have yet (new groups added
    after the pet was adopted). Groups that need adoption context (coat)
    are always present already."""
    out = dict(genes)
    for group, roller in ROLLERS.items():
        if group not in out:
            out[group] = roller(out["seed"], out["species"], ctx or {})
    return out


def resolve(genes: dict) -> dict:
    """Genes plus what the renderer needs: hex colors and color names."""
    colors = genes["coat"]["colors"]
    return {
        **genes,
        "hex": [COLORS[c].hex if c else None for c in colors],
        "color_names": [COLORS[c].name if c else None for c in colors],
    }


def new_colors(genes: dict, unlocked: set[str]) -> list[str]:
    """Colors on this pet the learner hadn't unlocked yet (for any species)."""
    return [c for c in genes["coat"]["colors"] if c and c not in unlocked]


def color_catalog(unlocked: set[str]) -> list[dict]:
    """Every color, unlocked ones flagged (the same list for every species)."""
    return [
        {"id": c.id, "name": c.name, "hex": c.hex, "family": c.family, "unlocked": c.id in unlocked}
        for c in COLORS.values()
    ]
