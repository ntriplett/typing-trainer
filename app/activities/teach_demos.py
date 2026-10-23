"""The teach-demo registry: 3 experimental "teach" variants for you to
compare, deliberately kept OUT of the main activity REGISTRY (app/
activities/__init__.py) so they can't be picked up by the live
scheduler and don't disturb the "exactly one activity per kind"
assumption production code relies on. Only the dedicated demo API/page
(app/main.py's /api/teach-demo/* routes, web/teach_demo.html) uses this.
"""

from __future__ import annotations

from app.activities.base import Activity
from app.activities.teach_hand_anchor_demo import TeachHandAnchorDemo
from app.activities.teach_reach_return_demo import TeachReachReturnDemo
from app.activities.teach_staged_combo_demo import TeachStagedComboDemo

DEMO_REGISTRY: dict[str, Activity] = {
    activity.id: activity
    for activity in (
        TeachHandAnchorDemo(),
        TeachReachReturnDemo(),
        TeachStagedComboDemo(),
    )
}

DEMO_DESCRIPTIONS: dict[str, str] = {
    "teach_hand_anchor_demo_v1": (
        "Hand Anchor: diagram, home-row anchor check, a short isolated drill, then combo practice. "
        "The textbook baseline structure."
    ),
    "teach_reach_return_demo_v1": (
        "Reach & Return: diagram, then a drill that alternates the new key with its OWN home key "
        "(f r f r...) to practice the actual reach-and-return motion, then combo practice."
    ),
    "teach_staged_combo_demo_v1": (
        "Staged Combo Builder: diagram, a short drill, then combo practice that widens one key at a "
        "time (1 known key, then 2, then 3) instead of jumping straight to the full mix."
    ),
}


def get_demo_activity(activity_id: str) -> Activity:
    return DEMO_REGISTRY[activity_id]


def list_demo_activities() -> list[dict]:
    return [
        {"id": activity_id, "description": DEMO_DESCRIPTIONS[activity_id]}
        for activity_id in DEMO_REGISTRY
    ]
