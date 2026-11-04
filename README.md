# Typing Trainer

A local, browser-based touch-typing tutor built to teach a 9-year-old to type, in 15-minute
daily sessions, up to ~30 WPM across the full keyboard.

See [`ProjectPlan.md`](ProjectPlan.md) for the original brief and [`PLAN.md`](PLAN.md) for the
detailed design (architecture, data model, skill model, scheduler, module contract, test
strategy, and build order).

## Status

Runnable: `python launcher/start.py` starts the server and opens the app. See PLAN.md Section 10 for
the build order and PLAN.md Section 11b for known issues.

## Install on Windows

1. Download **Install-TypingTrainer.cmd** from the
   [latest release](https://github.com/ntriplett/typing-trainer/releases/latest) and double-click it.
   (SmartScreen may warn about a downloaded script: *More info* -> *Run anyway*.) No admin needed;
   it takes a minute the first time.
2. It adds a **Typing Trainer** shortcut to the desktop and Start menu. The app opens in its own
   Chrome window (Edge if there's no Chrome); closing the window stops it.
3. The first time it opens, a grown-up chooses a 4-number PIN. It guards **For grown-ups** (in the
   profile menu, top right): the current player's daily goal, practice-vs-learn slider and updates.
   Forgot it? The page shows which file to delete, and you'll choose a new one next time.
4. Updates: when a newer release exists, the home page says so and **For grown-ups** has an
   *Update now* button. The app closes, updates, and reopens. Running the installer again also
   updates (or repairs) it.

Everything lives in `%LOCALAPPDATA%\TypingTrainer`. Progress is in `data\typing.db`, apart from
the program, and is copied to `data\backups\` before every update. To move progress from another
computer, close the app and copy a `typing.db` over that one. Uninstall: delete the folder and the
two shortcuts.

### Releasing

Bump `version` in `pyproject.toml`, commit, then `git tag v0.2.0 && git push origin v0.2.0`. The
release workflow runs the tests and publishes the zip plus installer; installed copies see it
within the hour. If dependencies change, run `uv lock` and commit `uv.lock` (installs use it as-is).

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
playwright install chromium   # one-time, for the e2e test suite (tests/e2e/)
pytest
```

## Developing

Run with `TYPING_TRAINER_DEV=1` for the labs (start at `/labs`) and free starting coins:

```
TYPING_TRAINER_DEV=1 .venv/bin/python -m uvicorn app.main:app --port 8420
```

Without it, as in an install, they don't exist. The tests turn it on themselves.

## License

All rights reserved; see [LICENSE](LICENSE). The fonts have their own license, in their folder.
