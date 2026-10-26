"""Unit tests for the brain (app/brain.py): which lesson comes next, and
how a practice lesson is shaped. Pure: no DB, no clock."""

import random
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app import brain
from app.activities.practice_modules import PRACTICE_MODULES
from app.activities.practice_text import SkillSnapshot, build_practice_text
from app.activities.teach_curriculum import INTRO_ID, PAIR_ID
from app.brain import BrainInput, KeyRecord, LessonRecord, lesson_ref, plan_next_lesson
from app.models import BigramStat

NOW = datetime(2026, 10, 25, 18, 0, tzinfo=UTC)
HOME = ("fj", "dk", "sl", "a;", "gh")
HOME_KEYS = frozenset(" fjdksla;gh")


def taught(*pairs: str) -> frozenset[str]:
    return frozenset({lesson_ref(INTRO_ID, "")} | {lesson_ref(PAIR_ID, p) for p in pairs})


def solid(acc: float = 1.0, n: int = 40) -> KeyRecord:
    return KeyRecord(recent_attempts=n, recent_correct=round(acc * n), older_attempts=80, older_correct=round(acc * 80))


def lesson(kind="practice", minutes_ago=2, accuracy=0.95, wpm=15.0, **kw) -> LessonRecord:
    return LessonRecord(kind, kw.pop("activity_id", "practice_garden_v1"), NOW - timedelta(minutes=minutes_ago), accuracy, wpm, **kw)


def home_learner(**kw) -> BrainInput:
    """Home row taught and solid, mid-sitting, plenty of practice since the last new lesson."""
    defaults = dict(
        now=NOW,
        taught_lessons=taught(*HOME),
        taught_keys=HOME_KEYS,
        keys={k: solid() for k in HOME_KEYS},
        history=[lesson("learn", 60 * 30), *[lesson(minutes_ago=m) for m in (12, 8, 4)]],
        fallback_wpm=15.0,
    )
    return BrainInput(**{**defaults, **kw})


def plan(inp: BrainInput, seed: int = 1):
    return plan_next_lesson(inp, random.Random(seed))


# --- which kind of lesson -------------------------------------------------------


def test_brand_new_learner_starts_with_the_intro():
    p = plan(BrainInput(now=NOW, taught_lessons=frozenset(), taught_keys=frozenset()))
    assert (p.kind, p.activity_id, p.teach_keys) == ("learn", INTRO_ID, "")


def test_after_the_intro_comes_the_first_key_pair_even_mid_day():
    inp = BrainInput(
        now=NOW, taught_lessons=taught(), taught_keys=frozenset(" "), learns_today=1,
        history=[lesson("learn", 1, activity_id=INTRO_ID)],
    )
    p = plan(inp)
    assert (p.kind, p.activity_id, p.teach_keys) == ("learn", PAIR_ID, "fj")


def test_first_lesson_of_a_sitting_is_an_easy_warmup():
    p = plan(home_learner(history=[lesson(minutes_ago=90)]))
    assert p.kind == "warmup"
    assert p.difficulty == brain.WARMUP_DIFFICULTY
    assert p.duration_s == brain.WARMUP_SECONDS


def test_everything_solid_learns_the_next_pair():
    p = plan(home_learner())
    assert (p.kind, p.teach_keys) == ("learn", "ru")


def test_one_shaky_key_keeps_practicing_and_focuses_it():
    keys = {k: solid() for k in HOME_KEYS} | {"g": solid(0.85)}
    p = plan(home_learner(keys=keys, learn_vs_practice=0.5))
    assert p.kind == "practice"
    assert "g" in p.focus_keys
    assert any("not solid yet: g" in r for r in p.reasons)


def test_the_learn_bar_slides_with_the_setting():
    keys = {k: solid(0.9) for k in HOME_KEYS}
    assert plan(home_learner(keys=keys, learn_vs_practice=1.0)).kind == "learn"  # bar 80%
    assert plan(home_learner(keys=keys, learn_vs_practice=0.0)).kind == "practice"  # bar 98%
    assert brain.solid_bar(0.5) == 0.89


def test_all_practice_needs_98_percent():
    keys = {k: solid(0.98, n=50) for k in HOME_KEYS}
    assert plan(home_learner(keys=keys, learn_vs_practice=0.0)).kind == "learn"
    keys["a"] = solid(0.96, n=50)
    assert plan(home_learner(keys=keys, learn_vs_practice=0.0)).kind == "practice"


def test_too_little_data_is_not_solid():
    keys = {k: solid() for k in HOME_KEYS} | {"h": solid(1.0, n=12)}
    p = plan(home_learner(keys=keys))
    assert p.kind == "practice"
    assert any("h (12/30 tries)" in r for r in p.reasons)


def test_placement_keys_without_data_dont_block():
    keys = {k: solid() for k in HOME_KEYS if k not in "gh"}
    p = plan(home_learner(keys=keys, placement_keys=frozenset("gh")))
    assert p.kind == "learn"


def test_needs_three_practices_since_the_last_new_lesson():
    history = [lesson("learn", 30), lesson(minutes_ago=20), lesson(minutes_ago=10)]
    p = plan(home_learner(history=history))
    assert p.kind == "practice"
    assert any("2/3 practices" in r for r in p.reasons)


def test_at_most_one_new_lesson_a_day():
    p = plan(home_learner(learns_today=1))
    assert p.kind == "practice"
    assert any("already learned" in r for r in p.reasons)


def test_nothing_left_to_learn_just_practices():
    from app.activities.teach_curriculum import lessons

    everything = frozenset(lesson_ref(l["module"], l["keys"]) for l in lessons())
    p = plan(home_learner(taught_lessons=everything))
    assert p.kind == "practice"


# --- frustration and comfort ------------------------------------------------------


def test_a_struggle_gets_a_comfort_lesson_not_a_new_letter():
    history = home_learner().history[:-1] + [lesson(minutes_ago=1, accuracy=0.7)]
    p = plan(home_learner(history=history))
    assert p.kind == "practice" and p.comfort
    assert p.difficulty == brain.COMFORT_DIFFICULTY
    assert p.duration_s == brain.COMFORT_SECONDS


def test_quitting_early_or_a_speed_crash_counts_as_frustration():
    base = home_learner().history[:-1]
    quit_early = plan(home_learner(history=base + [lesson(minutes_ago=1, finished_share=0.3)]))
    crash = plan(home_learner(history=base + [lesson(minutes_ago=1, wpm=6.0, predicted_wpm=15.0)]))
    assert quit_early.comfort and crash.comfort


def test_two_meh_lessons_in_a_row_count_as_frustration():
    history = [lesson("learn", 60 * 30), lesson(minutes_ago=6, accuracy=0.88), lesson(minutes_ago=2, accuracy=0.87)]
    assert plan(home_learner(history=history)).comfort


def test_comfort_lessons_leave_the_weak_keys_out():
    keys = {k: solid() for k in HOME_KEYS} | {"g": solid(0.7), "h": solid(0.75)}
    history = home_learner().history[:-1] + [lesson(minutes_ago=1, accuracy=0.7)]
    p = plan(home_learner(keys=keys, history=history))
    assert "g" not in p.allowed_keys and "h" not in p.allowed_keys
    assert " " in p.allowed_keys


def test_a_struggle_before_a_long_break_doesnt_count():
    history = [lesson("learn", 60 * 30), *[lesson(minutes_ago=m) for m in (300, 290)], lesson(minutes_ago=280, accuracy=0.5)]
    assert plan(home_learner(history=history)).kind == "warmup"


# --- shaping a practice lesson ---------------------------------------------------------


def practice_learner(**kw) -> BrainInput:
    return home_learner(learns_today=1, **kw)  # no new letter today: always practice


def test_regressions_come_first_in_focus():
    slipping = KeyRecord(recent_attempts=30, recent_correct=26, older_attempts=80, older_correct=78)
    keys = {k: solid() for k in HOME_KEYS} | {"d": slipping, "s": solid(0.85)}
    p = plan(practice_learner(keys=keys))
    assert p.focus_keys[0] in "ds" and "d" in p.focus_keys
    assert any(r.startswith("slipping: d") for r in p.reasons)


def test_newest_keys_get_focus():
    p = plan(practice_learner(newest_keys=("g", "h"), keys={k: solid(n=30) for k in HOME_KEYS}))
    assert set("gh") <= set(p.focus_keys)


def test_focus_is_capped():
    keys = {k: solid(0.8) for k in HOME_KEYS}
    assert len(plan(practice_learner(keys=keys)).focus_keys) <= brain.MAX_FOCUS_KEYS


def test_exceptionally_weak_bigrams_are_picked():
    def b(pair, acc, n=20):
        return BigramStat(1, pair[0], pair[1], 300.0, acc, n)

    bigrams = [b("fj", 0.97), b("jd", 0.95), b("dk", 0.96), b("sa", 0.6), b("lk", 0.93), b("a;", 0.7, n=3)]
    p = plan(practice_learner(bigrams=bigrams))
    assert p.focus_bigrams == ("sa",)  # a; has too few samples
    assert set("sa") <= set(p.focus_keys)


def test_evenly_weak_bigrams_are_not_exceptional():
    bigrams = [BigramStat(1, a, b, 300.0, 0.78, 20) for a, b in ("fj", "jd", "dk", "sa")]
    assert plan(practice_learner(bigrams=bigrams)).focus_bigrams == ()


def test_difficulty_walks_with_the_last_practice():
    great = [lesson(minutes_ago=1, accuracy=0.99, wpm=16, difficulty=0.5, predicted_wpm=15)]
    shaky = [lesson(minutes_ago=1, accuracy=0.89, wpm=15, difficulty=0.5, predicted_wpm=15)]
    assert plan(practice_learner(history=great)).difficulty == 0.6
    assert plan(practice_learner(history=shaky)).difficulty == 0.4


def test_lesson_length_follows_predicted_speed():
    slow = plan(practice_learner(fallback_wpm=5, history=[lesson(minutes_ago=1, wpm=5)]))
    fast = plan(practice_learner(fallback_wpm=30, history=[lesson(minutes_ago=1, wpm=30)]))
    assert slow.duration_s < fast.duration_s
    assert slow.predicted_wpm < fast.predicted_wpm


def test_the_goal_lands_on_an_easier_lesson():
    history = [lesson(minutes_ago=1, accuracy=0.93, difficulty=0.5, predicted_wpm=15)]
    normal = plan(practice_learner(history=history, goal_seconds=600, practiced_seconds=100))
    landing = plan(practice_learner(history=history, goal_seconds=600, practiced_seconds=540))
    assert landing.duration_s == 60
    assert landing.difficulty == normal.difficulty - brain.EASE_OFF
    assert any("daily goal lands" in r for r in landing.reasons)


def test_themes_dont_repeat_back_to_back():
    history = [lesson(minutes_ago=m, activity_id=PRACTICE_MODULES[i].id) for i, m in enumerate((9, 7, 5, 3, 1))]
    recent = {r.activity_id for r in history}
    for seed in range(20):
        assert plan(practice_learner(history=history), seed).activity_id not in recent


def test_focus_bigrams_show_up_in_practice_text():
    text = build_practice_text(
        ["s"], list(" fjdksla;gh"), 400, skill=SkillSnapshot(focus_bigrams=("sa",)), rng=random.Random(3)
    )
    assert text.count("sa") >= 8


def test_reasons_are_always_given():
    for inp in (home_learner(), practice_learner(), replace(home_learner(), history=[])):
        assert plan(inp).reasons
