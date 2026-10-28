"""Games (PLAN.md §11g): typing where the word you type is the choice you make.

Each game is self-contained: about 5 rounds of about a minute. Losing is
soft (the round ends, or you try again) and each round scores points,
tallied arcade-style and paid in coins as soon as the round ends. The game
rules run in the browser (web/static/js/crow_patrol.js, pet_battle.js);
the backend supplies the words and the per-round numbers, and pays coins.

Words: real words as soon as the taught letters can spell enough of them
(word_bank.py), favoring focus letters and, as difficulty goes up, weak
letters and pairs. Until then, made-up words from practice_text.py. Words
are grouped by length ("short", "medium", "long"); games pick from those
groups and keep the first letters on screen different, so the first key
you press picks one.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent, score_attempt
from app.activities.practice_text import SkillSnapshot, build_practice_text, focus_callout, letter_pool
from app.activities.word_bank import WORDS

# The first key picks a target, so a game needs a few different first letters.
MIN_LETTERS = 4
WORDS_PER_GROUP = 120
WORD_LENGTHS = {"short": (2, 3), "medium": (4, 5), "long": (6, 8)}
# A group switches to only real words once this many different ones fit.
REAL_WORDS_ENOUGH = 8
# A single round can't score more than this (a guard on what the browser sends).
MAX_ROUND_SCORE = 5000


def word_groups(
    focus_keys: list[str],
    allowed_keys: list[str],
    difficulty: float,
    skill: SkillSnapshot | None,
    rng: random.Random,
    count: int = WORDS_PER_GROUP,
) -> dict[str, list[str]]:
    """{"short": [...], "medium": [...], "long": [...]}, each word within its
    group's length range. Repeats are fine: they're how weighting shows up."""
    skill = skill or SkillSnapshot()
    focus = set(focus_keys) - {" "}
    allowed = (set(allowed_keys) | focus) - {" "}
    weak_keys = set(skill.weak_keys)
    groups = {}
    for name, (lo, hi) in WORD_LENGTHS.items():
        real = [w for w in WORDS if lo <= len(w) <= hi and set(w) <= allowed]
        if len(real) >= REAL_WORDS_ENOUGH:
            weights = [
                1
                + 2 * bool(set(w) & focus)
                + difficulty * sum(ch in weak_keys for ch in w)
                + 3 * difficulty * sum(b in w for b in skill.weak_bigrams)
                for w in real
            ]
            groups[name] = rng.choices(real, weights, k=count)
            continue
        words: list[str] = []
        while len(words) < count:
            text = build_practice_text(
                focus_keys, allowed_keys, count * (hi + 1), difficulty, skill, rng, word_len=(lo, hi),
                real_word_share=0.5,
            )
            words += [w for w in text.split() if lo <= len(w) <= hi]
        groups[name] = words[:count]
    return groups


@dataclass(frozen=True, slots=True)
class GameModule:
    id: str
    title: str
    blurb: str
    how_to: str  # instructions, keycap markup
    game: str  # which front-end game runs it
    coins_per_point: float
    levels: tuple[dict, ...] = field(default=())
    kind: str = "game"

    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool:
        letters = {k for k in list(focus_keys) + list(allowed_keys) if k.isalpha()}
        return len(letters) >= MIN_LETTERS

    def generate(
        self,
        focus_keys: list[str],
        allowed_keys: list[str],
        duration_s: int = 300,
        rng: random.Random | None = None,
        chars_per_second: float = 2.0,
        difficulty: float = 0.5,
        skill: SkillSnapshot | None = None,
    ) -> ActivityContent:
        """duration_s is part of the Activity protocol; games are sized by rounds instead."""
        rng = rng or random.Random()
        # letters only: ";" makes odd words, and a crow can't be called "hj;"
        focus_keys = [k for k in focus_keys if k.isalpha()]
        allowed_keys = [k for k in allowed_keys if k.isalpha() or k == " "]
        _, pool = letter_pool(focus_keys, allowed_keys)
        callout = focus_callout(focus_keys)
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=list(dict.fromkeys(list(allowed_keys) + list(focus_keys))),
            prompt="",
            instructions=f"{self.how_to} {callout}".strip(),
            title=self.title,
            game={
                "game": self.game,
                "difficulty": difficulty,
                "levels": [scale_level(level, difficulty) for level in self.levels],
                "words": word_groups(focus_keys, allowed_keys, difficulty, skill, rng),
                "letters": pool,
                # typing speed, so games can pace themselves to the learner
                "chars_per_second": round(chars_per_second, 2),
            },
        )

    def score(self, content: ActivityContent, keystrokes: list[KeystrokeEvent]) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        """Games pay by points (coins_for); the plain rule has nothing to go on."""
        return 0

    def coins_for(self, points: int) -> int:
        return int(max(0, min(points, MAX_ROUND_SCORE)) * self.coins_per_point)


def scale_level(level: dict, difficulty: float) -> dict:
    """Difficulty also nudges the game's own numbers: `speed` (crow flight)
    and `foe_hp` (critter HP) go 0.8x (easy) .. 1.2x (hard)."""
    factor = 0.8 + 0.4 * max(0.0, min(1.0, difficulty))
    out = dict(level)
    if "speed" in out:
        out["speed"] = round(out["speed"] * factor, 2)
    if "foe_hp" in out:
        out["foe_hp"] = max(3, round(out["foe_hp"] * factor))
    return out


CROW_PATROL = GameModule(
    id="game_crow_patrol_v1",
    title="Crow Patrol",
    blurb="Crows are after your pumpkins! Type a crow's word to shoo it away.",
    how_to="Type the word on a crow to shoo it. Save your pumpkins!",
    game="crow_patrol",
    coins_per_point=0.05,  # 1 coin per 20 points
    # seconds: round length; spawn: seconds between crows; max_crows: on screen at once;
    # speed: flight speed multiplier; types: crow kinds (crow_patrol.js) and how often each
    # comes; new: the kind this round introduces.
    levels=(
        {"name": "Morning", "seconds": 60, "spawn": 3.6, "max_crows": 2, "speed": 1.0,
         "types": {"little": 3, "crow": 2}, "new": "crow"},
        {"name": "Midday", "seconds": 60, "spawn": 3.4, "max_crows": 3, "speed": 1.05,
         "types": {"little": 3, "crow": 2, "big": 1}, "new": "big"},
        {"name": "Afternoon", "seconds": 60, "spawn": 3.2, "max_crows": 3, "speed": 1.1,
         "types": {"little": 2, "crow": 2, "big": 1, "caller": 1.5}, "new": "caller"},
        {"name": "Sunset", "seconds": 60, "spawn": 3.0, "max_crows": 4, "speed": 1.15,
         "types": {"little": 2, "crow": 2, "big": 1, "caller": 1, "squirrel": 1.5}, "new": "squirrel"},
        {"name": "Moonrise", "seconds": 60, "spawn": 2.8, "max_crows": 4, "speed": 1.2,
         "types": {"little": 2, "crow": 2, "big": 1.5, "caller": 1, "squirrel": 1, "golden": 0.7}, "new": "golden"},
    ),
)

PET_BATTLE = GameModule(
    id="game_pet_battle_v1",
    title="Pet Battles",
    blurb="Pick a partner and play friendly battles with wild critters. Moves are words, so choose well!",
    how_to="Type a move's word to use it. Watch what the critter will do next!",
    game="pet_battle",
    coins_per_point=0.15,
    # foe: a critter in pet_battle.js (its type and tricks; its look is a v3 pet,
    # app/pet_care.py battle_pets); foe_hp: its HP.
    levels=(
        {"name": "Meadow", "foe": "bunny", "foe_hp": 12},
        {"name": "Rocks", "foe": "lizard", "foe_hp": 14},
        {"name": "Hillside", "foe": "goat", "foe_hp": 16},
        {"name": "Woods", "foe": "fox", "foe_hp": 17},
        {"name": "Mountain", "foe": "llama", "foe_hp": 20},
    ),
)

GAME_MODULES = (CROW_PATROL, PET_BATTLE)
