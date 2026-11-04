"""Dev/release switches, in one place.

DEV_MODE: the labs and free coins exist only with TYPING_TRAINER_DEV=1, which
the dev server and the tests set and an install never does.

DEV_START_COINS: in dev mode, every learner gets this many free coins once (a
"dev_grant" ledger row), so the store can be explored without hours of typing.
The test suite turns it off via the env var (tests/conftest.py) so coin math
starts from zero.
"""

from __future__ import annotations

import os

DEV_MODE = os.environ.get("TYPING_TRAINER_DEV") == "1"
DEV_START_COINS = int(os.environ.get("TYPING_TRAINER_DEV_START_COINS", "50000")) if DEV_MODE else 0

# Wanderpaw days normally cost arcade tokens. On: anyone can start one (the test suite,
# which sets it in tests/conftest.py).
WANDER_FREE_DAYS = os.environ.get("TYPING_TRAINER_WANDER_FREE_DAYS") == "1"

# What revealing the keyboard-with-hands hint costs, once per short lesson.
KEYBOARD_HINT_PRICE = 10
