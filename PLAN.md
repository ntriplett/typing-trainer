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

## 6. The day, the brain, and tokens (replaced the session scheduler 2026-10-25)

The old up-front session skeleton (and its slider screen) is gone. The day is free-form: the home page
is a hub, and **Practice** asks the brain for **one lesson at a time**; the learner can stop after any
lesson, visit the store or pets, and come back.

### 6a. The daily practice chunk and arcade tokens (`app/daily.py`)

- Active typing time (idle gaps left out, capped by wall-clock time server-side) adds up in a
  `practice_chunk`. Reaching the parent's **daily goal** (default 10 min) pays **2 arcade tokens**
  (+100 coins); 1.5x the goal pays **1 more token** and practice **rests for 12 hours**.
- A chunk that reached the goal but not the bonus ends 12h after the goal (bonus forfeit); one that
  never reached the goal resets 18h after its first lesson ("reset overnight"). Multi-day streaks
  (36h between chunks) come later.
- Tokens are a second currency with their own append-only `token_ledger`; the top bar shows them
  (purple, with a glint) next to coins, plus the **day tracker** (a trail with token chests at the
  goal and at 1.5x).
- **Arcade** (`app/arcade.py`, `/arcade`): one token buys one whole game of Crow Patrol, two for Pet
  Battles; rounds still pay coins. Arcade plays end back at the arcade (no free replays).
- **Parent page** (`/parent`, open for now): per player, the daily goal and the practice <-> learn
  slider, today's progress, and the brain's next pick with its reasons. Lab links live here.

### 6a-2. Rooms that unlock (`app/unlocks.py`, 2026-10-25)

- **Pet Room** opens once the home row is taught, with a **free first baby pet** (any species/color,
  picked in the store's Pets tab). **Bedroom** opens once the top row is taught. Until then the home
  tile is a "?" block ("Mystery"), the page shows a mystery-room card with the keys still to learn,
  the store hides that tab, and the API answers 403. Players who already own pets / decorated their
  bedroom keep them open. The teach lesson that opens a room announces it.
- The arcade isn't locked: games already wait for 4+ known letters.
- Home hero greets with ~50 context-aware lines (hello / mid / almost / goal / all done / winding
  down after spending tokens); the goal chest shows a stack of 2 tokens.

### 6b. The brain (`app/brain.py`, run by `app/lessons.py`)

A pure function `plan_next_lesson(BrainInput) -> LessonPlan`; `lessons.py` gathers the input (taught
curriculum lessons, per-key recent/older accuracy from the keystroke log, bigram stats, lesson
history, settings, today's chunk) and records the result. In order:

1. No letters taught yet: **learn** (the intro, then F and J).
2. First lesson of a sitting (20+ min gap): an easy 50s **warmup**.
3. Frustration (last lesson < 85%, quit early, a speed crash, or two < 90% in a row): an easy
   **comfort** practice (weak keys left out, no weak runs, short). Never a new letter right after.
4. **Learn** the next curriculum lesson (teach_curriculum.py: intro, key pairs, capitals, numbers)
   when every taught key has 30+ recent tries at or above the bar (98% at "practice", 80% at
   "learn", interpolated), 3+ practices since the last new lesson, and none yet today. Placement keys
   with no data don't block.
5. Otherwise **practice**: focus on slipping keys (recent accuracy 6+ points under their own older
   level), the newest keys, weak keys, and exceptionally weak bigrams (low AND well under the
   learner's average pair; ~25% of words get built around one). Difficulty walks up after a great
   lesson and down after a shaky one; length follows predicted speed (an EMA of recent lessons); the
   lesson that lands the goal or bonus is trimmed to fit and eased off. Themes don't repeat for 5.

Learn lessons run on the teach page (`/teach/<module>?lesson=<id>`) and now feed the skill model and
mark their keys taught (`taught_lesson`; placement and pre-existing unlocked keys are back-filled).
Lessons in a row share one `session` row (a sitting); each finished lesson is a `session_event` whose
summary carries the plan (kind, focus, difficulty, predicted speed, reasons).

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
  else changes. (The keyboard-driven teach modules, Section 11e, are registered separately in
  `teach_modules.py` until they're strung into lessons, so the live scheduler can't pick them up yet.)
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
- Built (2026-10-24, approved): the intro (`teach_intro_home_row_v1`). It pays 250 coins the first time
  it's finished, whatever the accuracy; replays pay the normal rate.
- Built: `teach_key_pair_v1`, one module for any 1-2 keys on any row. Pages: new keys, then "meet" each
  key (reach keys add a reach page, a back-home page and a reach-and-return drill), take turns, eyes up,
  mix with known keys, real words (from `word_bank.py`, only when the taught letters spell some), done.
- Curriculum (`teach_curriculum.py`): the intro, then `KEY_ORDER` two keys at a time. A lesson's known
  keys are everything earlier. Every lesson can be tried from `/teach-lab` (replaces the old 3-way
  teach demo, which is deleted).
- Teach completions pay coins to the current player (reason `teach`, or `teach_first` for a module's
  one-time first-finish reward) but don't feed the skill model yet.
- Typing prompts everywhere (session and teach) use the shared `prompt_view.js`: one line at a time
  plus the next line faded below, wrapped only between words to fit the box. The space at a wrap is
  neither shown nor typed, so a line never ends on a space (the session reports `skipped_chars` so
  coins aren't docked for them). A space is a plain gap: yellow box when it's next, very light red if
  mistyped. No dotted space markers.
- Capitals (built): Shift is always the other hand's, pressed with its pinky. The page tracks which
  Shift is held and counts a same-hand Shift as a miss, with a hint. `teach_caps_intro_v1` teaches
  the idea with J (left Shift) and F (right Shift). Then `teach_caps_v1` takes a group of up to 5
  letters, all on one hand (one Shift): ASDF, QWER, ZXCV, HJKL, UIOP, then the pointer stretches GTB
  and YNM. Pages: new capitals, "Big X" per letter, big and small (Aa Ss), mix (capital then
  small letters), capital words, done. Capitals come after the bottom row and before the numbers.
- Next: string teach modules into lessons (after warmups/practice, 11f).

## 11f. Warmups and practice (built 2026-10-24)

- No separate eval: practice results feed the skill model, and that's the evaluation (eval module and
  scheduler eval step removed).
- Warmups are practice modules run short (60s) and easy (difficulty 0.15); practice is 100s at 0.5.
  The scheduler gives each warmup/practice step a different theme until all have had a turn.
- Practice text (`app/activities/practice_text.py`): focus letters weigh 3x each other allowed letter
  and are called out in the instructions ("Focus letters: [E] and [I]"). Nothing outside the allowed
  keys appears. `length` (characters, from seconds x typing speed) and `difficulty` (0-1) are inputs.
  Difficulty = how many weak letters / weak bigrams come in a row: easy never puts two weak letters
  together; hard chains weak pairs into whole words. Weak spots come from a `SkillSnapshot` built from
  key and bigram stats at session start. Mixes in real words when the taught letters spell some.
- 11 practice modules (`practice_modules.py`): the plain baseline plus 10 themed scenes
  (`web/static/js/practice_scenes.js`, code-drawn pixel art on a 180x54 canvas): fishing (fish nears
  the hook, misses scare it), garden (words plant, keys water), puppy walk (misses = sniff stop), moon
  rocket, potion lab (words drop ingredients, misses puff smoke), mountain hike (misses slip back), leaf
  catcher (misses = gust), star map (words light a constellation), campfire (keys feed the fire, toast a
  marshmallow), lily pad hop (each word is a hop).
- Shared stage (`practice_stage.js`) for every session step and the practice lab, in the teach look.
  A "Keyboard hint" button spends `config.KEYBOARD_HINT_PRICE` (10) coins to show the keyboard with
  hands for the rest of that lesson (`POST /api/hint/keyboard`).
- `/practice-lab` lists every module with its scene playing; options for letters, focus letters, length
  (short/medium/long) and difficulty (easy/medium/hard). Lab runs pay coins but don't feed the skill model.
- Later: tune difficulty per learner (e.g. ramp within a session), smarter weak-pair chaining.

## 11g. Games (built 2026-10-24, reworked after review)

- Rules agreed with the user: the word you type is the choice you make; time pressure in some games
  only and never very hard; soft losing; ~1 minute rounds, 5 rounds; self-contained for now
  (persistent/roguelite later). Full idea list: `GAME_IDEAS.md`.
- Words: real words (word_bank.py, ~730 kid words) as soon as the taught letters spell 8+ per length
  group; made-up words only until then. Weighted toward focus letters and (by difficulty) weak
  letters/pairs. Letters only, no ";". Groups: short 2-3, medium 4-5, long 6-8. Needs 4+ letters.
- `app/activities/game_modules.py`: `GameModule` gives `ActivityContent.game` = {game, levels, words,
  letters, chars_per_second, difficulty}. Difficulty scales crow speed / critter HP (0.8x-1.2x).
  Each round is posted when it ends (`POST /api/game/<id>/round` {score, keystrokes}) and paid
  right away at `coins_per_point` (crows 1 per 20 points, battles 0.15/point); a round is capped at
  5000 points.
- `game_kit.js`: Typer (first key locks onto the word starting with it; wrong keys are slips;
  Esc/Backspace lets go), GameShell (HUD, canvas, overlay screens covering the stage, and the arcade
  `roundTally`: rows count up one by one, round total, cheers, best round in localStorage, coins).
- **Crow Patrol** (real-time, paced by the learner's typing speed): crows come from left, right and
  top. Kinds: little (fast, short word, 10), crow (20), big (slow, long word, takes 2 pumpkins, 40),
  caller (timer ring; calls a friend when it runs out, 30), squirrel crow (drops a squirrel that runs
  to a pumpkin and eats it unless shooed, 30), golden (ignores pumpkins, crosses the sky, 100). One new
  kind per round, shown on the round card. The first slip on any crow: "CAW! Help!" bubble and a
  little friend joins (once per crow). Each round starts with a full patch (6, +2 per fence); losing
  every pumpkin just ends the round. Tally: crows by kind, pumpkins saved x100 (x250 with pie),
  perfect patch +200. Upgrades between rounds by typing: scarecrow, fence, bell, pie.
- **Pet Battles** (turn-based): types Leaf > Splash > Ember > Leaf (x2 / x0.5, both ways). Before each
  battle: the critter's type, weakness and trick; pick 1 of 3 partners by typing (pets along + Clover,
  Pip, Puddle starters to cover the types). Kits: Leaf (Vine whip, Leafy snack, Tickle = skip its
  move), Ember (Ember, Blaze, Warm up = next hit x2), Splash (Splash, Bubble shield, Big wave = always
  lands), plus Pounce (+1 star). Critters: bunny hops (your hit misses), hedgehog gets spiky (hits prick
  you), goat winds up a headbutt, fox steals stars, llama spits (your next words get longer). Bag:
  Berry, Star candy, Shell charm, typed to use; find one per win. Win tally: 200 + HP x10 + clean
  moves x20 + super hits x30. Losing: nap, pick again, critter 10% easier.
- `/game-lab` (letters, focus, difficulty) and `/game/<id>`; lab runs don't feed stats. Played for
  real from the arcade with tokens (section 6a).

## 11h. Pets v3: the Pets hub and the Pet Shop (agreed 2026-10-28)

Pets v3 (`app/pet_genes.py` rolls, `web/static/js/pet_render.js` draws) replaces the old pets.
The old pet system (`app/pets.py`, `owned_pet`, avatar/battle sprites) stays untouched until the
Pet Care Center round, which switches the avatar to v3 and wipes the old pets.

**Pets hub** (`/pets`, built 2026-10-28; home tile "Pets"; the old pet room moved to `/pets/room`
until the Pet Care Center replaces it): a field with your land pets wandering (topped up to 4 with
visitors rolled fresh each day; fish wait for the Aquarium) and four clickable buildings:
Pet Shop, **Pet Care Center** (inventory: visit and manage pets), **Aquarium**, **Trailhead**
(explore the habitats you buy). Open from the start, since the Fish department is.

**Pet Shop departments** (each player has their own stock):

| Department | Species | Slots | Opens |
|---|---|---|---|
| Fish | fish | 16 | start |
| Household | dog, cat, bunny | 16 | home row |
| Farm | goat, sheep, llama | 12 | top row |
| Reptiles & Amphibians | turtle, lizard, snake | 8 | bottom row |
| Mythical | dragon, unicorn, phoenix | 2 | number row |
| Special Orders | any open species | 4 | home row |
| Pet Supplies | - | - | coming soon |

Closed departments show "coming soon" with the keys still to learn.

- **Stock**: each slot holds one rolled pet for 2-5 days, then re-rolls at midnight (one slot at a
  time, so the shop changes a little each day). A "Last day!" banner shows on pets leaving tomorrow.
- **Save for me**: one pet in the whole shop can be saved; it never re-rolls. To save another, let
  the first go or buy it.
- **Buying** puts the pet in the inventory (placing it in a habitat comes later) and unlocks all its
  colors for every species.
- **Pet coupon**: learning the home row grants one coupon: any Household pet for free. (Replaces the
  free-pet setting; players past the home row get one when the old pets are wiped.)

**Colors** (species with their own color rules -- dragon, unicorn, phoenix, fish -- keep the game's
own picks, `roll(None, None)`):
- A species' *available* colors: its 3 starters plus the player's unlocked colors from its families.
  (Unlocks start empty; buying a pet unlocks its colors for everyone it fits.)
- *Traditional*: available colors that are starters or from a NATURAL family; the rest are *fancy*.
- Main color: traditional when nothing fancy is available, else 50/50 traditional or fancy, so at
  least half the pets keep a traditional color however many fancy ones are unlocked. Second color:
  any available. Third: rolls as before (can be locked: a lucky find).
- **Unusual (8%)**: one of the two picked colors is swapped for a locked one; a natural-family color
  is 2x as likely as a rare-family one.

**Price** = species base (fish 100, household 800, farm 2K, reptiles 3K, mythical 10K)
x 1.5 if any color is new to the player x each rare feature x a random multiplier (Gaussian,
mean 0.75, sd 0.25, re-drawn until it lands in 0.25-1.5). Tabled: fish and mythicals pick from
their whole palette, so early on nearly all carry the 1.5x new-color price; revisit later.
Rare features are a registry in `pet_genes.py` (RARE_FEATURES: name, odds table, outcome), so new
looks (more sparkles...) add one entry. Each scores against its table's most common outcome:
1.0x at the most common, 1.5x at 50x rarer or more, log scale between; even tables score 1.0.

**Special Orders**: pick an open species and a main color from its available colors (the second
color too once capital letters are finished). The order fee is half the species base, paid up front.
Next day 4 matching pets arrive at their normal prices (buy any number); they leave after 3 days. A
new order sends any waiting ones home (the button says so). Copy for a 7-year-old, e.g. "Sending the
order costs 400 coins. Tomorrow, 4 cats in your colors will be waiting here. You can buy the ones you
love. If you don't, they go home after 3 days."

**Data**: `pet` (id, learner, seed, species, genes JSON, name, growth, last_fed, adopted_at, source
shop/order/gift, home: null = inventory), `pet_color_unlock` (learner, color), `shop_slot` (learner,
dept, slot, seed, species, genes JSON, price, stocked_on, leaves_on, saved), `special_order`
(learner, species, primary, secondary, ordered_on, ready_on, expires_on; its pets are `orders`
shop slots). Genes are stored, not re-rolled: the third color depends on unlocks at roll time.

**API**: `GET /api/pets/shop` (departments, open/coming soon, the saved pet), `GET
/api/pets/shop/{dept}`, `POST /api/pets/shop/{dept}/{slot}/buy`, `PUT|DELETE /api/pets/shop/save`,
`POST /api/pets/shop/orders` (species, primary, secondary), `GET /api/pets/shop/orders/preview`
(one sample pet for the order form). Order pets can't be saved (they already wait just for you).

**Build order**: (1) available colors, `shop_roll`, rare-feature registry; (2) `app/pet_shop.py`
stock/restock/save over a fake calendar; (3) tables, buying, API; (4) shop UI; (5) Special Orders
(a small pet-lab picker); (6) the hub page. Then: Pet Care Center, habitats, Aquarium, supplies.

## 11i. Pets v3: the Pet Care Center and the Trailhead (agreed 2026-10-28)

**Pet Care Center** (`/pets/care`): a book. Left page: 3x4 pet icons, page buttons at the bottom,
sort (species, age, time owned, name, rarity, size, energy) and filter (all, waiting for a home,
one habitat). Right page: the pet large, name + rename, species, colors, growth, personality
bars, favorite veggie, rare features, adopted date; buttons Feed, Move to habitat / Take out,
Bring along. New pet actions get added here later.
- **Feeding**: one garden veggie per pet per day, +1 growth (+2 for its favorite veggie), up to
  10 (all grown up). Fully grown pets don't eat (no veggie spent).
- **Bring along**: at most 2 pets ride with the avatar (`pet.along` 1 right, 2 left). Fish can't.
- **Homes**: `pet.home` is `trail:<spot>` (a habitat) or NULL (waiting in the Care Center). 6
  pets per habitat; fish never (the Aquarium will hold 10).

**Habitats**: bought in the Pet Shop's **Habitats** department: Meadow only for now (more looks
later: mountain, ...). The first is free, then 1,500 coins. `habitat` table (learner, spot 0..9
on the trail, kind, name, bought_at); a new one takes the first empty spot. 10 spots.

**Trailhead** (`/pets/trail`): a path view, one stop at a time: signpost, a small live view of
the habitat (or an empty lot), up/down the trail, click to open it full. A map button shows all
10 spots along a winding path like a zoo map. The full habitat is a scene where its pets move.

**Movement** (`pet_motion.js`, shared by the hub and habitats): each pet is a small state
machine (wander, rest/nap, hop, look at a prop, go to a friend, play). Energy: faster walk and
animation, more hops, shorter rests. Sleepy: more and longer naps. Friendly: drift toward other
friendly pets, shy ones keep distance. Curious: visit props. **Playful** (new trait, appended so
old pets keep theirs; stored pets get it filled in from their seed): jump, chase other playful pets.

**The hub field** shows the 2 pets along, plus the newest 4 land pets without a home; visitors
top it up to 4 for new players.

**Build order** (all done 2026-10-28): (1) tables, rules, API; (2) the Care Center book; (3)
`pet_motion.js` + the meadow; (4) the Trailhead path + map; (5) cleanup: the avatar, bedroom,
home tile and Pet Battles draw v3 pets (`pet_render.js` replaces `pets.js` everywhere; battle
critters and starters are rolled server-side, `pet_care.battle_pets`; the Hedge level's hedgehog
became a lizard); the store's Pets tab, the old pet room, the free-pet unlock, `app/pets.py`
and the `owned_pet` table are gone.

## 11j. Pets v3: many habitats and how pets move in them (agreed 2026-10-28)

**26 habitats** in three price tiers (`app/pet_care.py` TIER_PRICE; a player's first habitat is
free only if it's an everyday one; the same kind can be bought again, "Forest 2"):
- **Everyday / Outdoors, 1,500:** Meadow, Forest, Stream, Mountain, Farmyard, Backyard, Beach,
  Desert, Jungle, Snowy Tundra, Autumn Orchard, Pond & Marsh, Savanna.
- **Cozy, 2,500:** Cozy Cottage, Greenhouse, Treehouse Village, Library Nook, Playroom, Hay Loft,
  Attic Hideaway, Sunny Porch.
- **Magical, 5,000 (open with the Mythical department):** Crystal Cave, Cloud Kingdom, Volcano
  Rim, Enchanted Grove, Starry Observatory.

A kind is sold once `habitats.js` HABITAT_LOOKS has its look. Trail spots stay 10 for now (later:
buy more spots). Not now: favorite habitats, day/night looks.

**Movement** (`pet_motion.js`): each look gives `terrain` (feet coordinates): `water` rects
(swimmers swim, others hop across or splash at the edge), `blocks` (no feet: rocks, logs,
furniture), `ledges` {x0, x1, y} (raised walkways pets leap up onto and down from), and `props`
with an `action`: look, bask, nap, dig, jump (in leaves, a ball pit), optionally on a ledge.
Species leanings: CLIMBERS (goats most), SWIMMERS (turtles most), BASKERS (lizards, snakes,
turtles). Wandering stays within ~45 units.

**Batches**: (1) engine + Forest, Stream, Mountain; (3-5) all the rest, done 2026-10-28 (looks
in `habitats_outdoors.js`, `habitats_cozy.js`, `habitats_magic.js`; the shop groups habitat
cards by tier); (2) the Pet Shop's Habitats department is a gallery: framed pictures, 8 to a room
(Outdoors Hall, Outdoors Annex, Cozy Corner, Magical Wing), click one for a big preview and Buy.

## 11k. Pets v3: aquariums you build yourself (agreed 2026-10-28)

**Tanks** (`app/aquarium.py`): a 75-gallon tank (160x70 units, ~48"x21") for up to 10 fish, 400
coins; everyone starts with one empty basic tank (Deep Blue background, Sand). 10 tanks to start.
**Supplies**, all in the Pet Shop: backgrounds (40-60) and substrates (20-40) bought once and used
in any tank; plants, rocks and decorations (10-100) bought per copy, kept in storage, placed with
x/y, a layer (back: behind fish, middle: fish swim around it, front: in front of fish) and flip.
Each item tells fish what it is (`sees`: hide, explore, through, bubbles). Tables: `tank`,
`tank_piece`, `aqua_owned`; fish live in a tank via `pet.home = "tank:<spot>"`. Fish aren't fed yet.

**Pet Shop**: 4 doorways downstairs (Household, Farm, Reptiles, Mythical) plus the Special Orders
counter; a cute spiral staircase up to **Fish, Homes & Supplies**: Fish, Habitats (the gallery),
Aquarium Supplies, Pet Supplies (soon). Supplies rooms hold 8 items at most: Tanks & Backdrops,
Sand & Gravel, Little Plants, Plants, Tall Plants, Driftwood, Little Rocks, Big Rocks, Decorations
(a planted-tank look: carpets, stem plants to the surface, floating Frogbit, spiderwood, manzanita,
seiryu, dragon stone; hiding spots are dark inside). Room navigation is signposts above the scene,
never signs inside it.

**Schools**: you can buy another of a fish you own (its shop price, no new-color bonus): a copy is
its own `pet` row with `school` = the first fish's id, so each copy swims in a tank; the Care Center
shows the school once ("×4"); renaming, feeding and moving to a tank go for the whole school.
**Fish size**: in a tank the size gene scales a fish's pixels by 2^(0.6 x size), about 0.66x-1.5x.

**Aquarium** (`/pets/aquarium`): a dim hall of glowing live tanks: 4 in the main hall, 3 each in the
Reef Room and the River Room. `/pets/aquarium/{spot}`: one tank, with Decorate (like the bedroom:
backgrounds, bottoms, storage, drag, flip, layer, put away) and a Fish panel. The Care Center moves
fish into tanks too.

**Fish movement** (`fish_motion.js`): stay near `behavior.height` most of the time; curious fish
explore pieces and roam; small schooling fish steer together and turn as one; shy fish hide in
plants, caves and castles; bottom feeders poke along the substrate; playful fish ride bubbles;
fish swim through arches; fish always face forward; each fish's depth decides whether it passes
behind or in front of middle-layer pieces.

## 11l. Pets v3: Pet Supplies, playing, happiness, potions (agreed 2026-10-28)

**Shop** (upstairs, `app/pet_supplies.py`): Treats & Fish Food, Toys, Magic Potions rooms. Treats (5
coins, used up) and toys (100, kept) each loved by a few species; fish food (5): flakes float down
slowly, pellets sink for the bottom feeders.

**Playing**: under a habitat, a shelf of your treats and toys. Click one: three words appear in the
scene (left, middle, right); typing one throws it there. Pets that like it run over (leaping down
from ledges) and bounce with hearts; a treat is eaten by the first one there; a toy comes back.
Words: the games' words for the letters you know (`/api/play/words`). No rewards but happy pets.
**Happiness**: up to 5 hearts per pet (`pet.joy`, `pet.joy_on`): +1 per treat or toy it likes,
-1 per day nobody plays. Shown in the Care Center and the habitat's list. Fish have none.

**Fish food**: on a tank's page, the same type-a-word throw sprinkles food; fish swim to it at their
own height and eat it.

**Color potions** (one use): two colors each, applied to the pet's main and second color (the whole
school for fish), and unlocked. New every day, two per tier: Mystery (no colors shown) 20, second
color shown 40, main color shown 60, Clear (both shown) 150. Used from the Care Center's 🧪 button,
which lists only potions that species can wear.

## 11m. Farm Stand: the first persistent game (agreed 2026-10-28)

- One arcade token (1) = one market day of 4 hours x 60s in real time (reworked twice after
  playtests, 2026-10-28). Nothing moves until the first seed is planted; the first customer comes
  10s later. Crops grow in seconds (radish 20s .. pumpkin 110s), ripe ones go onto the shelf while
  it has room, and seed packets stay out so you replant while you serve. Customers are grown
  animals rolled like the Pet Shop's (2% mythical), every ~6-12s (sign upgrade = customers per
  minute, never faster than the learner can type), up to 3 in line, patience x1.3.
  Third pass (same day): the line refills as soon as it has room (1.5s apart), so 2-3 always
  wait and you choose; each waits 4x as long. The sign upgrade became "more big-basket
  customers" (share 15%..50%, from 8 reputation); pacing model uses ~9s per order served.
- Word groups (PrefixTyper in game_kit.js): every seed word starts with one letter, every
  customer with a second, every delivery with a third (the letters with the most words). The
  first key lights the group, later keys pick one; no word is the start of another, and second
  letters differ when they can. So 4 learned letters are enough (the first version ran out).
- Information, so planting is a choice: the next 4 customers' orders stack in the sky and the
  bottom one drops down to each animal that walks up; delivery orders (`farm_stand.deliveries()`,
  2-3 a day: an animal, a 3-5+ veggie order, due by the end of hour 2-4, pays x1.5; a missed
  deadline counts as a missed customer). Orders lean to the animal's favorite veggie. (Hot
  veggies were tried and dropped.)
- Serving: type a customer's word (even while they walk up). Short of something, the ticket shows
  "swap" and typing sells a swap: swapped-in veggies at half price (full if it's their favorite),
  no tip; nothing to swap shows "Need Carrot!". Tips up to +50% for quick full orders. Each
  hour's tally pays coins like other games.
- Your pets along help: the first carries deliveries (walks off with a basket, back in a few
  seconds, +10% tip; no other delivery meanwhile); the second (or only) pet is the gardener: it
  hops about a fenced pet plot that it replants with its favorite veggie for free (it hops over
  to plant, hearts when it ripens); a customer of your pet's species gets a
  happy hello (hearts) and waits 25% longer.
- Delivery orders hang in the sky at the top left; seed packets are the only thing below.
- Seeds go on credit during the day (money may dip below $0, so you can't get stuck with nothing
  to sell); a finished day never saves below $0. Coins 0.24/point (tripled at the user's ask).
- Fourth pass (same day): the line steps up when someone leaves (the front one waited longest);
  coins 0.08/point; a live star meter in the HUD and a big "PET FOOD!" reward card; the next
  locked veggie shows as a greyed "new seeds coming" packet; up to 4 delivery orders (2 + wagon).
- Upgrades (all open with reputation; something new about every 3 days to ~day 115 for a greedy
  player): More Plots (4-24; the plot grid adds rows and shrinks cells), Bigger Shelf, Sprout Alarm
  (empty plots flash), Shop Bell (patience), Tip Jar, Seed Catalog (seeds cheaper), Bigger Sign
  (big baskets), Delivery Wagon, Sprinkler (grow faster), Pet Patch (gardener gets 1-3 plots),
  Price Board (+10-30%), Fancy Customers (10-30% of customers want 50% more, wait half as long,
  pay double), Robo-Farmer (1-3 robot plots replanting your first seed of the day; it pays for
  seeds), Compost, and 12 decorations.
- The farm is saved (`farm_save` table, `app/farm_stand.py`): its own "stand money" (not coins),
  reputation (+0..3 stars a day), upgrades (plots 4-12, shelf, bell = patience, sign = customers,
  compost = +yield) and 12 decorations drawn on the stand. Crops are the 10 garden veggies, opening
  with reputation. Prices are tuned with `typical_day_profit()`; a test checks something new opens
  at least every 5 days through day 50 (the shop runs out around day 64 for a greedy player).
- Only arcade plays count: spending the token opens a day; `POST /api/farm/day` saves it and closes
  it (server checks the day is possible). Lab plays get a tally and change nothing.
- A 3-star day (80%+ served, at least 6) gives one veggie (pet food) from the day's sales.
- Later: seasons, special customers (regulars, chef, mayor), crops that stay in the ground overnight.

## 11n. Wanderpaw: an adventure that replaces Pet Battles (agreed 2026-10-29)

A persistent exploring game: lead a party of your pets across one world per player, reach the five
type temples, bring their relics home for the ending. Leans away from "pet fights in an arena":
clean storybook fantasy, critters get tired and wander off happy (or are befriended), "energy"
not health. Replaces `game_pet_battle_v1` when it's ready (pre-1.0, breaking is fine).

**Pacing.** 2 tokens = one trip of ~5-10 min (5 rushing, 10 exploring and reading). A temple
takes ~5-10 trips including the quests that open its path; the whole game ~50 trips.

**Types (5, a ring).** Splash -> Ember -> Dream -> Leaf -> Shock -> Splash. Each type is very
strong (x2) vs the next, strong (x1.5) vs the one after, weak (x2/3) and very weak (x1/2) vs the
other two. Colors: Ember red, Splash blue, Leaf green, Dream purple (sleep/mind), Shock
yellow-orange. Species (draft): Ember fox, dragon, phoenix; Splash fish, turtle; Leaf bunny,
goat, llama; Shock cat, dog, lizard; Dream unicorn, sheep, snake. A pet defends with its base
type and attacks with either type. At level 5 it picks a second type from 2: the type of the
partner it fought beside most, and one other at random.

**Pets.** Energy (not HP: stamina + level + growth), mana (big moves; refills a little each
turn), power (strength + level), speed (who acts first). Personality perks: curious spots hidden
things, friendly befriends better, sleepy resists Dream and rests better, playful sometimes gets
a free action. XP to pets that fought: 100 x difficulty clamped to 25..250 (even fight 100);
a level per 500 XP; levels raise energy, power, mana; new moves at some levels.

**Party.** Up to 5 pets per trip; empty slots get temp starters (don't level). The picker
remembers the last party and defaults to it; starred pets list first, the rest tucked away.
**Camp** holds up to 5 befriended critters (usable on trips, not in your pet area); a rare charm
(one per temple) promotes one to a real pet, freeing its slot.

**Battles.** 2 of your pets active, no swaps; each turn you type a move for each and they
resolve together. Both out of energy = battle lost; the others carry the trip on. Moves are
words (big moves 3-4 words, cost mana); each slip takes ~10% off that move (floor ~40%). Each
type leaves a mark: Splash Soaked, Ember Glowing, Leaf Tangled, Dream Drowsy, Shock Static;
marks combo across types (Soaked + Shock = chain zap) and stack within a type (2 Tangled =
Rooted, 2 Drowsy = Fast Asleep). Duets: big moves only two same-type active pets can do. Blocks
are typed: a block can't stop a type it's weak to, and bounces some back from types it's strong
against. Critters telegraph their next move; a quick dodge or shield word answers it. Terrain
boosts types (home region +, lakeside Splash, night Dream). Befriend by typing a kind phrase
(better on calm or Drowsy critters, with friendly pets): the critter joins as a temp party
member for the trip. Why two of one type: duets, stacking, two-pet field skills, home-region
boosts, and different second types.

**Field skills.** Types work on the map: Ember lights dark caves, Splash fills wells and douses
fires, Leaf grows vine bridges, Shock powers windmills and gates, Dream calms a guardian so you
can pass. Some need two pets of the type.

**World.** One per player, generated once from a seed (local maps rebuild from it; only
discoveries and unlocks are saved). Big map: ~60-90 big hexes, Camp in the center, five type
regions as wedges out to the edges, each with its temple at the far edge; harder farther from
Camp. Each big hex zooms into a local map of small hexes, 6 on a side (radius 5, 91 hexes),
walked by typing the word on a neighbor hex. You see only your hex and the six touching it;
walked hexes stay on your map. Every big hex has one easy-to-spot campfire. Explored big hexes
are crossed in one step on the big map. A town fills ~1/4 of a big hex; each building is one
small hex: stand on it and "go in" to get its screen (shop, dialog, camp, battle). A trip ends
when every pet is out of energy (or you head home): nap, then the next trip starts at the closest
campfire you've found (or Camp, if you choose). Kept forever: map, unlocks, temple progress,
relics, items, XP, everything found (losing just means a nap). Reset each trip: critters and
in-progress side quests.

**Story.** Each temple's gate needs that region's quest item and its field skill. Inside: the
relic, a permanent buff for the pet of that type who opened it (the bunny that opens the Leaf
temple gets Elder Leaf), and one befriending charm. All 5 relics open the final spot at the
center: an ending scene and credits. Quests give lasting rewards (shortcuts, bridges, key items,
waystones); small repeatable ones give coins and items.

**Build order.** (1) World gen + big map view; (2) local maps, walking, sight, campfires,
resume; (3) POIs, towns, quests, gates, temples, story; (4) pets: types, stats, XP, party, Camp;
(5) battles; (6) balance, credits, replace Pet Battles in the arcade.

**Phase 1 (built 2026-10-29).** `app/wanderpaw/` (hexes.py grid math, world.py generator,
save.py in the `wander_save` table). Pointy-top axial hexes, big map radius 5 trimmed to ~75-87.
Walls: each region is a "growing tree" maze from its one gate onto the heartland (the best of 16
tries, aiming at 10 steps gate -> temple) plus a few loops and rare crossings between regions;
temples average ~10 walking steps from Camp (5 in a straight line). `/wanderpaw` walks the big
map by typing (a stand-in until local maps); `/wander-lab` (admin, linked from the parent page)
shows any seed with no fog, steps-from-Camp, and moves you anywhere or restarts your world.

**Phase 2 (built 2026-10-29): small maps.** `app/wanderpaw/local.py`: each big hex is a radius-5
hexagon (91 small hexes) from the seed + its place. The outer ring is six 5-hex zones, each centered
on the corner hex facing that big neighbor: an open big edge gets 1-3 exit hexes (signposts; seeded by
the edge so both sides match, the far side mirrored), a walled one is all wall (river -> water, cliff,
thicket -> trees, rocks), the world's edge is water. Feel by biome (STYLES): open (clumps, ~72%
walkable), orchard rows (~75%), forest (~55%), deep forest (~47%), canyon/mountain cliff bands
(~61/55%), river with crossings, ponds, lake, isles (~50%). Clumps are smoothed noise cut at an exact
share (steady density). One visible trail per open side wiggles to the campfire (windier in forest
and cliffs, merging with other trails); other exits, buildings and cut-off pockets just get a way
through (bridges/fords over water), tiny pockets fill in; every walkable hex is reachable. Specials:
Camp's camp, towns (plaza + 5-7 buildings, campfire in the square, ~1/4 of the hex), temple toward
the world's edge, Heartstone in the middle. Save v2 (`save.py`): big `at` + small `spot`, per-big-hex
`seen` bitmasks (you see your hex and the six touching it; seen stays, dimmed), campfire smoke shows
anywhere in its big hex, found = seen. Trips: TRIP_ENERGY 120 steps (placeholder for pet energy); out
of energy = nap at the nearest found campfire (big-map walking steps); Enter at a campfire rests and
ends the trip; next trip starts there or at Camp (C). Lab: click a big hex for its whole small map
(fog toggle, click a small hex to put yourself there), Full energy, and a Land gallery of every biome.
Later: crossing explored big hexes in one step on the big map.

**Phase 3 (built 2026-10-29): gates, places, story.** World gets `gates` and `quests` from their own
random stream (STORY_VERSION; the land doesn't move). Per region: the elder lives in its town nearest
Camp, lost something in a ring-4+ hex (a star on your big map once asked), and the reward repairs the
`shortcut` (the wall whose opening saves the most steps to the temple; a "quest" gate until then).
On the pre-shortcut way to each temple: a gate of the region's own type (deep) and one of another
type (early); 20% of in-region loops get two-pet gates. Gates sit in the exits on both sides (dark
tunnel = Ember, brush fire = Splash, gap = Leaf, old gate = Shock, guardian = Dream, broken bridge =
quest); typing a gate's word uses the field skill if the party has the pets (2 energy); cleared
stays cleared. Party = a stand-in list of types (all five) until pets (phase 4); lab edits it.
Places (own random stream): 1-3 forage spots (region find, once per trip), chests (more likely
farther out; coins, once ever), shrines (type a line on the stone: energy x accuracy, once per
trip), the lost thing. Town buildings: elder (quest town only), notice board (side quest: 3 of the
region's find for 10 coins; forgotten at trip end), inn (+25 energy once per trip), shop (not
stocked yet), houses (chatter). Enter goes in (save.screen/act); the temple wants its key + a pet of
its type and gives the relic, a befriending charm and the Elder buff (recorded per type for now);
five relics at the Heartstone = credits. Words in `app/wanderpaw/story.py`. Save v3 adds party,
items, cleared, chests, quests, temples, charms, buffs, finished, stats, events (what the last move
did: the API pays coins and the page shows them). Lab: gates on the big map, story overlay (stars +
list), stand-in party editor, steps counted without unrepaired shortcuts.
Later: wild encounters (phase 5), the shop's stock, waystones.

**Phase 3b (built 2026-10-30): one seamless world, twistier land, nooks.** The small maps tile one
world grid (big hex b's middle is world hex 11*bq+5*br, -5*bq+6*br; the big map is drawn turned ~27°
to match), so you walk straight across big edges wherever both sides are walkable and the view stays
centered on you (radius 7, the outer ring faded, tiles slide 220 ms per step). Walls are one hex
thick, on one side of the edge (picked per edge); the world's edge is ocean. Land: spines of blocker
break up big open areas (TWISTS), trails fork and rejoin (FORKS), short one-wide spurs dig to dead
ends (SPURS). Drawing: water fills its hex as one channel with a current and bank lines (deep water
blocks; fords are pale shallows costing 2 energy, 1 with a Splash pet; bridges are normal steps);
cliffs, trees, rocks and bushes draw as ranges (a glyph between neighbors); a dark line marks every
side you can't walk across. **Type levels** replace pet counts: a party's levels of a type, summed
(stand-in pets all at `party_level`, default 5; later a pet's first type = its level, a second type
counts from 1). Gates take 3 levels (x2 gates 8). **Nooks** (local.Nook, ~3-4 a map, own stream):
caves in cliffs/rock (one door; deep ones need Ember), tunnels through cliffs (two doors, a shortcut
of 8+ steps; a sleeping creature for now), glades in thick woods (overgrown need Leaf), fishing spots
(type a line for fish, once a trip), dive spots (Splash), and a treat at dead ends (buried chest,
lookout, spring, ruin, nest, berries, log, statue, traveler, well, plus the region's: rune stone /
mushroom ring = Dream, machine = Shock, tangle = Leaf, burrow = Ember). Needs grow 1-2 near Camp to
8-10 at the edge. Finds: coins, clues and views once ever (`found`), forage, energy and fish once a
trip; a clue marks a buried cache up to 2 big hexes away (`clues`), dug up by stepping on it. The
server sends the hexes you can step to. Save v4. Dev: "Start next day" button (refill; tokens later).
Later: tunnels across big walls (must not skip gates), creatures in nooks (phase 5).

**Phase 4 (built 2026-10-31): pets.** Types live in the game (`app/wanderpaw/pets.py`;
the old genes `element` is gone, Pet Battles keeps its own 3-type map until it's retired). Two
farm/household species per type: Splash dog, turtle; Ember fox, lizard; Leaf bunny, goat; Dream llama,
sheep; Shock cat, snake. Mythicals are born with both types, equal from level 1, each pair unique:
dragon Shock/Ember, phoenix Ember/Dream, unicorn Dream/Leaf, mermaid Splash/Shock, flower fairy
Leaf/Splash (mermaid and flower fairy are stubs until their art is designed). Fish stay home. Type
levels: first type = level; at level 5 a pet picks a second type from two (the type it has fought
beside most, from `partners`, a per-type count bumped each battle; random until battles) which counts
from 1 (picked with left/right in the party list). 500 XP a level; XP for now from quests (150), temples (300), caches (25), and the first search
of a nook that needed levels (20); the lab gives XP. Stats from the genes' strength/speed/stamina +
level: energy 14+stamina+2*level, power, speed, mana (battles). Trip energy: your own 50 for walking
(WALK_ENERGY, spent first) then each pet's (spent evenly; battles will take theirs); food tops up yours
first. Party: up to 5 pets picked between trips (arrows, Space, S star, Enter), starred first, remembered;
empty slots get level-1 starters of the missing types (they don't level). Table `wander_pet` (one
Record JSON per pet). Save v5: `party` (ids, None = your first pets) and `team` (the trip's members).
Later: one befriendable mythical per type region via a hard quest; Camp roster (phase 5).

**World gen v2 (built 2026-10-31): gated zones.** Map radius 6 (~110-120 big hexes; land types
stretched to ring 6 until they're redone). Each region is a maze (tree) from one way in off the
heartland; regions only meet through broken shortcuts; loops only inside a zone. Gates carry a level:
the heartland (7 hexes) is free; entering a region takes 2 of its type; its temple is its farthest
leaf (7+ steps from Camp, one neighbor) behind 8 of its type; about half the region (the temple's
side) is behind 3 of the type it's very strong against; its one town (3-5 out, outside that half)
behind 3 of its own type; maybe a 1-2 hex pocket behind 3 of the type it's weak against. Each
region's shortcut joins two zones that both take 3 of its type. Rules hold with shortcuts open too
(checked). A broken layout rerolls the seed (World.rerolls); a region retries up to 40 mazes and up
to 10 towns before that. Lab: gate levels map (shortcuts broken/open). Shortcuts (revised): each sits
on the border to the next region around the ring, each side taking exactly one 3 (any type) and no 8;
its quest checks both 3s (Gate.types), so opening one only ever skips 2s. 100 seeds: mean ~0.8
rerolls, median 0, max 7. Showcase seed: 102.

**Quests v2 (built 2026-10-31).** `app/wanderpaw/quests.py` plans them from the seed. Each town has two
quest-givers (story.NPCS: the region's animals, each with a lost thing, a pitch, their own repair line,
a training style), one per shortcut on its borders. The first of a shortcut's pair you take on mends
it: bring their lost thing plus the part waiting on each side (bump the broken shortcut to pick up your
side's; a pet with 3 of the far side's type brings the other across, or walk round); the other trains
a pet one level (you pick). Shortcuts are a ferry, a cave-in tunnel, a footbridge, a vine ladder and a
lift (story.SHORTCUTS). Lost things hide in the region's pocket or in a nook that takes 3 of its type:
cave Ember, glade Leaf, dive Splash, grotto Dream, mine Shock (one entrance per type). Finishing either
quest in a town gets the rumor of the region's temple key (hidden in another such nook). Screens can
offer numbered options. Towns: houses of the region's animals plus a mythical neighbor, named inns and
shops.

**Play polish (2026-10-31).** Words to step by terrain: a letter for paths and paving, short for
grass, medium for fords and nook doors, long for gates. Top box shows what happened; keys in the map's
corner (Enter glows when new); Go home asks (end the day / come back later / keep playing); books 1-5:
Bag (what things are for), Journal (quests lit on a map), Party (stats), Log (last 10), Map (everything
you've visited, gray where land is unfound, legend in the margin, click for details). The big map only
shows places you've been. Great halls: the Heartstone (5 relic pillars that light up, colonnade, door
toward Camp) and temples (features per type) are 7 hexes across, with moving glows and sparkles.


**Phase 5 (building, 2026-10-31): battles.** Wild creatures (`critters.py`): guardians at key spots
(nook doors, by chests, one-wide trails; back each day) and wanderers in new spots each day; wild
animals of the region's species, level from how deep the place is; animated markers on the map;
walking into one (a long word) starts a battle; beaten ones are gone for the trip. Battles
(`battle.py`): your two fighters (picked in the Party book with F, else the first two) vs one
creature; each round each fighter types one of six moves: Attack (its best type), Big (a three-word
phrase, 6 mana, 2.2x, goes first, leaves its type's mark), Guard, Focus, Cheer, Rest; slips weaken a
move; then speed order. Pacing: a fair fight ~3 rounds, ~10% of each fighter's energy (creatures have
their own energy and hit sizes). Marks last this round and the next; a hit of the right type sets off
one of 20 combos (battle.COMBOS: a 5x5 of mark x hit with one gap per row and column), each uses up
the mark: more damage, lost turns, weaker hits, burning, or a boost for your pets. Combo book (book 6)
fills in as you find them (20 XP each, first time). Winning: XP to the fighters, partner counts (for
second types), you step on; losing rests the two; Esc runs (2 walking energy). The battle screen
replaces the map: fighters with energy and mana bars and their moves left, the creature right; each
round plays back step by step (lunges, shots, bursts, numbers, marks drawn on the creature).
Campfires: resting no longer ends the day: it makes the campfire a place a new day can start, and
once a day, once your energy is half gone, gives +10. A day ends only out of energy or Go home ->
end the day (waking by the nearest campfire you've rested at). Big maps are drawn flat-top, small
maps pointy-top. Next: befriending and the Camp roster, telegraphs, duets, terrain.

**Levels and tougher creatures (2026-11-01).** Each level costs 1.08x the last (pets.XP_FIRST_LEVEL 500,
XP_GROWTH: favorites may max out, the whole party shouldn't), cap 21 for pets and creatures (22,890 XP in all; stored XP is kept, levels recomputed). A creature's
level: heartland 1-2; elsewhere gate depth - 1 + 2 per ring past the heartland (ring 2 +2 .. ring 6 +10), +/-2 for
each creature; then +2 for every relic out of its temple (save.relics_out; relics count when taken until returning
them is its own step). Above level 5 a creature has a second type (seeded, from its looks seed): it hits with
whichever is best and defends with its first, like a pet. Later: gates rising with relics (balance pass), bigger
creature spells, temple bosses, a level 21 bonus that helps from outside the fight.

**Balance report.** `tools/wander_balance.py` (not in the game or the test suite): creature levels by ring, energy,
simulated fights, sessions to levels 5/10/15/20, and TARGETS for how the game should feel. Run it around big balance
changes; it exits 1 if a number leaves its target.

**Level-up pop-ups (2026-11-01).** Each level gained queues a pop-up in the save (`levelups`; survives reloads, shown
one at a time, after any battle): what grew, and at odd levels a choice that has to be made (pets.level_choice; so far
only level 5's second type, other levels just show stats). `POST /api/wander/levelup` finishes the first one. The
lab's XP buttons queue them too. The party list's pick stays for pets that reached 5 before this.

**Party book (2026-11-01).** A whole screen like a battle's (the board and side put away). Opens on "Whole party": the
team moving around a scene for where you are (PARTY_SCENES by biome; only the grass Meadow habitat so far, using
habitats.js and pet_motion.js). Each pet: big level, energy, mana and XP bars, power, speed, and its six moves as
battle-style cards saying what they do with its real numbers (battle.described_moves, sent as `moves` on each team member).

**Focuses (2026-11-01, level 3).** Odd levels bring a choice; level 3 picks one of four focuses, themed by the pet's first
type (battle.FOCUS_NAMES, `Record.focus`), each taking over a grey move: Healer for Guard (passive: partner +1 energy up to
5, +1 mana up to 3, a battle, each round), Elementalist for Cheer (typed, 1 mana, goes first of all, no damage, leaves its
mark), Daredevil for Rest (passive: its type's Attack and Big x2, each 4% of its energy, never its last), Guardian for Focus
(passive: partner can't be hurt by the two types it's strong against for 2 rounds; creatures with another type use it; Guard
turns its color and takes 25% from the type that beats it). Permanent for now; a later level may replace it. The level-up
screen is a whole page like the party book's: a number previews a choice in the six moves, Enter makes it. "Start my world
over" now sends pets back to level 1 (stars stay).

**Level 5 (2026-11-01).** The second type brings a plain attack in that type (`attack2`), taking the slot of a grey move
the player picks (`Record.swaps`: gave up -> got; a Guardian's colored Guard doesn't count). Two steps on one page, each saved,
so a reload keeps its place: the type, then the slot. Attack and Big are first type only (Big picking a type was confusing);
a Daredevil's double stays on its first type. Mythicals skip the type pick. Next: level 7, a mixed-type move replacing any of
the six.

**Level 7 (2026-11-01).** A mix of the pet's two types, taking any of its six slots (`swaps` chains: rest -> attack2 -> mix;
giving up a focus's passive ends it, battle.focus_active). The move is fixed by the pair, so the only choice is the slot.
battle.MIX_MOVES has all 20 ordered pairs (first type sets how it behaves: SPLASH weakens and supports, EMBER raw power with a
catch, DREAM tricks, LEAF outlasts, SHOCK fast and often; second its flavor); MYTHICAL_MOVES gives each mythical its own, a bit
stronger. All cost 4 mana, so about 4 uses a day at level 7. A mix hits with its better type, can set off a combo for either, and
a Daredevil doesn't double it. `tools/wander_balance.py` measures each in the real battle code, used once a fight.

**Level 9 (2026-11-01).** Two rewards, names getting a "+". The focus grows on its own (battle.focus_plus): Healer +3 energy a
round up to 9, mana up to 5 (long fights are its strength); Elementalist's move leaves both types' marks for 1 mana + 5% energy,
still no damage; Daredevil doubles both types; Guardian 3 rounds, other
types hit its partner 25% softer, Guard 25% from everything. And one other move upgrades (`Record.upgrades`): Attack and the
second attack 1.3x, Big 2.8x for 5 mana, Guard takes 25%, Focus and Cheer 2x, Rest 30% energy and 5 mana, a mix 3 mana. A pet that
gave up its focus at level 7 can take it back instead (with its growth), and its mix then picks a new slot. A balance pass
changed first drafts (a free second mark was far too strong; Guardian, Guard and Rest too weak).

**Move icons (2026-11-01).** Each card shows at a glance what it does (battle.move_icons, drawn by moveIcons): top right, circles
in order: >> for haste; circles for a hit (one per half of a plain attack, in its type, half and half for a mix); a burst for each
mark; a shield for protection (solid: you, thick outline: your partner, half and half: both; colored for certain types, dark gray
for all; two for immunity). Bottom right, its mana and energy costs. Hover for details. Text only says what icons don't. Energy,
mana and XP have icons wherever they're called out: wanderText adds them beside the words "energy" and "mana" in game text.
Text and tooltips follow app/wanderpaw/terms.py, the dictionary of game terms: You/Your, Partner, Both, Enemy, Gain and so on, one
word for one idea, with types, marks, battle effects, terrain and lands; "gain" and "drain" (taking energy from Enemy) differ. The same icon always has the same tooltip; anything more specific goes in the move's text, kept as short as it
can be. {energy}, {mana} and {xp} in text draw their icons in place of the word.
Tiles are drawn by wander_moves.js everywhere. `/move-lab` (admin) shows every tile (battle.move_catalog), as a party, battle or
level-up card, 3 or 4 across, and flags any whose words don't fit.

**Style rule: type words (user, 2026-11-01).** Any time a type's name appears in text (SPLASH, EMBER, DREAM, LEAF, SHOCK),
it's in all caps and in that type's color. Text marks them as tokens: `{ember}` in strings (`world.tw(kind)` in f-strings;
`story.fill` instead of `str.format` for templates holding tokens), and the page's `wanderText` (wander_text.js) draws them.
Use it for anything that shows game text. A thing merely named with the word (the Sun Ember, the Evergreen Leaf, "dream big",
the Ember Peaks biome) stays plain. Shock's text is a darker orange so it can be read on our paper.

## 12. Workflow

- GitHub repo, feature-branch-ish commits (small, one logical change each), tests green before every
  commit, as the ProjectPlan requires.
- We build part-by-part per the build order above, testing and checking in with you at each step before
  moving to the next.

## 13. Before release checklist

- Set `DEV_START_COINS = 0` in `app/config.py` (dev mode gives every learner 50K free coins once,
  recorded as a `dev_grant` ledger row; consider deleting those rows from the real DB too).
