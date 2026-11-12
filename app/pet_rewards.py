"""Reward pets: a free pet, rolled at random, for learning certain keys, so
a new player has a pet of each Wanderpaw type early on. Each one waits
wrapped up at the Pet Shop like a grown-up's gift (app/pet_gift.py), from
the Pet Shop, with a note saying what it's for.

Each reward is given once. grant() is safe to call any time: players who
learned the keys before rewards existed get theirs the next time it runs.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app import db, lessons
from app import pet_genes as g

GIVER = "the Pet Shop"


@dataclass(frozen=True, slots=True)
class Reward:
    id: str
    species: str
    needs: str  # keys to learn, in teaching order (skill_model.KEY_ORDER)


REWARDS: tuple[Reward, ...] = (
    Reward("first_four", "bunny", "fjdk"),
    Reward("top_two", "sheep", "ru"),
    Reward("top_six", "fox", "rueiwo"),
    Reward("bottom_four", "turtle", "vmc,"),
)


def _setting(reward: Reward) -> str:
    return f"reward_pet_{reward.id}"


def note(reward: Reward) -> str:
    keys = [k.upper() for k in reward.needs]
    listed = ", ".join(keys[:-1]) + " and " + keys[-1]
    return f"For learning {listed}. All your hard work is paying off!"


def grant(conn, learner_id: int, rng: random.Random | None = None) -> list[dict]:
    """Wrap up every reward earned and not given yet. Returns the new ones."""
    taught = lessons.taught_keys(conn, learner_id)
    rng = rng or random.Random()
    given = []
    for reward in REWARDS:
        if not set(reward.needs) <= taught or db.get_setting(conn, learner_id, _setting(reward)) is not None:
            continue
        unlocked = db.list_pet_color_unlocks(conn, learner_id)
        genes = g.shop_roll(reward.species, unlocked, g.new_seed(rng))
        name = g.species_name(reward.species)
        gift_id = db.add_pet_gift(conn, learner_id, GIVER, name, genes, note(reward))
        db.set_setting(conn, learner_id, _setting(reward), str(gift_id))
        given.append({"id": gift_id, "species": reward.species, "name": name})
    return given
