"""Games (PLAN.md §11g): typing where the word you type is the choice you make.

Each game is self-contained: about 5 levels of about a minute. Losing a
level is soft (you try it again) and the score is the number of
successes (crows shooed, battles won). The game rules run in the browser
(web/static/js/crow_patrol.js, pet_battle.js); the backend supplies the
words and the per-level numbers, and pays coins per success.

Words come from practice_text.py, so they use only the allowed letters,
favor the focus letters, and put in more weak letters and pairs as
difficulty goes up. Words are grouped by length ("short", "medium",
"long"); games pick from those groups and keep the first letters of
the words on screen different, so the first key you press picks one.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent, score_attempt
from app.activities.practice_text import SkillSnapshot, build_practice_text, focus_callout, letter_pool

# The first key picks a target, so a game needs a few different first letters.
MIN_LETTERS = 4
WORDS_PER_GROUP = 120
WORD_LENGTHS = {"short": (2, 3), "medium": (4, 5), "long": (6, 7)}


def word_groups(
    focus_keys: list[str],
    allowed_keys: list[str],
    difficulty: float,
    skill: SkillSnapshot | None,
    rng: random.Random,
    count: int = WORDS_PER_GROUP,
) -> dict[str, list[str]]:
    """{"short": [...], "medium": [...], "long": [...]}, each word within its
    group's length range."""
    groups = {}
    for name, (lo, hi) in WORD_LENGTHS.items():
        words: list[str] = []
        while len(words) < count:
            text = build_practice_text(
                focus_keys, allowed_keys, count * (hi + 1), difficulty, skill, rng, word_len=(lo, hi)
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
    coins_per_success: int
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
        """duration_s and chars_per_second are part of the Activity protocol;
        games are sized by levels instead."""
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
        """Games pay per success (coins_for); the plain rule has nothing to go on."""
        return 0

    def coins_for(self, successes: int) -> int:
        return max(0, successes) * self.coins_per_success


def scale_level(level: dict, difficulty: float) -> dict:
    """Difficulty also nudges the game's own numbers: `speed` keys (crow
    flight speed) go 0.8x (easy) .. 1.2x (hard), and `foe_hp` goes 0.8x .. 1.2x."""
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
    coins_per_success=3,
    # seconds: level length; spawn: seconds between crows; max_crows: on screen at once;
    # speed: field widths per second-ish (the front-end turns it into flight time).
    levels=(
        {"name": "Morning", "seconds": 60, "spawn": 4.0, "max_crows": 2, "speed": 1.0, "words": "short"},
        {"name": "Midday", "seconds": 60, "spawn": 3.4, "max_crows": 3, "speed": 1.1, "words": "short"},
        {"name": "Afternoon", "seconds": 60, "spawn": 3.4, "max_crows": 3, "speed": 1.1, "words": "medium"},
        {"name": "Sunset", "seconds": 60, "spawn": 3.0, "max_crows": 3, "speed": 1.2, "words": "medium"},
        {"name": "Moonrise", "seconds": 60, "spawn": 3.0, "max_crows": 4, "speed": 1.2, "words": "mixed"},
    ),
)

PET_BATTLE = GameModule(
    id="game_pet_battle_v1",
    title="Pet Battles",
    blurb="Your pet plays a friendly battle with wild critters. Moves are words, so choose well!",
    how_to="Type a move's word to use it. Watch what the critter will do next!",
    game="pet_battle",
    coins_per_success=25,
    # foe: a pet species (pets.js art); foe_hp: its energy to tire out;
    # foe_power: 1-3, which moves it knows (wind-ups and guards come later).
    levels=(
        {"name": "Meadow", "foe": "bunny", "foe_hp": 10, "foe_power": 1},
        {"name": "Hedge", "foe": "hedgehog", "foe_hp": 12, "foe_power": 1},
        {"name": "Hillside", "foe": "goat", "foe_hp": 14, "foe_power": 2},
        {"name": "Woods", "foe": "fox", "foe_hp": 15, "foe_power": 2},
        {"name": "Mountain", "foe": "llama", "foe_hp": 18, "foe_power": 3},
    ),
)

GAME_MODULES = (CROW_PATROL, PET_BATTLE)
