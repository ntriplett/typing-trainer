# Typing Trainer

A local, browser-based touch-typing tutor built to teach a 9-year-old to type, in 15-minute
daily sessions, up to ~30 WPM across the full keyboard.

See [`ProjectPlan.md`](ProjectPlan.md) for the original brief and [`PLAN.md`](PLAN.md) for the
detailed design (architecture, data model, skill model, scheduler, module contract, test
strategy, and build order).

## Status

Early scaffolding — see PLAN.md Section 10 for the build order. Not yet runnable.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pytest
```
