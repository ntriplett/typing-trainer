"""Aquariums (PLAN.md 11k): tanks you decorate yourself, then fill with fish.

A tank is a 75-gallon tank (TANK_W x TANK_H grid units, about 48" x 21")
that holds up to TANK_FISH fish. Everything that goes in it is sold in the
Pet Shop's Aquarium Supplies: backgrounds and substrates are bought once
and used in any tank; plants, rocks and decorations are bought one copy at
a time, wait in storage, and are placed (dragged, flipped, set in front of
or behind the fish) in a tank. Each item tells the fish what it is
(`sees`): somewhere to hide, to explore, to swim through, bubbles to play in.
Items are drawn by web/static/js/aquarium_items.js.
"""

from __future__ import annotations

from dataclasses import dataclass

from app import db
from app import pet_genes as g

TANK_PRICE = 400
TANK_SPOTS = 10
TANK_FISH = 10
TANK_W = 160
TANK_H = 70
SUBSTRATE_H = 8  # the substrate band at the bottom of the tank
LAYERS = ("back", "middle", "front")  # behind the fish .. in front of them
LOOK_KINDS = ("background", "substrate")  # bought once, used anywhere
PIECE_KINDS = ("plant", "rock", "decor")  # bought per copy, placed in tanks


@dataclass(frozen=True, slots=True)
class AquaItem:
    id: str
    name: str
    kind: str  # LOOK_KINDS or PIECE_KINDS
    price: int
    w: int = 0  # size in tank units (pieces)
    h: int = 0
    layer: str = "middle"  # where a newly placed copy goes
    sees: tuple[str, ...] = ()  # what fish make of it: hide, explore, through, bubbles


def _items(*items: AquaItem) -> dict[str, AquaItem]:
    return {i.id: i for i in items}


CATALOG: dict[str, AquaItem] = _items(
    # backgrounds
    AquaItem("bg_blue", "Deep Blue", "background", 0),
    AquaItem("bg_night", "Night Black", "background", 40),
    AquaItem("bg_stones", "River Stones", "background", 50),
    AquaItem("bg_sunset", "Sunset Glow", "background", 50),
    AquaItem("bg_coral", "Coral Mural", "background", 60),
    AquaItem("bg_roots", "Jungle Roots", "background", 60),
    # substrates
    AquaItem("sand", "Sand", "substrate", 0),
    AquaItem("gravel_mix", "Mixed Gravel", "substrate", 20),
    AquaItem("gravel_blue", "Blue Gravel", "substrate", 20),
    AquaItem("gravel_pink", "Pink Gravel", "substrate", 20),
    AquaItem("sand_white", "White Sand", "substrate", 30),
    AquaItem("sand_black", "Black Sand", "substrate", 30),
    AquaItem("pebbles", "River Pebbles", "substrate", 40),
    # plants
    AquaItem("grass", "Grass Strand", "plant", 10, 4, 18, "back", ("hide",)),
    AquaItem("kelp", "Kelp Strand", "plant", 10, 5, 44, "back", ("hide",)),
    AquaItem("moss_ball", "Moss Ball", "plant", 10, 6, 5, "front"),
    AquaItem("java_fern", "Java Fern", "plant", 20, 12, 16, "middle", ("hide",)),
    AquaItem("ludwigia", "Red Ludwigia", "plant", 20, 8, 26, "back", ("hide",)),
    AquaItem("sword", "Sword Plant", "plant", 30, 18, 28, "back", ("hide",)),
    AquaItem("lily", "Water Lily", "plant", 30, 16, 58, "back", ("hide",)),
    # rocks
    AquaItem("pebble", "Pebble", "rock", 10, 5, 3, "front"),
    AquaItem("flat_stone", "Flat Stone", "rock", 20, 14, 5, "middle"),
    AquaItem("slate", "Slate Stack", "rock", 40, 18, 16, "middle", ("explore",)),
    AquaItem("big_rock", "Big Rock", "rock", 50, 24, 14, "middle", ("explore",)),
    AquaItem("cave_rock", "Cave Rock", "rock", 80, 30, 18, "middle", ("hide", "explore")),
    # decorations
    AquaItem("diver", "Little Diver", "decor", 30, 8, 14, "middle", ("explore",)),
    AquaItem("clam", "Giant Clam", "decor", 30, 12, 7, "front", ("explore",)),
    AquaItem("bubbler", "Bubble Stone", "decor", 40, 6, 3, "middle", ("bubbles",)),
    AquaItem("chest", "Treasure Chest", "decor", 40, 14, 10, "middle", ("explore", "bubbles")),
    AquaItem("arch", "Stone Arch", "decor", 60, 30, 22, "middle", ("through", "explore")),
    AquaItem("castle", "Castle", "decor", 80, 26, 30, "back", ("hide", "explore")),
    AquaItem("ship", "Sunken Ship", "decor", 100, 48, 24, "back", ("hide", "explore")),
    AquaItem("driftwood", "Driftwood", "decor", 100, 50, 26, "middle", ("hide", "explore")),
)
STARTER_LOOK = {"background": "bg_blue", "substrate": "sand"}  # every player owns these


class AquaError(ValueError):
    """Kid-readable, like CareError."""


def _item(item_id: str) -> AquaItem:
    item = CATALOG.get(item_id)
    if item is None:
        raise AquaError("There's nothing like that in the shop.")
    return item


def owned_looks(conn, learner_id: int) -> set[str]:
    return db.list_aqua_owned(conn, learner_id) | set(STARTER_LOOK.values())


def tank_id(spot: int) -> str:
    return f"tank:{spot}"


def tank_spot(home: str | None) -> int | None:
    return int(home.split(":")[1]) if home and home.startswith("tank:") else None


def tanks(conn, learner_id: int) -> list[dict]:
    """A player's tanks; everyone starts with one empty basic tank."""
    found = db.list_tanks(conn, learner_id)
    if not found:
        db.add_tank(conn, learner_id, 0, "Tank 1", STARTER_LOOK["background"], STARTER_LOOK["substrate"])
        found = db.list_tanks(conn, learner_id)
    return found


def _tank(conn, learner_id: int, spot: int) -> dict:
    found = next((t for t in tanks(conn, learner_id) if t["spot"] == spot), None)
    if found is None:
        raise AquaError("There's no tank there yet.")
    return found


# --- buying (the Pet Shop's Aquarium Supplies) ---------------------------------------


def _pay(conn, learner_id: int, cost: int, what: str, ref: str) -> None:
    if not cost:
        return
    balance = db.get_coin_balance(conn, learner_id)
    if balance < cost:
        raise AquaError(f"You need {cost - balance:,} more coins for the {what}.")
    db.add_coins(conn, learner_id, -cost, "purchase", ref=ref)


def buy_tank(conn, learner_id: int) -> dict:
    """A new tank, in the first empty spot, with the starter look."""
    taken = {t["spot"] for t in tanks(conn, learner_id)}
    spot = next((s for s in range(TANK_SPOTS) if s not in taken), None)
    if spot is None:
        raise AquaError("Your Aquarium is full!")
    _pay(conn, learner_id, TANK_PRICE, "tank", "tank")
    name = f"Tank {spot + 1}"
    db.add_tank(conn, learner_id, spot, name, STARTER_LOOK["background"], STARTER_LOOK["substrate"])
    return {"spot": spot, "name": name}


def buy_item(conn, learner_id: int, item_id: str) -> dict:
    """A look is yours for good; a piece is one more copy in storage."""
    item = _item(item_id)
    if item.kind in LOOK_KINDS:
        if item.id in owned_looks(conn, learner_id):
            raise AquaError(f"You already have {item.name}!")
        _pay(conn, learner_id, item.price, item.name, f"aqua:{item.id}")
        db.add_aqua_owned(conn, learner_id, item.id)
        return {"item": item.id}
    _pay(conn, learner_id, item.price, item.name, f"aqua:{item.id}")
    return {"item": item.id, "piece": db.add_tank_piece(conn, learner_id, item.id, item.layer)}


def supplies_state(conn, learner_id: int) -> dict:
    """The shop's view: every item, what you own, and your tanks."""
    owned = owned_looks(conn, learner_id)
    copies: dict[str, int] = {}
    for piece in db.list_tank_pieces(conn, learner_id):
        copies[piece["item_id"]] = copies.get(piece["item_id"], 0) + 1
    return {
        "items": [
            {"id": i.id, "name": i.name, "kind": i.kind, "price": i.price, "w": i.w, "h": i.h, "sees": list(i.sees),
             "owned": i.id in owned if i.kind in LOOK_KINDS else copies.get(i.id, 0)}
            for i in CATALOG.values()
        ],
        "tank_price": TANK_PRICE,
        "tanks": len(tanks(conn, learner_id)),
        "spots": TANK_SPOTS,
    }


# --- decorating a tank ----------------------------------------------------------------


def _piece(conn, learner_id: int, piece_id: int) -> dict:
    piece = next((p for p in db.list_tank_pieces(conn, learner_id) if p["id"] == piece_id), None)
    if piece is None:
        raise AquaError("You don't have that piece.")
    return piece


def _clamp(item: AquaItem, x: float, y: float) -> tuple[float, float]:
    """Keep a piece inside the glass: x its left edge, y its bottom."""
    x = min(max(x, 0), TANK_W - item.w)
    y = min(max(y, item.h), TANK_H)
    return round(x, 1), round(y, 1)


def place(conn, learner_id: int, piece_id: int, spot: int, x: float | None = None, y: float | None = None) -> None:
    """Put a piece from storage (or another tank) into a tank."""
    _tank(conn, learner_id, spot)
    piece = _piece(conn, learner_id, piece_id)
    item = _item(piece["item_id"])
    x = (TANK_W - item.w) / 2 if x is None else x
    y = TANK_H - SUBSTRATE_H / 2 if y is None else y
    x, y = _clamp(item, x, y)
    db.update_tank_piece(conn, learner_id, piece_id, tank=spot, x=x, y=y)


def move(conn, learner_id: int, piece_id: int, x: float, y: float, layer: str | None = None, flip: bool | None = None) -> None:
    piece = _piece(conn, learner_id, piece_id)
    if piece["tank"] is None:
        raise AquaError("Put it in a tank first.")
    fields = dict(zip(("x", "y"), _clamp(_item(piece["item_id"]), x, y), strict=True))
    if layer is not None:
        if layer not in LAYERS:
            raise AquaError("Pieces go in the back, the middle, or the front.")
        fields["layer"] = layer
    if flip is not None:
        fields["flip"] = int(flip)
    db.update_tank_piece(conn, learner_id, piece_id, **fields)


def store(conn, learner_id: int, piece_id: int) -> None:
    """Take a piece out of its tank, back to storage."""
    _piece(conn, learner_id, piece_id)
    db.update_tank_piece(conn, learner_id, piece_id, tank=None)


def set_look(conn, learner_id: int, spot: int, background: str | None = None, substrate: str | None = None) -> None:
    _tank(conn, learner_id, spot)
    owned = owned_looks(conn, learner_id)
    fields = {}
    for kind, item_id in (("background", background), ("substrate", substrate)):
        if item_id is None:
            continue
        if _item(item_id).kind != kind:
            raise AquaError(f"That isn't a {kind}.")
        if item_id not in owned:
            raise AquaError(f"Buy {CATALOG[item_id].name} at the Pet Shop first.")
        fields[kind] = item_id
    if fields:
        db.update_tank(conn, learner_id, spot, **fields)


def rename(conn, learner_id: int, spot: int, name: str) -> None:
    _tank(conn, learner_id, spot)
    name = " ".join(name.split())
    if not name or len(name) > 20:
        raise AquaError("A tank name needs 1 to 20 letters.")
    db.update_tank(conn, learner_id, spot, name=name)


# --- fish -----------------------------------------------------------------------------


def set_fish_tank(conn, learner_id: int, pet_id: int, spot: int | None) -> None:
    """Move a fish into a tank, or back to the Care Center (spot None)."""
    pet = db.get_v3_pet(conn, learner_id, pet_id)
    if pet is None:
        raise AquaError("You don't have that pet.")
    if pet["species"] != "fish":
        raise AquaError("Only fish live in tanks!")
    if spot is not None:
        tank = _tank(conn, learner_id, spot)
        living = [p for p in db.list_v3_pets(conn, learner_id) if p["home"] == tank_id(spot) and p["id"] != pet_id]
        if len(living) >= TANK_FISH:
            raise AquaError(f"{tank['name']} is full ({TANK_FISH} fish).")
    db.update_v3_pet(conn, learner_id, pet_id, home=tank_id(spot) if spot is not None else None)


# --- views ---------------------------------------------------------------------------


def _fish_view(pet: dict) -> dict:
    return {"id": pet["id"], "name": pet["name"], "species": pet["species"], "growth": pet["growth"],
            "genes": g.resolve(pet["genes"])}


def _tank_view(tank: dict, pieces: list[dict], pets: list[dict]) -> dict:
    return {
        **tank,
        "pieces": [p for p in pieces if p["tank"] == tank["spot"]],
        "fish": [_fish_view(p) for p in pets if p["home"] == tank_id(tank["spot"])],
        "capacity": TANK_FISH,
    }


def _items_view() -> dict:
    return {i.id: {"name": i.name, "kind": i.kind, "w": i.w, "h": i.h, "sees": list(i.sees)} for i in CATALOG.values()}


def hall(conn, learner_id: int) -> dict:
    """The Aquarium hall: all TANK_SPOTS stands, a tank or None."""
    pieces = db.list_tank_pieces(conn, learner_id)
    pets = db.list_v3_pets(conn, learner_id)
    by_spot = {t["spot"]: t for t in tanks(conn, learner_id)}
    return {
        "spots": [_tank_view(by_spot[s], pieces, pets) if s in by_spot else None for s in range(TANK_SPOTS)],
        "size": {"w": TANK_W, "h": TANK_H, "substrate": SUBSTRATE_H},
        "items": _items_view(),
    }


def tank_state(conn, learner_id: int, spot: int) -> dict:
    """One tank, plus what's in storage and which looks you own (for Decorate)."""
    tank = _tank(conn, learner_id, spot)
    pieces = db.list_tank_pieces(conn, learner_id)
    pets = db.list_v3_pets(conn, learner_id)
    return {
        "tank": _tank_view(tank, pieces, pets),
        "storage": [p for p in pieces if p["tank"] is None],
        "looks": sorted(owned_looks(conn, learner_id)),
        "items": _items_view(),
        "waiting_fish": [_fish_view(p) for p in pets if p["species"] == "fish" and not p["home"]],
        "size": {"w": TANK_W, "h": TANK_H, "substrate": SUBSTRATE_H},
        "layers": list(LAYERS),
    }
