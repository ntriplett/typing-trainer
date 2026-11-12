"""Sparring: a quick match between two of your own pets, in a town's ring,
so a new pet can catch up with the party.

The higher-level pet teaches; the lower one learns. Only the learner gains
XP: RATE of its next level for each level between them, up to a whole
level a spar. A big gap is far faster than battles; a gap of a level or two
is slower. Pets of the same level have nothing to teach each other.

Each spar costs both pets COST of their full energy, about what a battle
does, and never their last bit of it. Energy is the only limit.

A spar plays as a few shots each way (SHOTS); the save keeps nothing of it
but the XP and energy.
"""

from __future__ import annotations

from app.wanderpaw import pets as wp

RATE = 0.07  # of the learner's next level, for each level of difference
MOST = 1.0  # levels a spar can give
COST = 0.10  # of each pet's full energy
SHOTS = 3  # each way, in the animation


def gap(teacher: dict, learner: dict) -> int:
    return teacher["level"] - learner["level"]


def xp(teacher: dict, learner: dict) -> int:
    """XP the learner gains from one spar (0: nothing to learn)."""
    levels = gap(teacher, learner)
    step = wp.progress(learner["xp"])
    if levels <= 0 or step is None:
        return 0
    return max(1, round(step[1] * min(MOST, RATE * levels)))


def cost(member: dict) -> int:
    """Energy one spar takes from this pet."""
    return max(1, round(member["energy"] * COST))


def can_afford(member: dict, energy_now: int) -> bool:
    """A spar never wears a pet out."""
    return energy_now > cost(member)


def pairs(team: list[dict], energy: list[int]) -> list[tuple[int, int, int]]:
    """(teacher place, learner place, XP) for each spar on offer, best first:
    real pets only, the learner lower, both with the energy to spare."""
    out = []
    for t, teacher in enumerate(team):
        for l, learner in enumerate(team):
            if t == l or teacher["id"] is None or learner["id"] is None:
                continue
            gain = xp(teacher, learner)
            if gain and can_afford(teacher, energy[t]) and can_afford(learner, energy[l]):
                out.append((t, l, gain))
    return sorted(out, key=lambda p: (-p[2], p[0], p[1]))
