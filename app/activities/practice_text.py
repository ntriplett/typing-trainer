"""Practice text: what warmups and practice modules ask the learner to type.

Inputs:
  - focus keys: what this step works on. Each focus letter shows up about
    FOCUS_WEIGHT (3x) as often as each other allowed letter.
  - allowed keys: everything taught so far; nothing outside it ever appears.
  - length: how many characters to produce (callers turn seconds into
    characters with the learner's typing speed).
  - difficulty, 0.0-1.0: how many of the learner's weak letters and weak
    letter pairs (bigrams) get put in a row. Easy never puts two weak
    letters side by side; hard chains weak pairs into whole words.
  - skill: the learner's weak spots (SkillSnapshot), from their stats.

Words are a mix of pseudo-words from the pools and, when the taught letters
can spell some, real words from word_bank.py.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.activities.word_bank import WORDS
from app.models import BigramStat, KeyStat

FOCUS_WEIGHT = 3
# A key or bigram is "weak" below this rolling accuracy, once it has enough samples.
WEAK_ACCURACY = 0.9
MIN_SAMPLES = 5


@dataclass(frozen=True, slots=True)
class SkillSnapshot:
    """The learner's weak spots, weakest first."""

    weak_keys: tuple[str, ...] = ()
    weak_bigrams: tuple[str, ...] = field(default=())  # "ei" = typing e then i


def snapshot_from_stats(
    key_stats: dict[str, KeyStat], bigram_stats: list[BigramStat] | None = None
) -> SkillSnapshot:
    def weak(acc: float | None, samples: int) -> bool:
        return acc is not None and samples >= MIN_SAMPLES and acc < WEAK_ACCURACY

    keys = sorted(
        (s for s in key_stats.values() if s.key != " " and weak(s.accuracy_rolling, s.sample_count)),
        key=lambda s: s.accuracy_rolling,
    )
    bigrams = sorted(
        (b for b in bigram_stats or [] if " " not in (b.key1, b.key2) and weak(b.accuracy_rolling, b.sample_count)),
        key=lambda b: b.accuracy_rolling,
    )
    return SkillSnapshot(tuple(s.key for s in keys), tuple(b.key1 + b.key2 for b in bigrams))


def letter_pool(focus_keys: list[str], allowed_keys: list[str]) -> tuple[list[str], list[str]]:
    """(focus letters, all letters) with space removed; falls back to
    whichever is non-empty."""
    focus = [k for k in dict.fromkeys(focus_keys) if k != " "]
    pool = [k for k in dict.fromkeys(list(allowed_keys) + focus) if k != " "]
    if not pool:
        raise ValueError("Need at least 1 focus or allowed letter to build practice")
    return focus, pool


def max_weak_run(difficulty: float) -> int:
    """Most weak letters allowed back to back: 1 (easy) .. 5 (hard)."""
    return 1 + round(max(0.0, min(1.0, difficulty)) * 4)


def build_practice_text(
    focus_keys: list[str],
    allowed_keys: list[str],
    length: int,
    difficulty: float = 0.5,
    skill: SkillSnapshot | None = None,
    rng: random.Random | None = None,
    word_len: tuple[int, int] = (2, 5),
    real_word_share: float = 0.3,
) -> str:
    rng = rng or random.Random()
    skill = skill or SkillSnapshot()
    focus, pool = letter_pool(focus_keys, allowed_keys)
    weights = [FOCUS_WEIGHT if k in focus else 1 for k in pool]

    weak = {k for k in skill.weak_keys if k in pool}
    calm = [k for k in pool if k not in weak]
    calm_weights = [FOCUS_WEIGHT if k in focus else 1 for k in calm]
    weak_pairs = [b for b in skill.weak_bigrams if b[0] in pool and b[1] in pool]
    run_limit = max_weak_run(difficulty)

    allowed_set = set(pool)
    real_words = [w for w in WORDS if set(w) <= allowed_set and len(w) <= word_len[1] + 2]
    focused_real = [w for w in real_words if set(w) & set(focus)] or real_words

    def pseudo_word() -> str:
        size = rng.randint(*word_len)
        out: list[str] = []
        run = 0
        while len(out) < size:
            if run >= run_limit and calm:
                ch = rng.choices(calm, calm_weights)[0]
            else:
                ch = rng.choices(pool, weights)[0]
            if len(out) >= 2 and out[-1] == out[-2] == ch:
                continue  # no "fff"
            out.append(ch)
            run = run + 1 if ch in weak else 0
        return "".join(out)

    def tricky_word() -> str:
        """Weak pairs chained end to start where possible ("ei" + "it" -> "eit")."""
        word = rng.choice(weak_pairs)
        pairs_used = 1
        while len(word) < word_len[1] and pairs_used < run_limit:
            follow = [b for b in weak_pairs if b[0] == word[-1]]
            word += rng.choice(follow)[1] if follow else rng.choice(weak_pairs)
            pairs_used += 1
        return word

    words: list[str] = []
    total = 0
    while total < length:
        roll = rng.random()
        if weak_pairs and roll < difficulty * 0.4:
            word = tricky_word()
        elif focused_real and roll > 1 - real_word_share:
            word = rng.choice(focused_real)
        else:
            word = pseudo_word()
        words.append(word)
        total += len(word) + 1
    return " ".join(words)


def focus_callout(focus_keys: list[str]) -> str:
    """"Focus letters: [E] and [I]." for instructions (keycap markup)."""
    letters = [k for k in dict.fromkeys(focus_keys) if k != " "]
    if not letters:
        return ""
    caps = [f"[{k}]" for k in letters]
    joined = caps[0] if len(caps) == 1 else ", ".join(caps[:-1]) + " and " + caps[-1]
    return f"Focus {'letter' if len(caps) == 1 else 'letters'}: {joined}."
