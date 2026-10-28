"""The Pet Shop (PLAN.md 11h): departments of pets rolled by
app/pet_genes.py, each player with their own stock.

Each slot holds one pet for STAY_DAYS, then a new one rolls in at
midnight (slots come and go on their own days, so the shop changes a
little each day). One pet in the whole shop can be saved ("Save for me"):
it never leaves. A bought pet's slot stays empty until tomorrow.

These are the pure rules: `today` is passed in, and slots are plain
values the caller stores (app/db.py) -- so tests can run a fake calendar.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from datetime import date, timedelta

from app import pet_genes as g

HOME_ROW = "asdfghjkl;"
TOP_ROW = "qwertyuiop"
BOTTOM_ROW = "zxcvbnm,./"
NUMBERS = "1234567890"


@dataclass(frozen=True, slots=True)
class Department:
    id: str
    name: str
    species: tuple[str, ...]
    slots: int
    base_price: int
    needs: str  # keys to learn before it opens ("" = open from the start)
    soon: bool = False  # not built yet: always "coming soon"


DEPARTMENTS: dict[str, Department] = {
    d.id: d
    for d in [
        Department("fish", "Fish", ("fish",), 16, 100, ""),
        Department("household", "Household Pets", ("dog", "cat", "bunny"), 16, 800, HOME_ROW),
        Department("farm", "Farm Pets", ("goat", "sheep", "llama"), 12, 2000, TOP_ROW),
        Department("reptiles", "Reptiles & Amphibians", ("turtle", "lizard", "snake"), 8, 3000, BOTTOM_ROW),
        Department("mythical", "Mythical Pets", ("dragon", "unicorn", "phoenix"), 2, 10000, NUMBERS),
        Department("orders", "Special Orders", (), 4, 0, HOME_ROW),
        Department("supplies", "Pet Supplies", (), 0, 0, "", soon=True),
    ]
}
# Departments whose stock rolls in by itself (special orders arrive when ordered).
STOCKED = tuple(d.id for d in DEPARTMENTS.values() if d.species)
BASE_PRICE = {sp: d.base_price for d in DEPARTMENTS.values() for sp in d.species}

STAY_DAYS = (2, 5)
NEW_COLOR_PRICE = 1.5
# The random part of a price: a bell curve, re-drawn until it lands in range.
PRICE_ROLL_MEAN = 0.75
PRICE_ROLL_SD = 0.25
PRICE_ROLL_RANGE = (0.25, 1.5)


class ShopError(ValueError):
    """Kid-readable, like PetError."""


@dataclass(frozen=True, slots=True)
class Slot:
    dept: str
    index: int
    seed: int
    species: str
    genes: dict
    price_roll: float
    stocked_on: date
    leaves_on: date  # the first day it's gone
    saved: bool = False
    sold: bool = False  # bought: empty until leaves_on


def missing_keys(dept: Department, taught: set[str]) -> str:
    return "".join(k for k in dept.needs if k not in taught)


def is_open(dept: Department, taught: set[str]) -> bool:
    return not dept.soon and not missing_keys(dept, taught)


def roll_price_factor(rng: random.Random) -> float:
    low, high = PRICE_ROLL_RANGE
    while True:
        x = rng.gauss(PRICE_ROLL_MEAN, PRICE_ROLL_SD)
        if low <= x <= high:
            return round(x, 3)


def nice_price(amount: float) -> int:
    """Rounded like a shop would: 75, 1,230, 4,350, 12,400."""
    step = 5 if amount < 200 else 10 if amount < 2000 else 50 if amount < 10000 else 100
    return max(step, round(amount / step) * step)


def price(genes: dict, unlocked: set[str], price_roll: float) -> int:
    """Worked out when shown, so unlocking a color makes its pets cheaper."""
    amount = BASE_PRICE[genes["species"]] * g.rarity(genes) * price_roll
    if g.new_to_player(genes, unlocked):
        amount *= NEW_COLOR_PRICE
    return nice_price(amount)


def stock_slot(dept_id: str, index: int, today: date, unlocked: set[str], rng: random.Random) -> Slot:
    dept = DEPARTMENTS[dept_id]
    species = rng.choice(dept.species)
    seed = g.new_seed(rng)
    return Slot(
        dept=dept_id,
        index=index,
        seed=seed,
        species=species,
        genes=g.shop_roll(species, unlocked, seed),
        price_roll=roll_price_factor(rng),
        stocked_on=today,
        leaves_on=today + timedelta(days=rng.randint(*STAY_DAYS)),
    )


def refresh(dept_id: str, slots: list[Slot], today: date, unlocked: set[str], rng: random.Random) -> list[Slot]:
    """The department's stock for today: saved pets and pets whose day
    hasn't come stay; every other slot (empty, gone, or sold yesterday)
    gets a new pet."""
    have = {s.index: s for s in slots}
    out = []
    for i in range(DEPARTMENTS[dept_id].slots):
        slot = have.get(i)
        if slot is None or not (slot.saved or today < slot.leaves_on):
            slot = stock_slot(dept_id, i, today, unlocked, rng)
        out.append(slot)
    return out


def last_day(slot: Slot, today: date) -> bool:
    """Leaving tomorrow: the shop shows a "Last day!" banner."""
    return not slot.saved and not slot.sold and slot.leaves_on == today + timedelta(days=1)


def save(slot: Slot, already: Slot | None) -> Slot:
    """Save a pet for later. `already`: the one saved now, if any."""
    if slot.sold:
        raise ShopError("That pet already went home with someone.")
    if already is not None and (already.dept, already.index) != (slot.dept, slot.index):
        raise ShopError("You're already saving a pet. Buy it or let it go first.")
    return replace(slot, saved=True)


def unsave(slot: Slot, today: date) -> Slot:
    """Let a saved pet go. One that was past its day gets one last day."""
    return replace(slot, saved=False, leaves_on=max(slot.leaves_on, today + timedelta(days=1)))


def sell(slot: Slot, today: date) -> Slot:
    """Mark a slot bought (the caller pays and adds the pet): empty until tomorrow."""
    if slot.sold:
        raise ShopError("That pet already went home with someone.")
    return replace(slot, saved=False, sold=True, leaves_on=today + timedelta(days=1))


def view(slot: Slot, today: date, unlocked: set[str]) -> dict:
    """What the shop page draws for one slot."""
    if slot.sold:
        return {"dept": slot.dept, "index": slot.index, "sold": True}
    return {
        "dept": slot.dept,
        "index": slot.index,
        "sold": False,
        "species": slot.species,
        "genes": g.resolve(slot.genes),
        "price": price(slot.genes, unlocked, slot.price_roll),
        "new_colors": g.new_to_player(slot.genes, unlocked),
        "rare": g.rare_features(slot.genes),
        "saved": slot.saved,
        "last_day": last_day(slot, today),
    }
