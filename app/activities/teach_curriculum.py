"""The order keys are taught in: the intro, then two keys per lesson in
skill_model.KEY_ORDER (home row, top row, bottom row, numbers), with
capitals slotted in after the letters and before the numbers. Each
lesson's "known" keys are everything taught before it.
"""

from __future__ import annotations

from app.skill_model import KEY_ORDER

INTRO_ID = "teach_intro_home_row_v1"
PAIR_ID = "teach_key_pair_v1"
CAPS_INTRO_ID = "teach_caps_intro_v1"
CAPS_ID = "teach_caps_v1"

# Four fingers of one hand on one row, then the pointer-finger stretch
# keys -- every group uses a single Shift (the other hand's).
CAPS_GROUPS = ("asdf", "qwer", "zxcv", "hjkl", "uiop", "gtb", "ynm")

_TAUGHT_KEYS = [k for k in KEY_ORDER if k != " "]
_GROUPS = (("Home row", "asdfghjkl;"), ("Top row", "qwertyuiop"), ("Bottom row", "zxcvbnm,./"), ("Numbers", "1234567890"))


def _group(key: str) -> str:
    return next(name for name, keys in _GROUPS if key in keys)


def known_before(keys: list[str]) -> list[str]:
    """Keys taught before the earliest of `keys` (plus space), never `keys` themselves."""
    first = min(_TAUGHT_KEYS.index(k) for k in keys)
    return [" "] + [k for k in _TAUGHT_KEYS[:first] if k not in keys]


def lessons() -> list[dict]:
    out = [{"module": INTRO_ID, "keys": "", "group": "Start here", "title": "Hands on home"}]
    for i in range(0, len(_TAUGHT_KEYS), 2):
        pair = _TAUGHT_KEYS[i : i + 2]
        if pair[0] == "1":
            out += _caps_lessons()
        out.append(
            {
                "module": PAIR_ID,
                "keys": "".join(pair),
                "group": _group(pair[0]),
                "title": " and ".join(k.upper() for k in pair),
            }
        )
    return out


def _caps_lessons() -> list[dict]:
    out = [{"module": CAPS_INTRO_ID, "keys": "", "group": "Capitals", "title": "Big letters"}]
    for letters in CAPS_GROUPS:
        out.append({"module": CAPS_ID, "keys": letters, "group": "Capitals", "title": " ".join(letters.upper())})
    return out
