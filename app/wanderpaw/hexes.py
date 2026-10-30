"""Hex grid math for Wanderpaw's maps, big and small (PLAN.md 11n).

Pointy-top hexes in axial coordinates (q, r): q runs east, r runs
south-east. A hexagonal map of radius R is every hex within R steps of
(0, 0). Directions are numbered 0..5 starting east and going
counter-clockwise, so the opposite of direction d is (d + 3) % 6.
"""

from __future__ import annotations

import math

Hex = tuple[int, int]

# E, NE, NW, W, SW, SE
DIRECTIONS: tuple[Hex, ...] = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))


def add(a: Hex, b: Hex) -> Hex:
    return (a[0] + b[0], a[1] + b[1])


def neighbor(h: Hex, direction: int) -> Hex:
    return add(h, DIRECTIONS[direction % 6])


def neighbors(h: Hex) -> list[Hex]:
    return [add(h, d) for d in DIRECTIONS]


def direction_to(a: Hex, b: Hex) -> int:
    """The direction from a to its neighbor b (ValueError if not neighbors)."""
    return DIRECTIONS.index((b[0] - a[0], b[1] - a[1]))


def distance(a: Hex, b: Hex) -> int:
    dq, dr = a[0] - b[0], a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def ring(center: Hex, radius: int) -> list[Hex]:
    """The hexes exactly `radius` steps away, walking once around."""
    if radius == 0:
        return [center]
    out = []
    h = add(center, (DIRECTIONS[4][0] * radius, DIRECTIONS[4][1] * radius))
    for d in range(6):
        for _ in range(radius):
            out.append(h)
            h = neighbor(h, d)
    return out


def spiral(center: Hex, radius: int) -> list[Hex]:
    """Every hex within `radius`, center first, ring by ring."""
    return [h for k in range(radius + 1) for h in ring(center, k)]


def edge_key(a: Hex, b: Hex) -> tuple[Hex, Hex]:
    """One key for the edge between two neighbors, whichever way round."""
    return (a, b) if a <= b else (b, a)


def to_pixel(h: Hex, size: float = 1.0) -> tuple[float, float]:
    """Center of a pointy-top hex with corner radius `size` (y grows down)."""
    q, r = h
    return (size * math.sqrt(3) * (q + r / 2), size * 1.5 * r)


def angle(h: Hex) -> float:
    """Compass angle of the hex's center around (0, 0), in degrees 0..360
    (0 east, counter-clockwise, like DIRECTIONS)."""
    x, y = to_pixel(h)
    return math.degrees(math.atan2(-y, x)) % 360
