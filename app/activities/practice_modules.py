"""Practice modules: the plain one plus 10 themed ones. They share one text
generator (practice_text.py); each theme has its own scene in the browser
(web/static/js/practice_scenes.js), its own blurb, and its own word shape.

Warmups are practice modules too, just run short and easy (the scheduler
sets duration and difficulty). There's no separate eval: practice results
feed the skill model, and that's the evaluation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent, combined_pool, default_coins, score_attempt
from app.activities.practice_text import SkillSnapshot, build_practice_text, focus_callout

DEFAULT_DIFFICULTY = 0.5


@dataclass(frozen=True, slots=True)
class PracticeModule:
    id: str
    title: str
    blurb: str  # one short sentence: what the theme does
    scene: str | None = None  # practice_scenes.js scene id; None = plain
    word_len: tuple[int, int] = (2, 5)
    real_word_share: float = 0.3
    kind: str = "practice"

    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool:
        return any(k != " " for k in focus_keys + allowed_keys)

    def generate(
        self,
        focus_keys: list[str],
        allowed_keys: list[str],
        duration_s: int,
        rng: random.Random | None = None,
        chars_per_second: float = 2.0,
        difficulty: float = DEFAULT_DIFFICULTY,
        skill: SkillSnapshot | None = None,
    ) -> ActivityContent:
        length = max(12, int(duration_s * chars_per_second))
        prompt = build_practice_text(
            focus_keys,
            allowed_keys,
            length,
            difficulty=difficulty,
            skill=skill,
            rng=rng,
            word_len=self.word_len,
            real_word_share=self.real_word_share,
        )
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=combined_pool(focus_keys, allowed_keys),
            prompt=prompt,
            instructions=" ".join(filter(None, [self.blurb, focus_callout(focus_keys)])),
            title=self.title,
            scene=self.scene,
        )

    def score(self, content: ActivityContent, keystrokes: list[KeystrokeEvent]) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        return default_coins(content, result)


PRACTICE_MODULES: tuple[PracticeModule, ...] = (
    # The plain baseline keeps its old id so history stays readable.
    PracticeModule("practice_random_keys_v1", "Practice", "Type the letters, nice and steady."),
    PracticeModule(
        "practice_fishing_v1", "Gone fishing", "Every right key pulls the fish closer to your hook. A mistake scares it off!", "fishing"
    ),
    PracticeModule(
        "practice_garden_v1", "Garden rows", "Each word you finish plants a seed. Keep typing to make them grow.", "garden"
    ),
    PracticeModule(
        "practice_pet_walk_v1", "Puppy walk", "Keep typing to walk your puppy home. Mistakes make it stop and sniff.", "pet_walk"
    ),
    PracticeModule("practice_rocket_v1", "Moon rocket", "Right keys fire the engine. Fly all the way to the moon!", "rocket"),
    PracticeModule(
        "practice_potion_v1",
        "Potion lab",
        "Each word drops an ingredient in the pot. A mistake makes a puff of smoke!",
        "potion",
        real_word_share=0.5,
    ),
    PracticeModule("practice_hike_v1", "Mountain hike", "Every right key is a step up the trail. Reach the flag!", "hike"),
    PracticeModule(
        "practice_leaves_v1", "Leaf catcher", "Leaves are falling! Each right key catches one in your basket.", "leaves"
    ),
    PracticeModule(
        "practice_stars_v1",
        "Star map",
        "Each word lights a star. Finish to see the whole picture in the sky.",
        "stars",
        word_len=(2, 3),
        real_word_share=0.2,
    ),
    PracticeModule(
        "practice_campfire_v1", "Campfire", "Keep the fire cozy! Right keys add sparks, mistakes let it shrink.", "campfire"
    ),
    PracticeModule(
        "practice_frog_v1", "Lily pad hop", "Finish a word to hop to the next lily pad. Don't slip!", "frog", word_len=(3, 5)
    ),
)
