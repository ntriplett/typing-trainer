"""Suite-wide setup. Runs before any app module is imported."""

import os

# Dev-mode free coins (app/config.py) would make every coin assertion off
# by 50K; tests start from zero. Set in the environment (not just patched)
# so e2e tests' server subprocesses inherit it too.
os.environ["TYPING_TRAINER_DEV_START_COINS"] = "0"
