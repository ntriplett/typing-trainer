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

## 12. Workflow

- GitHub repo, feature-branch-ish commits (small, one logical change each), tests green before every
  commit, as the ProjectPlan requires.
- We build part-by-part per the build order above, testing and checking in with you at each step before
  moving to the next.

## 13. Before release checklist

- Set `DEV_START_COINS = 0` in `app/config.py` (dev mode gives every learner 50K free coins once,
  recorded as a `dev_grant` ledger row; consider deleting those rows from the real DB too).
