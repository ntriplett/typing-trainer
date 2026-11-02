"""Farm Stand (PLAN.md 11m): a market-day game on a farm that's saved.

One play is one day: plant in the morning (no timer), then HOURS market
hours of HOUR_SECONDS each, in real time: customers keep coming, crops
grow in seconds, and you replant while you serve. Then the evening tally.
The browser runs the day
(web/static/js/farm_stand.js); this module holds the catalog (crops,
upgrades), the save, and what a finished day earns. The farm has its own
money ("stand money") that only buys farm upgrades; coins are still paid
for each hour like the other games (/api/game/.../round).

Customers are grown animals rolled like the Pet Shop's (same rarity odds,
the player's own unlocked colors), new every day and never saved.

So planting is a choice, not a guess, you see the next few customers'
orders coming, and each day has delivery orders (deliveries()): animals
who want a bigger order by a deadline hour and pay DELIVERY_BONUS for it.
Your pet along carries them (and earns a PET_TIP), and tends a plot of its
own. A customer whose order you can't fill can take a swap (SWAP_SHARE of
the price for the swapped veggies).

A day only counts when it was paid for in the arcade: spending the token
opens a day (open_day) and finishing it closes it. Lab plays get a tally
but change nothing. A 3-star day gives one veggie (pet food) from the
crops sold that day.

Pacing: crops and upgrade levels open with reputation (stars earned), and
prices are tuned against typical_day_profit() so something new opens every
few days through day 50 and beyond (tests/unit/test_farm_stand.py).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app import db, garden, pet_shop
from app import pet_genes as g

GAME_ID = "game_farm_stand_v1"
HOURS = 4
HOUR_SECONDS = 60
DAY_SECONDS = HOURS * HOUR_SECONDS
DELIVERY_BONUS = 1.5
BASE_DELIVERIES = 2  # + the wagon's, 4 at most (two rows in the sky)
PET_TIP = 0.1  # a delivery your pet carries
SWAP_SHARE = 0.5
START_MONEY = 20
GREAT_SHARE = 0.8  # served share for 3 stars
GOOD_SHARE = 0.5  # ... for 2
GREAT_MIN_SERVED = 6  # serving 1 of 1 isn't a great day
MAX_PLOTS = 24
FANCY_PAY = 2  # fancy customers pay double (and want more, and wait less)
CUSTOMERS_PER_DAY = 12  # animals rolled for a day; they come back as regulars
MYTHICAL_CHANCE = 0.02
CUSTOMER_GROWTH = 10  # fully grown
BIG_BASKET_REP = 8  # big orders (3-4 veggies) start coming at this reputation
SERVE_SECONDS = 9  # the line is always full: about how long a busy player takes per customer


@dataclass(frozen=True, slots=True)
class Crop:
    id: str  # a garden veggie, so it can be pet food
    seed_cost: int
    grow: int  # seconds from planting to ripe
    yields: int
    price: int  # each
    rep: int  # reputation it opens at


CROPS: dict[str, Crop] = {
    c.id: c
    for c in [
        Crop("radish", 1, 20, 2, 2, 0),
        Crop("peas", 2, 25, 2, 3, 0),
        Crop("carrot", 3, 40, 3, 3, 0),
        Crop("tomato", 4, 45, 3, 4, 6),
        Crop("corn", 5, 50, 3, 5, 14),
        Crop("pepper", 6, 60, 3, 7, 24),
        Crop("zucchini", 7, 65, 4, 6, 36),
        Crop("broccoli", 8, 75, 3, 9, 50),
        Crop("eggplant", 9, 85, 3, 10, 66),
        Crop("pumpkin", 12, 110, 2, 16, 84),
    ]
}
assert set(CROPS) <= set(garden.VEGGIES)


@dataclass(frozen=True, slots=True)
class Upgrade:
    id: str
    name: str
    blurb: str
    values: tuple  # the value at level 0, 1, ...
    costs: tuple[int, ...]  # cost of level 1, 2, ...
    rep: tuple[int, ...]  # reputation each level opens at
    decor: bool = False  # just for looks: it shows on the stand

    @property
    def max_level(self) -> int:
        return len(self.costs)


def _decor(id_: str, name: str, blurb: str, cost: int, rep: int) -> Upgrade:
    return Upgrade(id_, name, blurb, (False, True), (cost,), (rep,), decor=True)


UPGRADES: dict[str, Upgrade] = {
    u.id: u
    for u in [
        Upgrade("plots", "More Plots", "Another plot to plant in.",
                tuple(range(4, MAX_PLOTS + 1)),
                (40, 70, 110, 160, 230, 320, 430, 560, 700, 850, 1000, 1150, 1300, 1450, 1600, 1800, 2000, 2200, 2400, 2600),
                (0, 2, 6, 12, 20, 30, 42, 56, 66, 76, 86, 96, 106, 116, 126, 136, 146, 156, 166, 176)),
        Upgrade("shelf", "Bigger Shelf", "Room for more veggies on the stand.",
                (8, 10, 12, 15, 18, 22, 26, 30),
                (60, 120, 220, 360, 520, 750, 1000),
                (2, 8, 18, 32, 50, 75, 100)),
        Upgrade("alarm", "Sprout Alarm", "Empty plots flash, so you never forget to plant.",
                (False, True), (60,), (3,)),
        Upgrade("bell", "Shop Bell", "Customers wait longer.",
                (1.0, 1.15, 1.3, 1.45),
                (80, 240, 480),
                (4, 16, 34)),
        Upgrade("tips", "Tip Jar", "Quick service earns bigger tips.",
                (0.5, 0.75, 1.0),
                (180, 500),
                (7, 26)),
        Upgrade("catalog", "Seed Catalog", "Seeds cost less.",
                (1.0, 0.75, 0.5),
                (150, 500),
                (8, 28)),
        Upgrade("sign", "Bigger Sign", "More big-basket customers.",
                (0.15, 0.22, 0.29, 0.36, 0.43, 0.5),
                (100, 220, 400, 620, 900),
                (6, 16, 30, 48, 70)),
        Upgrade("wagon", "Delivery Wagon", "More delivery orders every day.",
                (0, 1, 2),
                (200, 700),
                (9, 32)),
        Upgrade("sprinkler", "Sprinkler", "Crops grow faster.",
                (1.0, 1.15, 1.3, 1.5),
                (250, 600, 1200),
                (10, 30, 55)),
        Upgrade("pet_plots", "Pet Patch", "Your gardener pet gets another plot.",
                (1, 2, 3),
                (300, 900),
                (12, 40)),
        Upgrade("prices", "Price Board", "Veggies sell for more.",
                (1.0, 1.1, 1.2, 1.3),
                (350, 800, 1500),
                (14, 36, 65)),
        Upgrade("fancy", "Fancy Customers", "Some customers want more and wait less, but pay double!",
                (0, 0.1, 0.2, 0.3),
                (400, 900, 1700),
                (15, 35, 60)),
        Upgrade("robot", "Robo-Farmer", "A robot plot that keeps planting your first seed of the day.",
                (0, 1, 2, 3),
                (450, 1100, 2200),
                (20, 45, 80)),
        Upgrade("compost", "Compost", "Every plant grows one more veggie.",
                (0, 1, 2),
                (500, 1200),
                (28, 60)),
        _decor("flowers", "Flower Boxes", "Bright flowers along the stand.", 150, 10),
        _decor("awning", "Striped Awning", "Shade with stripes.", 250, 20),
        _decor("lanterns", "Lanterns", "A warm glow for the evening.", 400, 30),
        _decor("bunting", "Party Flags", "A string of little flags.", 550, 40),
        _decor("scarecrow", "Scarecrow", "A friendly scarecrow by the plots.", 700, 50),
        _decor("bench", "Bench", "A seat for customers who wait.", 850, 60),
        _decor("beehive", "Beehive", "Buzzy bees for the flowers.", 1000, 70),
        _decor("apple_tree", "Apple Tree", "A big tree beside the stand.", 1200, 80),
        _decor("pond", "Duck Pond", "A little pond with ducks.", 1400, 90),
        _decor("windmill", "Windmill", "It turns in the breeze.", 1700, 100),
        _decor("barn", "Red Barn", "Every farm needs a barn.", 2000, 115),
        _decor("ribbon", "Blue Ribbon", "Best Farm Stand in the county!", 2500, 130),
    ]
}


class FarmError(ValueError):
    """Kid-readable, like StoreError."""


# --- the save --------------------------------------------------------------------


def new_save() -> dict:
    return {
        "day": 0,
        "money": START_MONEY,
        "reputation": 0,
        "upgrades": {},
        "best_day": 0,
        "served": 0,
        "earned": 0,
        "great_days": 0,
        "open_day": False,
    }


def load(conn, learner_id: int) -> dict:
    return {**new_save(), **(db.get_farm(conn, learner_id) or {})}


def level(save: dict, upgrade_id: str) -> int:
    return save["upgrades"].get(upgrade_id, 0)


def value(save: dict, upgrade_id: str):
    return UPGRADES[upgrade_id].values[level(save, upgrade_id)]


def open_crops(save: dict) -> list[Crop]:
    return [c for c in CROPS.values() if c.rep <= save["reputation"]]


def crop_yield(save: dict, crop: Crop) -> int:
    return crop.yields + value(save, "compost")


# --- the upgrade shop ------------------------------------------------------------


def shop(save: dict) -> list[dict]:
    out = []
    for u in UPGRADES.values():
        lv = level(save, u.id)
        done = lv >= u.max_level
        out.append({
            "id": u.id,
            "name": u.name,
            "blurb": u.blurb,
            "level": lv,
            "max_level": u.max_level,
            "value": u.values[lv],
            "next_value": None if done else u.values[lv + 1],
            "cost": None if done else u.costs[lv],
            "needs_rep": None if done or u.rep[lv] <= save["reputation"] else u.rep[lv],
            "can_buy": not done and u.rep[lv] <= save["reputation"] and u.costs[lv] <= save["money"],
        })
    return out


def apply_buy(save: dict, upgrade_id: str) -> dict:
    """The save after buying the next level (pure)."""
    u = UPGRADES.get(upgrade_id)
    if u is None:
        raise FarmError("There's no upgrade like that.")
    lv = level(save, upgrade_id)
    if lv >= u.max_level:
        raise FarmError(f"{u.name} is as big as it gets!")
    if u.rep[lv] > save["reputation"]:
        raise FarmError(f"Earn {u.rep[lv]} stars of reputation first.")
    if u.costs[lv] > save["money"]:
        raise FarmError(f"That costs ${u.costs[lv]}. Sell more veggies!")
    return {**save, "money": save["money"] - u.costs[lv], "upgrades": {**save["upgrades"], upgrade_id: lv + 1}}


def buy(conn, learner_id: int, upgrade_id: str) -> dict:
    save = apply_buy(load(conn, learner_id), upgrade_id)
    db.save_farm(conn, learner_id, save)
    return save


# --- a day -----------------------------------------------------------------------


def open_day(conn, learner_id: int) -> None:
    """The arcade sold a play: the next finished day counts."""
    db.save_farm(conn, learner_id, {**load(conn, learner_id), "open_day": True})


def stars_for(served: int, missed: int) -> int:
    if served <= 0:
        return 0
    share = served / (served + missed)
    if share >= GREAT_SHARE and served >= GREAT_MIN_SERVED:
        return 3
    return 2 if share >= GOOD_SHARE else 1


def all_plots(save: dict) -> int:
    """Your plots, the pet's and the robot's."""
    return value(save, "plots") + value(save, "pet_plots") + value(save, "robot")


def max_sold(save: dict) -> int:
    """The most veggies a day can possibly sell: every plot replanted with
    the quickest crop the moment it's picked, at the biggest yield."""
    quickest = min(c.grow for c in CROPS.values()) / value(save, "sprinkler")
    biggest = max(crop_yield(save, c) for c in CROPS.values())
    return all_plots(save) * int(DAY_SECONDS // quickest + 1) * biggest


def max_pay(save: dict) -> float:
    """Most a veggie can earn, as a share of its base price: a fancy
    customer's with the biggest tip, or a pet-carried delivery."""
    fancy = FANCY_PAY if value(save, "fancy") else 1
    return value(save, "prices") * max(fancy * (1 + value(save, "tips")), DELIVERY_BONUS * (1 + PET_TIP))


def check_day(save: dict, served: int, missed: int, sold: dict[str, int], earned: int, spent: int) -> None:
    """What the browser reports has to be possible on this farm."""
    if min(served, missed, earned, spent, *sold.values(), 0) < 0:
        raise FarmError("A day can't sell less than nothing.")
    opened = {c.id for c in open_crops(save)}
    if not set(sold) <= opened:
        raise FarmError("That crop isn't open on this farm yet.")
    if sum(sold.values()) > max_sold(save):
        raise FarmError("That's more veggies than this farm can grow.")
    if served > sum(sold.values()):
        raise FarmError("Every served customer buys at least one veggie.")
    if earned > sum(CROPS[c].price * n for c, n in sold.items()) * max_pay(save):
        raise FarmError("That's more money than those veggies are worth.")


def apply_day(save: dict, served: int, missed: int, sold: dict[str, int], earned: int, spent: int) -> tuple[dict, dict]:
    """(new save, the tally) for a finished day (pure; check_day first)."""
    stars = stars_for(served, missed)
    profit = earned - spent
    before = {c.id for c in open_crops(save)}
    new = {
        **save,
        "day": save["day"] + 1,
        "money": max(0, save["money"] + profit),
        "reputation": save["reputation"] + stars,
        "best_day": max(save["best_day"], profit),
        "served": save["served"] + served,
        "earned": save["earned"] + earned,
        "great_days": save["great_days"] + (stars == 3),
        "open_day": False,
    }
    tally = {
        "stars": stars,
        "profit": profit,
        "best": profit > save["best_day"] and save["day"] > 0,
        "new_crops": [c.id for c in open_crops(new) if c.id not in before],
    }
    return new, tally


def finish_day(conn, learner_id: int, served: int, missed: int, sold: dict[str, int], earned: int, spent: int,
               rng: random.Random | None = None) -> dict:
    """Ends a day. Saved (and maybe a veggie) only if the arcade opened it."""
    rng = rng or random.Random()
    save = load(conn, learner_id)
    sold = {c: n for c, n in sold.items() if n > 0}
    check_day(save, served, missed, sold, earned, spent)
    new, tally = apply_day(save, served, missed, sold, earned, spent)
    counted = save["open_day"]
    veggie = None
    if counted:
        if tally["stars"] == 3 and sold:
            veggie = rng.choices(list(sold), weights=list(sold.values()))[0]
            db.add_veggies(conn, learner_id, veggie, 1, "farm_stand")
        db.save_farm(conn, learner_id, new)
    return {**tally, "counted": counted, "veggie": veggie, "farm": state(new if counted else save)}


# --- what the browser gets -------------------------------------------------------


def customers(unlocked: set[str], rng: random.Random, count: int = CUSTOMERS_PER_DAY) -> list[dict]:
    """Today's customers: grown animals rolled like the Pet Shop's."""
    land = [sp for d in pet_shop.STOCKED if d not in ("fish", "mythical", "companions") for sp in pet_shop.DEPARTMENTS[d].species]
    mythical = (*pet_shop.DEPARTMENTS["mythical"].species, "flower_fairy")  # a mermaid can't walk up to the stall
    out = []
    for _ in range(count):
        sp = rng.choice(mythical if rng.random() < MYTHICAL_CHANCE else land)
        genes = g.resolve(g.shop_roll(sp, unlocked, g.new_seed(rng)))
        out.append({"species": sp, "growth": CUSTOMER_GROWTH, "genes": genes,
                    "favorite": genes["personality"]["favorite"]})
    return out


def deliveries(save: dict, customers: list[dict], rng: random.Random) -> list[dict]:
    """Today's delivery orders: an animal from `customers` (by index) wanting a
    bigger order by the end of hour `due`, paying DELIVERY_BONUS for it."""
    crops = open_crops(save)
    rep = save["reputation"]
    out = []
    for i in rng.sample(range(len(customers)), min(len(customers), BASE_DELIVERIES + value(save, "wagon"))):
        # one kind, two once the farm is known
        kinds = rng.sample([c.id for c in crops], 1 + (rep >= 10 and len(crops) > 1))
        size = rng.randint(3, 5) + rep // 25
        order: dict[str, int] = {}
        for _ in range(size):
            k = rng.choice(kinds)
            order[k] = order.get(k, 0) + 1
        due = rng.randint(2, HOURS)
        pay = round(sum(CROPS[k].price * n for k, n in order.items()) * DELIVERY_BONUS)
        out.append({"customer": i, "order": order, "due": due, "pay": pay})
    return sorted(out, key=lambda d: d["due"])


def state(save: dict) -> dict:
    """The save plus everything derived from it, for the page."""
    return {
        **save,
        "plots": value(save, "plots"),
        "pet_plots": value(save, "pet_plots"),
        "robot_plots": value(save, "robot"),
        "shelf": value(save, "shelf"),
        "patience": value(save, "bell"),
        "max_tip": value(save, "tips"),
        "alarm": value(save, "alarm"),
        "fancy_share": value(save, "fancy"),
        "fancy_pay": FANCY_PAY,
        "big_share": value(save, "sign") if save["reputation"] >= BIG_BASKET_REP else 0,
        "crops": [
            # what they cost, take and sell for on this farm (catalog, sprinkler, price board)
            {"id": c.id, "name": garden.VEGGIES[c.id].name,
             "seed_cost": max(1, round(c.seed_cost * value(save, "catalog"))),
             "grow": round(c.grow / value(save, "sprinkler")),
             "yields": crop_yield(save, c), "price": round(c.price * value(save, "prices"), 2)}
            for c in open_crops(save)
        ],
        "next_crop": next(({"id": c.id, "name": garden.VEGGIES[c.id].name, "rep": c.rep}
                           for c in CROPS.values() if c.rep > save["reputation"]), None),
        "shop": shop(save),
    }


def game_data(conn, learner_id: int, game: dict, rng: random.Random | None = None) -> dict:
    """The game content's `game` plus `farm` (the state) and `customers`."""
    rng = rng or random.Random()
    unlocked = db.list_pet_color_unlocks(conn, learner_id)
    save = load(conn, learner_id)
    people = customers(unlocked, rng)
    return {
        **game,
        "hours": HOURS,
        "farm": state(save),
        "customers": people,
        "deliveries": deliveries(save, people, rng),
        "rules": {"swap_share": SWAP_SHARE, "pet_tip": PET_TIP},
    }


# --- pacing ----------------------------------------------------------------------


def typical_day_profit(save: dict, serve_rate: float = 0.75) -> int:
    """A rough model of an average day, for tuning prices (not used in play):
    the line is always full, so the player sells about one order every
    SERVE_SECONDS; customers ask for a mix of the open crops, and the plots
    (yours, the pet's, the robot's) grow them (a replant takes about 5
    seconds of a busy player's time)."""
    crops = open_crops(save)
    big = state(save)["big_share"]
    fancy = value(save, "fancy")
    items_each = 1.6 + big * 2 + fancy * 0.8  # a big basket is 3-4 veggies; fancy ones want 50% more
    demand = DAY_SECONDS / SERVE_SECONDS * serve_rate * items_each * (0.9 + 0.1 * value(save, "bell"))
    speed = value(save, "sprinkler")
    per_plot = sum(DAY_SECONDS / (c.grow / speed + 5) * crop_yield(save, c) for c in crops) / len(crops)
    supply = per_plot * all_plots(save)
    shelf_cap = value(save, "shelf") * HOURS * 2
    sold = min(demand, supply, shelf_cap)
    price = value(save, "prices") * (1 + fancy * (FANCY_PAY - 1))
    margin = sum(c.price * price - c.seed_cost * value(save, "catalog") / crop_yield(save, c) for c in crops) / len(crops)
    tips = 1 + 0.3 * value(save, "tips")  # deliveries and tips
    return int(sold * margin * tips)
