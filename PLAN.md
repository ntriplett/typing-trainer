# Touch Typing Trainer — Project Plan

Status: engine design locked; game roster/theme/rewards deferred until after first playable build.

## 1. Goals (from ProjectPlan.md)

- Teach a 9-year-old touch typing in 15 min/day sessions, scaling to 30 WPM full-keyboard.
- Runs locally on Windows, launched from a single desktop icon, opens in a browser.
- Tracks progress durably across sessions, restarts, and browser cache clears.
- Has teaching, practice, games, and evaluation; adapts dynamically to weak skills.
- Visually appealing/fun for a 9-year-old.
- Has a detailed performance analysis page.
- Modular, well-tested (unit/module/integration/e2e), versioned in git/GitHub, tests green before every commit.
- Grounded in actual typing-pedagogy research (see Section 2).

## 2. Research basis

- **Dosage**: 15–30 min/day is the right session length for elementary kids; ~25–30 cumulative hours
  to reach solid fluency (roughly 4–6 months at 15 min/day). 30 WPM is a realistic end state, not an
  early milestone — grade 5–6 norms are ~15–25 WPM.
- **Accuracy gates speed**: accuracy relies on declarative memory, speed on procedural memory — they
  are trained differently. Hold ~95% accuracy before rewarding speed increases; errors build competing
  motor patterns that are expensive to unlearn later.
- **Adaptive per-key modeling** (keybr-style) outperforms fixed drill sequences:
  - Each key has a confidence score = `targetSpeed / EMA(timeToType)`, EMA α≈0.1, computed only from
    error-free keystrokes.
  - A new key unlocks once all currently-active keys hit confidence ≥ 1.0.
  - Known weaknesses in the reference design we will fix: no minimum sample count (a key can "master"
    off one lucky attempt) and no accuracy floor (a key can be fast but consistently wrong). We add both.
  - Practice text uses generated pseudo-words from the active key set, not real words, so the fingers
    respond to letter sequences instead of pattern-matching whole words from memory.
- **Key introduction order**: home-row first (f, j, d, k, s, l, a, ;, then reaches), then top row, then
  bottom row, then numbers/symbols — better for building finger discipline in a beginner than pure
  letter-frequency order.
- **Technique before throughput**: correct finger assignment and no looking at the keyboard matter more
  early on than raw speed; no competitive comparison to other kids — progress is measured against his
  own history only.

## 3. Architecture

**Stack**: Python (FastAPI) backend + SQLite + browser front-end (HTML/CSS/vanilla JS or small TS build).
Decided because the hard requirement — progress must survive browser cache clears and PC restarts —
rules out browser-only storage (localStorage/IndexedDB) as the system of record. SQLite is the durable
store; the browser is purely a view.

```
Desktop icon (.vbs/.bat, no console window)
  -> health-check http://127.0.0.1:<port>/health
     - already running -> focus/open browser tab, exit
     - not running -> acquire lockfile, start uvicorn in background,
                       wait for health check, open browser tab
Browser (single page) <--REST/JSON--> FastAPI app <--> SQLite (typing.db)
```

- **Single-instance guarantee**: lockfile + health-check in the launcher script, so double-clicking
  twice never spawns two servers.
- **No repeated admin prompt**: one-time setup installs the Python venv/deps (may need elevation once);
  day-to-day launches just run a local script and bind a localhost port — no elevation needed.
- **Packaging**: plain venv + setup script for now (fastest to iterate on). Bundle into a standalone
  exe (PyInstaller) later, once the app is stable — packaging is last-mile, not a design concern.

## 4. Data model (SQLite)

Draft schema — refined as we build, but this is the shape:

- `learner` — id, name, created_at (single learner for v1, but keyed so multi-learner isn't a rewrite).
- `key_stat` — learner_id, key (physical key/char), ema_time_ms, confidence, accuracy_rolling,
  sample_count, unlocked_at, mastered_at.
- `session` — id, learner_id, started_at, ended_at, planned_phases (json), completed_phases (json).
- `session_event` — session_id, phase (warmup/teach/practice/eval/game), activity_id, started_at,
  ended_at, summary_stats (json: wpm, accuracy, error keys).
- `keystroke_log` — session_event_id, seq, expected_char, typed_char, correct (bool), latency_ms,
  timestamp. (Raw log — this is what key_stat and the analysis page are built from.)
- `activity_catalog` — static-ish registry of lesson/game/eval modules and their metadata
  (id, type, display_name, min_level, params schema).
- `streak` — learner_id, current_streak_days, longest_streak, last_active_date.

Keystroke-level logging is kept raw and append-only; all aggregates (confidence, accuracy, WPM) are
derived/recomputable from it, so we can change the skill-model formula later without losing history.

## 5. Skill model (the adaptive core)

- Per key: EMA of error-free keystroke latency, confidence = target/EMA, **plus** a rolling accuracy
  (last N attempts) and a minimum sample count before a key can be considered "mastered."
- A key is "solid" only when: confidence ≥ 1.0 AND rolling accuracy ≥ 0.95 AND sample_count ≥ threshold.
- Active key set expands home-row-first as keys become solid; never contracts automatically, but a key
  that regresses below an accuracy floor gets flagged as "needs review" and the scheduler will
  re-surface it in warmup/practice even if nominally unlocked.
- This model is the single source of truth the scheduler queries to decide: which keys need warmup,
  whether a new key/teach topic is ready, and whether skills are solid enough to run an eval today.

## 6. Session scheduler (the daily arc)

Fixed phase order, dynamic content per phase, confirmed with you:

1. **Warmup** (~2 min) — drills the 2-4 currently weakest keys (lowest confidence/accuracy).
2. **Teach/Practice** (~9 min) — if a new key is ready to introduce, a short teach activity runs first,
   then practice folds it in with the active set. If no new key is ready, this phase is pure adaptive
   practice. Whether an **evaluation** runs at the end of this block is a scheduler decision (e.g. not
   every day — only when there's enough fresh practice on the active set to make a check meaningful).
3. **Games** (~4-5 min) — scheduler filters the game roster by what would reinforce current weak spots,
   presents a pick of 2-4 to the child, child chooses.

The scheduler is a pure function of (skill model state, recent session history) -> a session plan
(ordered list of phase/activity choices). This is the key seam for testability: given a fixed skill
state, the scheduler's output is deterministic and unit-testable without any UI or timing involved.

### 6a. Pre-session config and adaptive content length

Before a session starts, the learner picks (PLAN.md's slider screen):
- **duration** (15-30 min) — scales the total time budget every phase's share comes out of.
- **learn vs. practice** — gates whether `teach` runs at all (off near the "practice" extreme) and
  scales its time share (bigger share = more repetition on the new-ish key = "push harder").
- **focus vs. general** — sizes the key pool `practice` draws from: the full active set at "general",
  shrinking toward just the weakest few at "focus" (reuses the warmup recommender with a bigger `n`).

This produces a `SessionSkeleton`: the phase sequence, each phase's time budget, and its key focus —
but **no typing content yet**. Content is generated lazily, one step at a time, right before that step
starts, sized to the session's *current* estimated WPM (starts from the learner's historical average,
then blends in each completed step's real WPM). That's what lets a later step's content length adapt
to how fast today is actually going, without the earlier, already-decided phase durations changing.

### 6b. Short sub-lessons, key states, and the focus/allowed split

Each step is a **1-2 minute sub-lesson**, not one long block per phase kind — a 15-minute session ends
up with roughly 10 of them, built one at a time by a priority rule (eval if ready → teach if there's
room and it's been a couple of steps → game if it's been a few steps → practice otherwise), so the
sequence can be anything from "warmup, teach, practice, teach, game, practice, eval, practice, game" on
up, not a fixed shape.

Every key has a live **state**, derived from its stats, not stored separately:
- **untaught** — never introduced
- **teaching** — introduced, but not enough attempts yet to trust an accuracy reading
- **learning** — enough attempts to trust it, but accuracy below 80%
- **learned** — accuracy at or above 80%

(This is a lighter, separate bar from `is_mastered()`/`mastered_at`, which still gates *when the next
key ever gets introduced* across sessions. The 4 states are for *this session's* lesson-building.)

Every activity gets **two key pools**, not one: `focus_keys` (what this step should actively work on —
new or weak keys) and `allowed_keys` (everything introduced so far, safe as filler). A lesson never
draws a character from outside `allowed_keys` — "it shouldn't use any letters in other lessons that
weren't taught yet." Each module mixes the two in its own ratio: teach is ~100% focus (one new key at
a time, blocked pattern, ignoring allowed entirely); warmup leans 75% focus / 25% allowed; practice is
balanced 50/50; eval leans 70% allowed / 30% focus (a broad check, not another drill on the newest key);
game is 60% allowed / 40% focus. Within one plan, once a teach step is inserted its key is immediately
added to the *allowed* pool for every subsequent step — so a practice step right after teaching `d` can
actually use `d`, and a later teach step targets the next new key instead of repeating the same one.

## 7. Module contract (for modularity requirement)

Every lesson, practice drill, game, and evaluation is a self-contained module implementing one interface
(as actually built in `app/activities/base.py`, Section 6b's `focus_keys`/`allowed_keys` split):

```python
class Activity(Protocol):
    id: str
    kind: Kind  # "warmup" | "teach" | "practice" | "eval" | "game"
    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool: ...
    def generate(
        self, focus_keys: list[str], allowed_keys: list[str], duration_s: int,
        rng: random.Random | None = None, chars_per_second: float = 2.0,
    ) -> ActivityContent: ...
    def score(self, content: ActivityContent, keystrokes: list[KeystrokeEvent]) -> ActivityResult: ...
```

- The scheduler only ever talks to this interface — it never knows the internals of a specific game.
- New activities are added by registering a module in `app/activities/__init__.py`'s `REGISTRY`; nothing
  else changes. (Experimental/demo variants, like the 3 teach-demo modules in Section 6b, are registered
  separately in their own demo registry instead, so they can't be picked up by the live scheduler.)
- `ActivityContent` can optionally carry `micro_steps` (a list of plain dicts) for a structured
  multi-part lesson instead of one flat prompt — `None` for every ordinary flat-prompt activity.
- Front-end renders generically from `ActivityContent`'s declared shape (flat prompt vs. `micro_steps`,
  `kind`, etc.).

## 8. Test strategy

- **Unit**: skill-model math (confidence/EMA/unlock logic), scheduler decision logic, each activity's
  `generate`/`score`.
- **Module**: each activity tested in isolation with synthetic keystroke streams (e.g., "80% accuracy
  on these keys produces this confidence delta").
- **Integration**: FastAPI endpoints against a real (temp) SQLite DB — session lifecycle, event logging.
- **End-to-end**: Playwright driving the actual browser UI through one full mock session.
- Tests run locally before every commit; CI (GitHub Actions) runs the same suite on push as the backstop.

## 9. Repo structure (initial)

```
typing/
  app/
    main.py              # FastAPI app, routes
    db.py                # SQLite access layer
    models.py            # dataclasses / pydantic schemas
    skill_model.py        # confidence/EMA/unlock logic
    scheduler.py          # session planning
    activities/
      __init__.py         # registry
      teach_home_row.py
      practice_pseudowords.py
      eval_timed_test.py
      game_falling_letters.py   # first proof-of-concept game
  web/
    index.html
    static/ (css/js)
  launcher/
    start.vbs            # desktop-icon target
    start.py             # health-check + spawn + open browser
  tests/
    unit/
    integration/
    e2e/
  PLAN.md
  ProjectPlan.md
  README.md
  requirements.txt / pyproject.toml
  .github/workflows/test.yml
```

## 10. Build order (incremental, test-at-each-step)

1. Repo skeleton + GitHub remote + CI stub (test workflow that runs `pytest`, even with zero tests).
2. SQLite schema + data layer, with unit/integration tests.
3. Skill model (confidence/EMA/unlock/accuracy floor) — pure logic, fully unit-tested, no UI yet.
4. Scheduler — pure function over skill-model state, unit-tested with synthetic states.
5. One activity end-to-end: a home-row teach/practice module + minimal browser UI that can run a real
   typed session and log keystrokes. This is the first walking skeleton — launcher, server, DB, one
   activity, all wired together and testable by actually typing.
6. One game end-to-end (simple — e.g. falling letters/words using the active key set) to prove the game
   contract and that the scheduler's game-phase picker works.
7. Analysis page (reads keystroke_log/session tables, charts WPM/accuracy/weak-key trends over time).
8. Launcher polish (single-instance lock, desktop shortcut creation step).
9. Only after 1-6 are working and tested: expand game roster, add remaining teach topics for top/bottom
   rows and symbols, visual theme/art pass, reward economy (streaks, badges, etc.) — in collaboration
   with your son on what he actually wants.

## 11. Deferred (by design, per your decision)

- Full game roster (beyond the one proof-of-concept game).
- Visual theme, character/mascot, art direction, graphics/UX polish (reward animations, etc.).
- Reward economy details (badges, streak bonuses, unlockables).
- Exact eval format/frequency tuning — start simple, tune once real data exists.
- Exe packaging of the launcher.

### 11a. Keeping the graphics door open

The look stays plain/functional for now, but the architecture must not block a later visual pass:

- Front-end is a normal static HTML/CSS/JS page talking to JSON endpoints — nothing here prevents
  dropping in a canvas/sprite library (e.g. PixiJS, Phaser) or CSS animation libraries later; it's an
  additive change to `web/static/`, not a rewrite.
- `web/static/assets/` reserved now as the home for future art/sound/sprite files, even if empty/near-empty today.
- `ActivityResult` (from the module contract, Sec. 7) includes a generic `reward_signal` field (e.g.
  "nailed_it" / "improved" / "struggled") that the front-end can map to a flourish (confetti, a sprite
  animation, a sound) without the backend or scheduler needing to know what the reward *looks* like.
  This is the hook point for "a light reward graphic after each practice."
- Each `Activity`'s rendering is already isolated to its own front-end module (Sec. 7/9), so a game can
  get a full graphics upgrade later without touching other activities or the scheduler.

## 11b. Known issues

- **FIXED (2026-10-23): intermittent blank/stuck front-end renders.** Root cause was server-side, not
  the front-end: FastAPI runs the sync `get_db` generator dependency on threadpool workers, so one
  request's connect, endpoint body, and commit/close could land on different threads, and sqlite3's
  default `check_same_thread=True` raised `ProgrammingError` at random. The analysis page's 4 parallel
  fetches made it most visible (any 500 -> `Promise.all` rejects -> blank page), but any endpoint could
  hit it -- including failing at commit time, i.e. silently dropping writes. Fix: `check_same_thread=False`
  in `db.connect` (safe: one connection per request, never shared concurrently), a cross-thread regression
  test in `tests/unit/test_db.py`, the e2e xfails removed, and `analysis.js` now shows an error message
  instead of a blank page if a fetch fails.
- **Launcher smoke e2e tests use the real port 8420**, so they error at setup if the app is already
  running locally. Not a code bug; stop the local app before running `tests/e2e`.

## 11c. Gamification round 1: coins, avatar, store, cozy theme (agreed 2026-10-23)

**MVP scope**: coins, coin display, simple layered avatar, a small store, and a warm sandy pixel theme.
Profiles come right after (11d). Games that reuse the dressed avatar come after that.

- **Coins** (the cozy name for points). Each `Activity` owns its coin rule via `coins(result)`; the default
  is `round(accuracy * 100 * fraction_of_prompt_completed)`, so 85% on a finished step = 85 coins and
  ending a step early doesn't pay full. Target is ~50-100 per 1-2 min step, ~1K per 15-min session.
  Bonus rules (session complete, new key mastered, daily streak) are separate and added over time.
- **Ledger, not a balance column**: `coin_ledger(learner_id, amount, reason, ref, created_at)`, with +earn
  and -spend rows; balance = SUM. Gives history and auditability.
- **Store catalog lives in code** (`app/store.py`, like the activity registry): `StoreItem(id, name, slot,
  price, sprite, starter)`. Slots: body, hat, shirt, pet, background. Starting avatars are free hidden
  `starter` items in the `body` slot, so the avatar is just "everything equipped" and there's no learner
  schema migration. Tables: `owned_item(learner_id, item_id, purchased_at)`,
  `equipped_item(learner_id, slot, item_id)`.
- **Avatar renderer is a standalone front-end module** taking `{equipped, pose}` (only "idle" for now),
  layered per slot, so future games can draw the same dressed avatar in other poses (e.g. casting a
  fishing rod).
- **Learner isolation**: every new table is keyed by `learner_id` and every query filters on it; tests
  assert two learners' coins and items never mix. MVP stays single-learner (id 1) but routes through one
  `current_learner` dependency so cookie-based profiles slot in later.
- **API**: `GET /api/me`, `GET /api/store`, `POST /api/store/buy/{id}`, `POST /api/store/equip/{id}`,
  `POST /api/store/unequip/{slot}`; step completion response gains `coins_earned: [{amount, reason}]`.
- **Theme**: shared `theme.css` (sandy palette, pixel-bordered "windows", wood/parchment buttons) plus a
  shared header (coin counter and avatar) on every page. Bundled OFL pixel font for headings/UI; the
  typing prompt stays in a clean monospace for legibility. Art: free/open-licensed or AI-made, with
  code-drawn pixel placeholders until then.

## 11c-2. Gamification round 2 (agreed 2026-10-23)

Economy target: ~3 months of play at ~1K coins/session, so ~100K coins earned in total. The catalog
should hold well over that, so there's always something to save for. Small items cost ~200-800,
big ones (pets, rare places, night unlocks) cost ~2-5K.

Status (2026-10-23): all 5 phases below are built and tested. Art is code-drawn placeholder
pixel art (web/static/js/sprites.js, backgrounds.js, wardrobe.js, pets.js, room.js), meant to be
replaced piece by piece with real art later. Next up: profiles (11d), then games that reuse the
avatar.

Build order (each phase is tested and shown before the next):

1. **Profile page + character designer.** `/profile` is the hub linking the store, progress,
   character designer, pet room and bedroom; the header avatar opens it. The designer picks
   boy/girl, skin tone, hair color and hair length from a few options each. Appearance is learner
   data (an `appearance` table), not store items. Fancy hair dyes (blue, green, pink, ...) are store
   purchases that unlock extra hair colors.
2. **Places + page themes.** 18 places in 4 groups (fields & forests, water, wild lands, space). Each
   place also re-themes the whole page subtly: background, header, and drifting particles (leaves,
   petals, snow, bubbles, stars...). Each group has one **night unlock**. While night is on, the
   avatar scene goes to night and the whole UI switches to a dark-mode theme.
3. **Wardrobe.** Slots: hat, accessory, shirt, pants, shoes. Styles are drawn once and recolored per
   item (30+ clothes). Accessories include scarf, gloves, watering can, portal gun, ball, and more.
4. **Pets.** Each pet is an individual you own: species, coloring, name, growth 0-10. Species: cat,
   bunny, dog, sheep, goat, llama (plus hedgehog and fox). Pets start as babies. Food is bought and
   fed **once per pet per day** to grow them, with 3 visual stages (baby, young, grown). Up to 2
   pets come along on the avatar. The pet room shows all of them.
5. **Bedroom.** A shared room engine (also used by the pet room): wallpaper and floor, wall items
   (windows, posters) and floor items (furniture, toys, rugs) placed by dragging, with pets wandering.
   Room is 2x the dressing-room picture in each direction (96x96 pixel grid, ~576px).

## 11d. Profiles (next round)

No passwords. With no profile selected (cookie), show a pick-from-dropdown or create screen. Create asks
for a name, an avatar choice, and a quick placement (known keys, rough WPM). The last-picked profile is
remembered per browser via cookie, so losing the cookie just means picking again. Top-right profile button
opens details plus "log out / switch". Two kids can play at once in separate browsers on the same PC. One
DB, all tables keyed by `learner_id`.

## 11e. Keyboard-driven teach modules (started 2026-10-24)

Order: (1) intro: hands on home row + thumbs on space, (2) home row, (3) top row, (4) bottom row,
(5) number row, 2 keys per lesson each, (6) capitals: shift with one hand and the key with the other,
then a few capitals at a time. They get strung together into lessons once enough exist.

- Every step advances from a key press, never the mouse ("press Space with your thumb"), so hands
  stay on home. Steps are `show` (explain, wait for one key) or `type` (type a prompt; a wrong key
  doesn't move on). Builders: `app/activities/teach_steps.py`.
- Shared front-end: `teach_keyboard.js` (full keyboard + gray ghost hands; lights a finger and key,
  reaches a finger to any key, and can light Shift for capitals) and `teach_player.js` (runs any
  module's steps at `/teach/<id>`). Bigger text (30px) and bold keycaps.
- Registered in `app/activities/teach_modules.py`, outside the live scheduler, and stateless for now.
- Built so far: the intro (`teach_intro_home_row_v1`), a draft for review.

## 12. Workflow

- GitHub repo, feature-branch-ish commits (small, one logical change each), tests green before every
  commit, as the ProjectPlan requires.
- We build part-by-part per the build order above, testing and checking in with you at each step before
  moving to the next.

## 13. Before release checklist

- Set `DEV_START_COINS = 0` in `app/config.py` (dev mode gives every learner 50K free coins once,
  recorded as a `dev_grant` ledger row; consider deleting those rows from the real DB too).
