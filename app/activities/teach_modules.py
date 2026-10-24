"""The keyboard-driven teach modules (intro, rows, numbers, capitals),
kept OUT of the live activity REGISTRY until they're strung together into
lessons, so the scheduler can't pick them up yet. The /teach page and the
/api/teach/* routes in app/main.py use this.
"""

from __future__ import annotations

from app.activities.teach_intro_home_row import TeachIntroHomeRow

TEACH_REGISTRY = {activity.id: activity for activity in (TeachIntroHomeRow(),)}


def get_teach_module(activity_id: str):
    return TEACH_REGISTRY[activity_id]


def list_teach_modules() -> list[dict]:
    return [
        {"id": a.id, "title": a.title, "description": a.description}
        for a in TEACH_REGISTRY.values()
    ]
