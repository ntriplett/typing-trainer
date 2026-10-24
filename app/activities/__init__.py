"""The activity registry (PLAN.md Section 7): the scheduler and API only
ever look things up here by id or kind -- adding a new activity later
means adding one line to REGISTRY, not touching the scheduler.
"""

from __future__ import annotations

from app.activities.base import Activity
from app.activities.game_random_keys import GameRandomKeys
from app.activities.practice_modules import PRACTICE_MODULES
from app.activities.teach_random_keys import TeachRandomKeys

REGISTRY: dict[str, Activity] = {
    activity.id: activity
    for activity in (
        TeachRandomKeys(),
        *PRACTICE_MODULES,  # also used for warmups (short and easy)
        GameRandomKeys(),
    )
}


def get_activity(activity_id: str) -> Activity:
    return REGISTRY[activity_id]


def activities_by_kind(kind: str) -> list[Activity]:
    return [a for a in REGISTRY.values() if a.kind == kind]
