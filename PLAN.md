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

## 7. Module contract (for modularity requirement)

Every lesson, practice drill, game, and evaluation is a self-contained module implementing one interface, e.g.:

```python
class Activity(Protocol):
    id: str
    kind: Literal["teach", "practice", "eval", "game"]
    def is_eligible(self, skill_state: SkillState) -> bool: ...
    def generate(self, skill_state: SkillState, duration_s: int) -> ActivityContent: ...
    def score(self, content: ActivityContent, keystrokes: list[KeystrokeEvent]) -> ActivityResult: ...
```

- The scheduler only ever talks to this interface — it never knows the internals of a specific game.
- New activities are added by registering a module in `activity_catalog`; nothing else changes.
- Front-end renders generically from `ActivityContent`'s declared type (text-prompt, game-canvas, etc.).

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

## 12. Workflow

- GitHub repo, feature-branch-ish commits (small, one logical change each), tests green before every
  commit, as the ProjectPlan requires.
- We build part-by-part per the build order above, testing and checking in with you at each step before
  moving to the next.
