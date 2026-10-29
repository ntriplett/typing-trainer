"""The Pet Shop (PLAN.md 11h): departments of pets rolled by
app/pet_genes.py, each player with their own stock.

Each slot holds one pet for STAY_DAYS, then a new one rolls in at
midnight (slots come and go on their own days, so the shop changes a
little each day). One pet in the whole shop can be saved ("Save for me"):
it never leaves. A bought pet's slot stays empty until tomorrow.

The pure rules come first: `today` is passed in and slots are plain
values, so tests can run a fake calendar. Below them, one learner's shop
stored in app/db.py: departments opening as rows are learned, buying
(coins, or the pet coupon learning the home row gives), Save for me.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from datetime import date, timedelta

from app import aquarium, db, lessons, pet_care, pet_supplies
from app import pet_genes as g
from app.activities.teach_curriculum import CAPS_GROUPS, CAPS_ID
from app.brain import lesson_ref

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
        Department("farm", "Farm Pets", ("goat", "sheep", "llama", "fox"), 12, 2000, TOP_ROW),
        Department("reptiles", "Reptiles & Amphibians", ("turtle", "lizard", "snake"), 8, 3000, BOTTOM_ROW),
        Department("mythical", "Mythical Pets", ("dragon", "unicorn", "phoenix"), 2, 10000, NUMBERS),
        Department("orders", "Special Orders", (), 4, 0, HOME_ROW),
        Department("habitats", "Habitats", (), 0, 0, ""),  # sold by app/pet_care.py
        Department("aqua", "Aquarium Supplies", (), 0, 0, ""),  # sold by app/aquarium.py
        Department("supplies", "Pet Supplies", (), 0, 0, ""),  # sold by app/pet_supplies.py
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


# --- special orders: pick a species and its colors, pets arrive tomorrow -------------

ORDER_PETS = 4
ORDER_DAYS = 3  # how long the pets wait once they arrive
ORDER_FEE_SHARE = 0.5  # of the species' base price, paid when ordering


def order_fee(species: str) -> int:
    return nice_price(BASE_PRICE[species] * ORDER_FEE_SHARE)


def order_slots(
    species: str, primary: str, secondary: str | None, today: date, unlocked: set[str], rng: random.Random
) -> list[Slot]:
    """The pets an order brings: they arrive tomorrow and wait ORDER_DAYS."""
    ready = today + timedelta(days=1)
    out = []
    for i in range(ORDER_PETS):
        seed = g.new_seed(rng)
        out.append(
            Slot(
                dept="orders", index=i, seed=seed, species=species,
                genes=g.order_roll(species, primary, secondary, unlocked, seed),
                price_roll=roll_price_factor(rng), stocked_on=ready, leaves_on=ready + timedelta(days=ORDER_DAYS),
            )
        )
    return out


def order_status(ready_on: date, leaves_on: date, today: date) -> str | None:
    """"waiting" (arriving tomorrow), "ready" (here now), or None (no order, or they went home)."""
    if today < ready_on:
        return "waiting"
    return "ready" if today < leaves_on else None


# --- one learner's shop, stored in app/db.py ---------------------------------------

# Learning the home row gives one coupon: any Household pet for free.
COUPON_DEPT = "household"
SETTING_COUPON_USED = "pet_coupon_used"


# TEMPORARY test switch: a learner with this setting has every department and
# the order's second color open. Remove once shop testing is done.
SETTING_OPEN_ALL = "pet_shop_open_all"
_ALL_KEYS = set("abcdefghijklmnopqrstuvwxyz0123456789;,./'")


def _taught(conn, learner_id: int) -> set[str]:
    if db.get_setting(conn, learner_id, SETTING_OPEN_ALL):
        return _ALL_KEYS
    return lessons.taught_keys(conn, learner_id)


class Closed(PermissionError):
    """A department that hasn't opened yet (kid-readable)."""


def _to_row(slot: Slot) -> dict:
    return {
        "dept": slot.dept, "idx": slot.index, "seed": slot.seed, "species": slot.species, "genes": slot.genes,
        "price_roll": slot.price_roll, "stocked_on": slot.stocked_on.isoformat(),
        "leaves_on": slot.leaves_on.isoformat(), "saved": slot.saved, "sold": slot.sold,
    }


def _from_row(row: dict) -> Slot:
    return Slot(
        dept=row["dept"], index=row["idx"], seed=row["seed"], species=row["species"], genes=row["genes"],
        price_roll=row["price_roll"], stocked_on=date.fromisoformat(row["stocked_on"]),
        leaves_on=date.fromisoformat(row["leaves_on"]), saved=row["saved"], sold=row["sold"],
    )


def _dept_info(dept: Department, taught: set[str]) -> dict:
    return {
        "id": dept.id, "name": dept.name, "species": list(dept.species), "slots": dept.slots,
        "open": is_open(dept, taught), "soon": dept.soon, "missing": missing_keys(dept, taught),
    }


def _open_dept(conn, learner_id: int, dept_id: str) -> Department:
    dept = DEPARTMENTS.get(dept_id)
    if dept is None:
        raise ShopError("There's no department like that.")
    missing = missing_keys(dept, _taught(conn, learner_id))
    if dept.soon:
        raise Closed(f"{dept.name} is coming soon!")
    if missing:
        raise Closed(f"{dept.name} opens when you learn {' '.join(missing.upper())}.")
    return dept


def magical_habitats_open(conn, learner_id: int) -> bool:
    """Magical habitats open with the Mythical department."""
    return is_open(DEPARTMENTS["mythical"], _taught(conn, learner_id))


def has_coupon(conn, learner_id: int) -> bool:
    taught = _taught(conn, learner_id)
    return is_open(DEPARTMENTS[COUPON_DEPT], taught) and db.get_setting(conn, learner_id, SETTING_COUPON_USED) is None


def stock(conn, learner_id: int, dept_id: str, today: date, rng: random.Random | None = None) -> list[Slot]:
    """Today's stock for an open department, restocked and stored."""
    _open_dept(conn, learner_id, dept_id)
    if dept_id in ("habitats", "aqua", "supplies"):
        return []
    if dept_id == "orders":  # never restocked: only an order's pets, while they wait
        rows = [_from_row(r) for r in db.list_shop_slots(conn, learner_id, dept_id)]
        return [s for s in rows if s.stocked_on <= today < s.leaves_on]
    if dept_id not in STOCKED:
        raise ShopError("Nothing here yet!")
    old = [_from_row(r) for r in db.list_shop_slots(conn, learner_id, dept_id)]
    unlocked = db.list_pet_color_unlocks(conn, learner_id)
    new = refresh(dept_id, old, today, unlocked, rng or random.Random())
    for slot in new:
        if slot not in old:
            db.put_shop_slot(conn, learner_id, _to_row(slot))
    return new


def _saved(conn, learner_id: int) -> Slot | None:
    return next((_from_row(r) for r in db.list_shop_slots(conn, learner_id) if r["saved"]), None)


def shop_state(conn, learner_id: int, today: date) -> dict:
    """The shop's front: every department, the saved pet, the coupon."""
    taught = _taught(conn, learner_id)
    saved = _saved(conn, learner_id)
    unlocked = db.list_pet_color_unlocks(conn, learner_id)
    return {
        "departments": [_dept_info(d, taught) for d in DEPARTMENTS.values()],
        "saved": view(saved, today, unlocked) if saved else None,
        "coupon": has_coupon(conn, learner_id),
    }


def department_state(conn, learner_id: int, dept_id: str, today: date, rng: random.Random | None = None) -> dict:
    slots = stock(conn, learner_id, dept_id, today, rng)
    unlocked = db.list_pet_color_unlocks(conn, learner_id)
    taught = _taught(conn, learner_id)
    saved = _saved(conn, learner_id)
    out = {
        "department": _dept_info(DEPARTMENTS[dept_id], taught),
        "slots": [view(s, today, unlocked) for s in slots],
        "saved": view(saved, today, unlocked) if saved else None,
        "coupon": dept_id == COUPON_DEPT and has_coupon(conn, learner_id),
    }
    if dept_id == "orders":
        out |= {
            "order": _order_view(conn, learner_id, today),
            "choices": order_choices(conn, learner_id),
            "pick_secondary": capitals_done(conn, learner_id),
        }
    if dept_id == "aqua":
        out["aqua"] = aquarium.supplies_state(conn, learner_id)
    if dept_id == "supplies":
        out["supplies"] = pet_supplies.supplies_state(conn, learner_id, today)
    if dept_id == "habitats":
        out["habitats"] = pet_care.habitats_state(conn, learner_id, magical_habitats_open(conn, learner_id))
    return out


def _slot(conn, learner_id: int, dept_id: str, index: int, today: date) -> Slot:
    slot = next((s for s in stock(conn, learner_id, dept_id, today) if s.index == index), None)
    if slot is None:
        raise ShopError("There's no pet in that spot.")
    return slot


def buy(conn, learner_id: int, dept_id: str, index: int, today: date, use_coupon: bool = False) -> dict:
    """Buy the pet in a slot (with coins or the coupon): it goes to the Pet
    Care Center and all its colors unlock. Returns the new pet."""
    slot = _slot(conn, learner_id, dept_id, index, today)
    sold = sell(slot, today)  # raises if it's gone already, before anything is paid
    if dept_id == "orders":  # an order's other pets keep waiting; this spot stays "Adopted!"
        sold = replace(sold, leaves_on=slot.leaves_on)
    unlocked = db.list_pet_color_unlocks(conn, learner_id)
    if use_coupon:
        if dept_id != COUPON_DEPT:
            raise ShopError("Your pet coupon is for Household Pets.")
        if not has_coupon(conn, learner_id):
            raise ShopError("You don't have a pet coupon.")
        db.set_setting(conn, learner_id, SETTING_COUPON_USED, today.isoformat())
    else:
        cost = price(slot.genes, unlocked, slot.price_roll)
        balance = db.get_coin_balance(conn, learner_id)
        if balance < cost:
            raise ShopError(f"You need {cost - balance:,} more coins for this {slot.species}.")
        db.add_coins(conn, learner_id, -cost, "purchase", ref=f"pet:{dept_id}:{slot.seed}")
    db.put_shop_slot(conn, learner_id, _to_row(sold))
    new = g.new_to_player(slot.genes, unlocked)
    db.unlock_pet_colors(conn, learner_id, [c for c in slot.genes["coat"]["colors"] if c and g.COLORS[c].family != "metal"])
    source = "order" if dept_id == "orders" else "shop"
    pet_id = db.add_v3_pet(conn, learner_id, slot.genes, slot.species.capitalize(), source)
    pet = db.get_v3_pet(conn, learner_id, pet_id)
    return {**pet, "genes": g.resolve(pet["genes"]), "new_colors": [g.COLORS[c].name for c in new]}


# A school: another of a fish you have costs a fifth of its shop price (its colors are yours already).
COPY_SHARE = 0.2


def copy_price(conn, learner_id: int, genes: dict) -> int:
    return nice_price(price(genes, db.list_pet_color_unlocks(conn, learner_id), 1.0) * COPY_SHARE)


def buy_fish_copy(conn, learner_id: int, pet_id: int) -> dict:
    """Another of a fish, joining its school: same look, name and growth."""
    pet = db.get_v3_pet(conn, learner_id, pet_id)
    if pet is None:
        raise ShopError("You don't have that pet.")
    if pet["species"] != "fish":
        raise ShopError("Only fish come in schools!")
    head = db.get_v3_pet(conn, learner_id, pet["school"]) if pet["school"] else pet
    cost = copy_price(conn, learner_id, head["genes"])
    balance = db.get_coin_balance(conn, learner_id)
    if balance < cost:
        raise ShopError(f"You need {cost - balance:,} more coins for another {head['name']}.")
    db.add_coins(conn, learner_id, -cost, "purchase", ref=f"pet:copy:{head['id']}")
    new_id = db.add_v3_pet(conn, learner_id, head["genes"], head["name"], "copy", school=head["id"], growth=head["growth"])
    return {"id": new_id, "price": cost}


def save_pet(conn, learner_id: int, dept_id: str, index: int, today: date) -> None:
    if dept_id == "orders":
        raise ShopError("Special order pets are already waiting just for you!")
    slot = _slot(conn, learner_id, dept_id, index, today)
    db.put_shop_slot(conn, learner_id, _to_row(save(slot, _saved(conn, learner_id))))


def unsave_pet(conn, learner_id: int, today: date) -> str:
    """Let the saved pet go; returns its department."""
    saved = _saved(conn, learner_id)
    if saved is None:
        raise ShopError("You aren't saving a pet.")
    db.put_shop_slot(conn, learner_id, _to_row(unsave(saved, today)))
    return saved.dept


# --- one learner's special order -------------------------------------------------------


def capitals_done(conn, learner_id: int) -> bool:
    """Picking an order's second color opens once capital letters are learned."""
    if db.get_setting(conn, learner_id, SETTING_OPEN_ALL):
        return True
    taught = db.list_taught(conn, learner_id)
    return all(lesson_ref(CAPS_ID, letters) in taught for letters in CAPS_GROUPS)


def _color(color_id: str) -> dict:
    c = g.COLORS[color_id]
    return {"id": c.id, "name": c.name, "hex": c.hex}


def order_choices(conn, learner_id: int) -> list[dict]:
    """Every species an order can ask for (its department is open), with its
    fee and the colors it can be ordered in."""
    taught = _taught(conn, learner_id)
    unlocked = db.list_pet_color_unlocks(conn, learner_id)
    return [
        {
            "species": sp, "dept": d.id, "fee": order_fee(sp),
            "primaries": [_color(c) for c in g.order_primaries(sp, unlocked)],
            "colors": [_color(c) for c in g.available_colors(sp, unlocked)],
        }
        for d in DEPARTMENTS.values()
        if d.id in STOCKED and is_open(d, taught)
        for sp in d.species
    ]


def _order_view(conn, learner_id: int, today: date) -> dict | None:
    order = db.get_special_order(conn, learner_id)
    if order is None:
        return None
    ready_on, leaves_on = date.fromisoformat(order["ready_on"]), date.fromisoformat(order["leaves_on"])
    status = order_status(ready_on, leaves_on, today)
    if status is None:
        return None
    return {
        "species": order["species"],
        "primary": _color(order["primary_color"]),
        "secondary": _color(order["secondary_color"]) if order["secondary_color"] else None,
        "status": status,
        "days_left": (leaves_on - today).days if status == "ready" else None,
    }


def _check_order(conn, learner_id: int, species: str, secondary: str | None) -> None:
    if species not in {c["species"] for c in order_choices(conn, learner_id)}:
        raise ShopError("You can't order that pet yet.")
    if secondary is not None and not capitals_done(conn, learner_id):
        raise ShopError("Learn your capital letters to pick a second color too!")


def place_order(
    conn, learner_id: int, species: str, primary: str, secondary: str | None, today: date,
    rng: random.Random | None = None,
) -> None:
    """Pay the fee and send the order: its pets arrive tomorrow. Any pets
    still waiting from the last order go home."""
    _open_dept(conn, learner_id, "orders")
    _check_order(conn, learner_id, species, secondary)
    unlocked = db.list_pet_color_unlocks(conn, learner_id)
    try:
        slots = order_slots(species, primary, secondary, today, unlocked, rng or random.Random())
    except g.GeneError as exc:
        raise ShopError(str(exc)) from None
    fee = order_fee(species)
    balance = db.get_coin_balance(conn, learner_id)
    if balance < fee:
        raise ShopError(f"You need {fee - balance:,} more coins to send this order.")
    db.add_coins(conn, learner_id, -fee, "purchase", ref=f"order:{species}:{today.isoformat()}")
    db.clear_shop_slots(conn, learner_id, "orders")
    for slot in slots:
        db.put_shop_slot(conn, learner_id, _to_row(slot))
    db.put_special_order(conn, learner_id, {
        "species": species, "primary_color": primary, "secondary_color": secondary, "fee": fee,
        "ordered_on": today.isoformat(), "ready_on": slots[0].stocked_on.isoformat(),
        "leaves_on": slots[0].leaves_on.isoformat(),
    })


def order_preview(conn, learner_id: int, species: str, primary: str, secondary: str | None) -> dict:
    """One pet like the order would bring (nothing saved), for the order form."""
    _open_dept(conn, learner_id, "orders")
    _check_order(conn, learner_id, species, secondary)
    unlocked = db.list_pet_color_unlocks(conn, learner_id)
    try:
        return g.resolve(g.order_roll(species, primary, secondary, unlocked, g.new_seed()))
    except g.GeneError as exc:
        raise ShopError(str(exc)) from None


# --- the Pets hub: who's out in the field --------------------------------------------

# Land pets out in the field; a new player's field is filled up with visitors.
FIELD_PETS = 4
VISITOR_DEPTS = ("household", "farm")


def hub_visitors(learner_id: int, today: date, count: int) -> list[dict]:
    """Animals passing through the field: rolled fresh each day (the same
    all day), in starter colors, never saved."""
    rng = random.Random(f"visitors:{learner_id}:{today.isoformat()}")
    species = [sp for d in VISITOR_DEPTS for sp in DEPARTMENTS[d].species]
    out = []
    for _ in range(count):
        sp = rng.choice(species)
        out.append({"species": sp, "growth": rng.randint(3, 10), "genes": g.resolve(g.shop_roll(sp, set(), g.new_seed(rng)))})
    return out


def hub_state(conn, learner_id: int, today: date) -> dict:
    """The Pets hub: your pets, the ones out in the field (pet_care.field_pets),
    visitors to fill it up, and news for the Pet Shop's door (a coupon, an order)."""
    pets = [
        {"id": p["id"], "name": p["name"], "species": p["species"], "growth": p["growth"], "genes": g.resolve(p["genes"])}
        for p in db.list_v3_pets(conn, learner_id)
    ]
    field = pet_care.field_pets(conn, learner_id, today)
    return {
        "pets": pets,
        "field": field,
        "visitors": hub_visitors(learner_id, today, max(0, FIELD_PETS - len(field))),
        "coupon": has_coupon(conn, learner_id),
        "order": _order_view(conn, learner_id, today),
    }
