"""Dev/release switches, in one place.

DEV_START_COINS: while developing, every learner gets this many free
coins once (a "dev_grant" ledger row), so the store can be explored
without hours of typing. SET TO 0 BEFORE RELEASE. The test suite turns it
off via the env var (tests/conftest.py) so coin math starts from zero.
"""

from __future__ import annotations

import os

DEV_START_COINS = int(os.environ.get("TYPING_TRAINER_DEV_START_COINS", "50000"))
