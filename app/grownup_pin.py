"""The For Grown-ups page's PIN: 4 digits, chosen the first time the app opens.

It keeps a child out of the settings; it isn't a security boundary (see the note on
the player cookie in main.py). It lives in its own small file beside the database,
so a forgotten PIN is fixed by deleting that file and choosing a new one. Only a
salted hash is kept.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path

FILE_NAME = "grownup_pin.json"
ROUNDS = 100_000
COOKIE_SECONDS = 30 * 60


class PinError(ValueError):
    """Readable by whoever's typing it."""


def path_for(db_path: Path) -> Path:
    return Path(db_path).parent / FILE_NAME


def _hash(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), ROUNDS).hex()


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def is_set(path: Path) -> bool:
    return _load(path) is not None


def set_pin(path: Path, pin: str) -> None:
    if not re.fullmatch(r"[0-9]{4}", pin or ""):
        raise PinError("A PIN is 4 numbers.")
    salt = secrets.token_hex(16)
    path.write_text(json.dumps({"salt": salt, "hash": _hash(pin, salt)}))


def check(path: Path, pin: str) -> bool:
    saved = _load(path)
    return bool(saved) and hmac.compare_digest(_hash(pin or "", saved["salt"]), saved["hash"])


def pass_for(path: Path) -> str | None:
    """What the unlocked cookie holds: changes with the PIN, so a new PIN ends old ones."""
    saved = _load(path)
    return hashlib.sha256(f"unlocked:{saved['hash']}".encode()).hexdigest() if saved else None
