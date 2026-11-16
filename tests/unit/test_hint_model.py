"""Unit tests for the fading keyboard hint (app/hint_model.py). Pure functions only."""

import random

import pytest

from app import hint_model as hm
from app.hint_model import HintDisplay, Press


def press(key="f", correct=True, latency_ms=300, support=3.0, solo=False) -> Press:
    return Press(key, correct, latency_ms, support, solo)


# --- display ---------------------------------------------------------------------


def test_full_support_is_todays_hint():
    assert hm.display(5.0) == HintDisplay(letter=True, finger_ms=0, key_ms=0)


def test_letters_band_delays_the_lights_as_support_drops():
    hi, lo = hm.display(4.9), hm.display(4.0)
    assert hi.letter and lo.letter
    assert hi.finger_ms < lo.finger_ms == 1500
    assert lo.key_ms == lo.finger_ms + 400


def test_letters_hide_below_four():
    d = hm.display(3.99)
    assert not d.letter
    assert d.finger_ms == pytest.approx(1500, abs=20)
    assert d.key_ms == d.finger_ms + 1000
    assert hm.display(3.0).finger_ms == 3000


def test_finger_only_band():
    d = hm.display(2.5)
    assert d == HintDisplay(letter=False, finger_ms=4000, key_ms=None)
    assert hm.display(2.0).finger_ms == 5000


def test_hands_only_and_below():
    assert hm.display(1.5) == HintDisplay(letter=False, finger_ms=None, key_ms=None)
    assert hm.display(0.0) == HintDisplay(letter=False, finger_ms=None, key_ms=None)


def test_display_is_monotonic_in_help():
    """Less support never shows more: letters off, lights later or never."""
    prev = hm.display(5.0)
    for i in range(500, -1, -1):
        d = hm.display(i / 100)
        assert d.letter <= prev.letter
        for now, before in ((d.finger_ms, prev.finger_ms), (d.key_ms, prev.key_ms)):
            if before is None:
                assert now is None
            elif now is not None:
                assert now >= before
        prev = d


def test_keyboard_needed_when_any_key_is_at_one_or_more():
    assert hm.keyboard_needed([0.2, 1.0])
    assert not hm.keyboard_needed([0.2, 0.99])
    assert not hm.keyboard_needed([])


def test_hint_key_folds_capitals():
    assert hm.hint_key("R") == "r"
    assert hm.hint_key(";") == ";"
    assert hm.hint_key(" ") == " "


def test_clamp():
    assert hm.clamp(7) == 5.0 and hm.clamp(-1) == 0.0 and hm.clamp(2.5) == 2.5


# --- what was lit, and how much a press counts --------------------------------------


@pytest.mark.parametrize(
    "support,latency,kind",
    [
        (5.0, 10, "key"),  # lit at once
        (3.0, 2999, "free"),
        (3.0, 3000, "finger"),
        (3.0, 4000, "key"),
        (2.5, 9000, "finger"),  # the key never lights in this band
        (1.5, 9000, "free"),  # hands only
        (0.0, 9000, "free"),
    ],
)
def test_press_kind(support, latency, kind):
    assert hm.press_kind(support, latency) == kind


def test_solo_and_no_hint_system():
    assert hm.press_kind(5.0, 9000, solo=True) == "free"
    assert hm.press_kind(None, 9000) is None


@pytest.mark.parametrize(
    "p,weight",
    [
        (press(support=None), 1.0),  # teach pages, old data: as before
        (press(support=1.5, latency_ms=9000), 1.0),  # nothing would light
        (press(support=3.0, latency_ms=500), 1.0),  # before the light
        (press(support=2.5, latency_ms=4500), 0.3),  # after the finger lit
        (press(support=3.0, latency_ms=4500), 0.0),  # after the key lit
        (press(support=4.5, latency_ms=10), 0.0),  # letters showing
        (press(support=4.5, latency_ms=10, solo=True), 1.0),  # solo line: nothing showing
    ],
)
def test_mastery_weight(p, weight):
    assert hm.mastery_weight(p) == weight


# --- the ratchet ---------------------------------------------------------------------


def a_day(support: float, accuracy: float, day_presses: int = 30, lessons: int = 10, **kw) -> float:
    """Ratchet a key through one day: `day_presses` presses over `lessons` lessons."""
    per = day_presses // lessons
    wrong = round(day_presses * (1 - accuracy))
    for i in range(lessons):
        presses = [press(correct=i * per + j >= wrong, **kw) for j in range(per)]
        support = hm.ratchet(support, presses, day_presses)
    return support


@pytest.mark.parametrize("accuracy,levels", [(1.0, -2.0), (0.95, -1.5), (0.9, -1.0), (0.8, 0.0), (0.7, 1.0)])
def test_a_day_moves_by_accuracy_above_eighty_percent(accuracy, levels):
    start = 2.5
    assert a_day(start, accuracy, day_presses=40) - start == pytest.approx(levels, abs=0.01)


@pytest.mark.parametrize("day_presses", [20, 60, 120])
def test_a_day_is_a_day_however_often_the_key_comes_up(day_presses):
    assert a_day(3.0, 0.9, day_presses=day_presses) == pytest.approx(2.0, abs=0.01)


def test_rare_keys_move_no_faster_than_the_floor():
    rare = hm.ratchet(3.0, [press()], day_presses=2)
    assert rare == pytest.approx(hm.ratchet(3.0, [press()], day_presses=hm.DAY_PRESSES_FLOOR))


def test_misses_add_help_quickly():
    assert hm.ratchet(3.0, [press(correct=False)] * 2, 30) == pytest.approx(3.0 + 2 * 10 * 0.8 / 30)


def test_right_answers_take_help_away_faster_when_remembered():
    free = hm.ratchet(3.0, [press(latency_ms=500)])
    finger = hm.ratchet(2.5, [press(support=2.5, latency_ms=4500)])
    guided = hm.ratchet(3.0, [press(latency_ms=4500)])
    assert 3.0 - free > 2.5 - finger > 3.0 - guided > 0


def test_one_lesson_drops_at_most_half_a_level():
    assert hm.ratchet(3.0, [press()] * 200) == pytest.approx(2.5)


def test_one_lesson_rises_at_most_one_and_a_half():
    assert hm.ratchet(1.0, [press(support=1.0, correct=False)] * 50) == pytest.approx(2.5)


def test_ratchet_stays_in_range():
    assert hm.ratchet(4.9, [press(support=4.9, correct=False)] * 50) == 5.0
    assert hm.ratchet(0.1, [press(support=0.1)] * 50) == 0.0


def test_ratchet_counts_the_help_a_rescue_gave():
    """Presses typed while rescued were guided, so they take little help away."""
    rescued = hm.ratchet(2.0, [press(support=5.0)] * 5)
    plain = hm.ratchet(2.0, [press(support=2.0)] * 5)
    assert 2.0 - rescued < 2.0 - plain


def test_no_presses_no_change():
    assert hm.ratchet(3.3, []) == 3.3


def test_starting_support_for_old_keys():
    assert hm.starting_support(None, mastered=False) == 5.0
    assert hm.starting_support(0.80, mastered=False) == 4.5
    assert hm.starting_support(0.92, mastered=False) == 4.0
    assert hm.starting_support(0.98, mastered=False) == 3.0
    assert hm.starting_support(0.98, mastered=True) == 2.5


# --- grown-up override and the More / Less buttons ------------------------------------


def test_effective_adds_the_nudge_and_honors_the_override():
    assert hm.effective(3.0, 0.5, "auto") == 3.5
    assert hm.effective(4.8, 1.0, "auto") == 5.0
    assert hm.effective(1.0, 0.0, "full") == 5.0
    assert hm.effective(4.0, 2.0, "off") == 0.0


def test_reliance_is_how_often_he_waits_for_lights_that_would_come():
    waits = [press(latency_ms=4500)] * 8 + [press(latency_ms=500)] * 2
    assert hm.reliance(waits, more_clicks=0) == pytest.approx(0.8)
    # no lights coming: nothing to lean on
    assert hm.reliance([press(support=1.0, latency_ms=9000)] * 5, more_clicks=0) == 0.0
    assert hm.reliance([], more_clicks=0) == 0.0


def test_more_clicks_raise_reliance():
    base = hm.reliance([press(latency_ms=500)] * 10, more_clicks=0)
    assert hm.reliance([press(latency_ms=500)] * 10, more_clicks=3) > base
    assert hm.reliance([], more_clicks=100) <= 1.0


def test_more_gives_less_to_a_learner_who_leans_on_help():
    assert hm.nudge_step("more", 0.0) == pytest.approx(hm.NUDGE_MORE_MAX)
    assert hm.nudge_step("more", 1.0) == pytest.approx(hm.NUDGE_MORE_MIN)
    assert hm.nudge_step("more", 0.3) > hm.nudge_step("more", 0.7)
    assert hm.nudge_step("less", 0.9) == hm.NUDGE_LESS


def test_nudge_offset_is_limited_and_decays():
    assert hm.apply_nudge(1.8, 1.0) == hm.NUDGE_LIMIT
    assert hm.apply_nudge(-1.8, -0.5) == -hm.NUDGE_LIMIT
    assert hm.decay_nudge(1.0) == 0.5
    assert hm.decay_nudge(0.04) == 0.0  # tiny leftovers snap to zero


# --- solo lines ------------------------------------------------------------------------


def test_no_solo_lines_while_letters_show_or_in_an_easy_lesson():
    rng = random.Random(1)
    assert hm.plan_solo_lines(rng, [4.0, 3.5], comfort=False) == []
    assert hm.plan_solo_lines(rng, [1.0, 2.0], comfort=True) == []


def test_solo_lines_are_random_never_the_first_and_about_a_quarter():
    lines = hm.plan_solo_lines(random.Random(7), [2.0, 3.0], comfort=False)
    assert 0 not in lines
    assert lines == sorted(set(lines))
    assert all(0 < i < hm.SOLO_LINES_PLANNED for i in lines)
    total = sum(len(hm.plan_solo_lines(random.Random(s), [2.0], comfort=False)) for s in range(200))
    assert total / 200 == pytest.approx(hm.SOLO_CHANCE * (hm.SOLO_LINES_PLANNED - 1), rel=0.15)


def test_no_solo_lines_without_hint_keys():
    assert hm.plan_solo_lines(random.Random(1), [], comfort=False) == []


# --- coins ------------------------------------------------------------------------------


def test_free_bonus_pays_for_right_presses_before_any_light():
    assert hm.free_bonus([press(latency_ms=500)] * 10) == hm.FREE_BONUS_MAX
    half = [press(latency_ms=500)] * 5 + [press(latency_ms=4500)] * 5
    assert hm.free_bonus(half) == hm.FREE_BONUS_MAX // 2


def test_wrong_guesses_never_pay_more_than_waiting():
    waited = [press(latency_ms=4500)] * 10
    guessed = [press(latency_ms=200, correct=False)] * 10
    assert hm.free_bonus(guessed) == hm.free_bonus(waited) == 0


def test_free_bonus_ignores_presses_outside_the_hint_system():
    assert hm.free_bonus([press(support=None)] * 10) == 0
    assert hm.free_bonus([]) == 0


def test_solo_bonus():
    good = [press(solo=True)] * 9 + [press(solo=True, correct=False)]
    assert hm.solo_bonus(good) == hm.SOLO_BONUS
    assert hm.solo_bonus(good + [press(solo=True, correct=False)]) == 0  # below 90%
    assert hm.solo_bonus([press(solo=True)] * 4) == 0  # too few to count
    assert hm.solo_bonus([press()] * 20) == 0  # not solo


def test_graduations():
    assert hm.graduations(4.2, 3.9) == [hm.LETTERS_OFF]
    assert hm.graduations(4.2, 1.9) == [hm.LETTERS_OFF, hm.BY_HEART]
    assert hm.graduations(3.0, 2.1) == []
    assert hm.graduations(1.9, 2.5) == []  # going back up takes nothing away, pays nothing


# --- measuring the lift ---------------------------------------------------------------


def test_lift_per_key():
    presses = (
        [press(key="j", latency_ms=4500, support=3.0)] * 18  # aided, right
        + [press(key="j", latency_ms=4500, support=3.0, correct=False)] * 2
        + [press(key="j", latency_ms=600, support=3.0)] * 6  # early, right
        + [press(key="j", latency_ms=600, support=3.0, correct=False)] * 4
    )
    out = hm.lift(presses, min_presses=20)
    j = out["j"]
    assert (j.aided, j.aided_correct, j.free, j.free_correct) == (20, 18, 10, 6)
    assert (j.early, j.waited_for) == (6, 30)
    assert j.aided_ms == 4500 and j.free_ms == 600
    assert j.lift == pytest.approx(0.9 - 0.6)


def test_lift_prefers_solo_lines_as_the_baseline():
    presses = (
        [press(key="j", latency_ms=4500)] * 20
        + [press(key="j", latency_ms=500)] * 10  # free and right: flattering
        + [press(key="j", solo=True)] * 5
        + [press(key="j", solo=True, correct=False)] * 5
    )
    assert hm.lift(presses)["j"].lift == pytest.approx(1.0 - 0.5)


def test_lift_none_without_both_sides():
    assert hm.lift([press(key="j", latency_ms=500)] * 30)["j"].lift is None


def test_rare_keys_pool_into_their_finger():
    presses = [press(key="r")] * 5 + [press(key="t")] * 5 + [press(key="f")] * 25
    out = hm.lift(presses, min_presses=20)
    assert set(out) == {"f", "finger:left_index"}
    assert out["finger:left_index"].free == 10


def test_lift_skips_presses_outside_the_hint_system():
    assert hm.lift([press(support=None)] * 30) == {}


# --- the rescue (this lesson only) -------------------------------------------------------


def test_rescue_waits_for_a_few_presses():
    assert hm.rescue_step(0.0, [False] * 4) == 0.0


def test_rescue_climbs_while_lost_all_the_way_to_full_help():
    offset, recent = 0.0, []
    for _ in range(40):
        recent.append(False)
        offset = hm.rescue_step(offset, recent)
    assert offset == hm.MAX_SUPPORT


def test_rescue_holds_in_between_and_eases_when_doing_well():
    in_between = [True] * 4 + [False]  # 80%
    assert hm.rescue_step(2.0, in_between * 3) == 2.0
    assert hm.rescue_step(2.0, [True] * 15) == pytest.approx(2.0 - hm.RESCUE_DOWN)
    # a miss doesn't ease it, even at 90%+
    assert hm.rescue_step(2.0, [True] * 14 + [False]) == 2.0


def test_rescue_never_goes_below_zero():
    assert hm.rescue_step(0.05, [True] * 15) == 0.0
    assert hm.rescue_step(0.0, [True] * 15) == 0.0


def test_rescue_only_looks_at_the_recent_window():
    old_trouble = [False] * 30 + [True] * hm.RESCUE_WINDOW
    assert hm.rescue_step(3.0, old_trouble) < 3.0


def test_rescue_params_match_the_constants():
    p = hm.rescue_params()
    assert (p["window"], p["below"], p["ease"], p["up"], p["down"]) == (
        hm.RESCUE_WINDOW, hm.RESCUE_BELOW, hm.RESCUE_EASE, hm.RESCUE_UP, hm.RESCUE_DOWN
    )
