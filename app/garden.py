"""The garden: where daily streaks grow into veggies (pet food).

Reaching half the daily goal (app/daily.py) pays a seed and waters the
garden. A seed planted in one of SPOTS spots grows a random veggie plant
with VEGGIES_PER_PLANT baby veggies; each watering ripens one of them.
Ripe veggies wait on the plant until picked; once the last one is picked
the spot is empty again. So practicing every chunk gives 1 veggie, then
2, ... up to 5 per chunk.

A plant that goes WITHER_AFTER without water withers: its ripe, unpicked
veggies drop into the basket (collect them any time), the rest are lost.
Watering is once per practice chunk, so the 12h/36h rhythm of the daily
goal carries over: play as often as every 12 hours, lose nothing for 36.

Withering is applied lazily: every read or action first calls tend().
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from app import db

SPOTS = 10
VEGGIES_PER_PLANT = 5
WITHER_AFTER = timedelta(hours=36)


@dataclass(frozen=True, slots=True)
class Veggie:
    id: str
    name: str
    plural: str


VEGGIES: dict[str, Veggie] = {
    v.id: v
    for v in [
        Veggie("carrot", "Carrot", "Carrots"),
        Veggie("tomato", "Tomato", "Tomatoes"),
        Veggie("pepper", "Pepper", "Peppers"),
        Veggie("zucchini", "Zucchini", "Zucchini"),
        Veggie("corn", "Corn", "Corn"),
        Veggie("pumpkin", "Pumpkin", "Pumpkins"),
        Veggie("peas", "Peas", "Peas"),
        Veggie("radish", "Radish", "Radishes"),
        Veggie("eggplant", "Eggplant", "Eggplants"),
        Veggie("broccoli", "Broccoli", "Broccoli"),
    ]
}


class GardenError(ValueError):
    """Kid-readable, like StoreError."""


def tend(conn: sqlite3.Connection, learner_id: int, now: datetime) -> list[dict]:
    """Wither every plant that went too long without water. Returns the
    withered plants ({"slot", "kind", "saved"}: saved went to the basket)."""
    withered = []
    for plot in db.list_plots(conn, learner_id):
        if now - plot["watered_at"] <= WITHER_AFTER:
            continue
        saved = plot["ripe"] - plot["picked"]
        if saved:
            db.add_to_basket(conn, learner_id, plot["kind"], saved)
        db.clear_plot(conn, learner_id, plot["slot"])
        withered.append({"slot": plot["slot"], "kind": plot["kind"], "saved": saved})
    return withered


def water(conn: sqlite3.Connection, learner_id: int, now: datetime) -> list[dict]:
    """Water the whole garden: every growing plant ripens one veggie.
    Returns the plants that ripened one ({"slot", "kind"})."""
    tend(conn, learner_id, now)
    ripened = []
    for plot in db.list_plots(conn, learner_id):
        ripe = plot["ripe"]
        if ripe < VEGGIES_PER_PLANT:
            ripe += 1
            ripened.append({"slot": plot["slot"], "kind": plot["kind"]})
        db.update_plot(conn, learner_id, plot["slot"], ripe, plot["picked"], now)
    return ripened


def plant(
    conn: sqlite3.Connection, learner_id: int, slot: int, now: datetime, rng: random.Random | None = None
) -> dict:
    """Spend a seed on an empty spot; the veggie kind is a surprise."""
    tend(conn, learner_id, now)
    if not 0 <= slot < SPOTS:
        raise GardenError("That spot isn't in the garden.")
    if any(p["slot"] == slot for p in db.list_plots(conn, learner_id)):
        raise GardenError("Something is already growing there.")
    if db.get_seed_balance(conn, learner_id) < 1:
        raise GardenError("You need a seed! Practice to earn one.")
    kind = (rng or random).choice(list(VEGGIES))
    db.add_seeds(conn, learner_id, -1, "plant", ref=f"slot:{slot}")
    db.plant_plot(conn, learner_id, slot, kind, now)
    return {"slot": slot, "kind": kind}


def pick(conn: sqlite3.Connection, learner_id: int, slot: int, now: datetime) -> dict:
    """Take every ripe veggie on one plant. A plant with nothing left to
    grow is cleared, freeing the spot."""
    tend(conn, learner_id, now)
    plot = next((p for p in db.list_plots(conn, learner_id) if p["slot"] == slot), None)
    if plot is None:
        raise GardenError("Nothing is growing there.")
    count = plot["ripe"] - plot["picked"]
    if count == 0:
        raise GardenError("Nothing is ripe yet. Practice to water it!")
    db.add_veggies(conn, learner_id, plot["kind"], count, "pick")
    if plot["ripe"] >= VEGGIES_PER_PLANT:
        db.clear_plot(conn, learner_id, slot)
    else:
        db.update_plot(conn, learner_id, slot, plot["ripe"], plot["ripe"], plot["watered_at"])
    return {"slot": slot, "kind": plot["kind"], "count": count}


def collect_basket(conn: sqlite3.Connection, learner_id: int, now: datetime) -> dict[str, int]:
    """Move everything in the basket into the veggie pile."""
    tend(conn, learner_id, now)
    basket = db.get_basket(conn, learner_id)
    if not basket:
        raise GardenError("The basket is empty.")
    for kind, count in basket.items():
        db.add_veggies(conn, learner_id, kind, count, "basket")
    db.empty_basket(conn, learner_id)
    return basket


def _plot_view(plot: dict) -> dict:
    return {
        "slot": plot["slot"],
        "kind": plot["kind"],
        "name": VEGGIES[plot["kind"]].name,
        "babies": VEGGIES_PER_PLANT - plot["ripe"],
        "ready": plot["ripe"] - plot["picked"],
        "picked": plot["picked"],
        "wilts_at": (plot["watered_at"] + WITHER_AFTER).isoformat(),
    }


def status(conn: sqlite3.Connection, learner_id: int, now: datetime) -> dict:
    """Everything the garden page (and the home tile) shows."""
    tend(conn, learner_id, now)
    by_slot = {p["slot"]: _plot_view(p) for p in db.list_plots(conn, learner_id)}
    spots = [by_slot.get(i) for i in range(SPOTS)]
    return {
        "spots": spots,
        "seeds": db.get_seed_balance(conn, learner_id),
        "ready": sum(s["ready"] for s in spots if s),
        "growing": sum(1 for s in spots if s),
        "basket": (basket := db.get_basket(conn, learner_id)),
        "basket_total": sum(basket.values()),
        "veggies": db.get_veggies(conn, learner_id),
        "names": {v.id: {"name": v.name, "plural": v.plural} for v in VEGGIES.values()},
    }
