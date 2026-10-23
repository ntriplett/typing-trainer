"""Read-side aggregations for the analysis page and the recommender.

Split deliberately into:
  - finger_stats(): pure, no DB -- derived entirely from already-fetched
    key_stat rows, so it's trivially unit-testable.
  - key_report() / worst_bigrams() / daily_trend(): DB-backed reads
    that shape key_stat/bigram_stat/session_event rows for display.

Nothing here writes anything; this is purely "what does the data say."
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from app import db
from app.finger_map import ALL_FINGERS, KEY_TO_FINGER
from app.models import BigramStat, KeyStat
from app.skill_model import KEY_ORDER


@dataclass(frozen=True, slots=True)
class FingerStat:
    finger: str
    keys: list[str]
    accuracy: float | None
    avg_confidence: float | None
    sample_count: int


def finger_stats(key_stats: dict[str, KeyStat]) -> dict[str, FingerStat]:
    """Aggregate per-key stats up to per-finger stats, weighted by each
    key's sample_count so a heavily-drilled key counts more than one
    barely touched. Keys with no attempts yet don't contribute.
    """
    keys_by_finger: dict[str, list[str]] = {finger: [] for finger in ALL_FINGERS}
    for key, finger in KEY_TO_FINGER.items():
        keys_by_finger[finger].append(key)

    result: dict[str, FingerStat] = {}
    for finger, keys in keys_by_finger.items():
        total_samples = 0
        accuracy_sum = 0.0
        confidence_sum = 0.0
        for key in keys:
            stat = key_stats.get(key)
            if stat is None or stat.sample_count == 0:
                continue
            total_samples += stat.sample_count
            confidence_sum += stat.confidence * stat.sample_count
            if stat.accuracy_rolling is not None:
                accuracy_sum += stat.accuracy_rolling * stat.sample_count

        result[finger] = FingerStat(
            finger=finger,
            keys=keys,
            accuracy=(accuracy_sum / total_samples) if total_samples else None,
            avg_confidence=(confidence_sum / total_samples) if total_samples else None,
            sample_count=total_samples,
        )
    return result


def key_report(conn, learner_id: int) -> list[dict]:
    """Every key in KEY_ORDER with its current stats, for the keyboard
    heatmap -- including never-attempted keys, so the page can show
    them as "not started" rather than omitting them.
    """
    stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    report = []
    for key in KEY_ORDER:
        stat = stats.get(key)
        report.append(
            {
                "key": key,
                "finger": KEY_TO_FINGER.get(key),
                "confidence": stat.confidence if stat else 0.0,
                "accuracy": stat.accuracy_rolling if stat else None,
                "sample_count": stat.sample_count if stat else 0,
                "unlocked": stat.unlocked_at is not None if stat else False,
                "mastered": stat.mastered_at is not None if stat else False,
            }
        )
    return report


def worst_bigrams(
    conn, learner_id: int, limit: int = 10, min_samples: int = 3
) -> list[BigramStat]:
    """The letter-pairs most worth drilling: lowest accuracy first,
    then slowest among equally-accurate pairs. Pairs with too few
    samples are excluded -- a single unlucky attempt shouldn't top
    the list (same reasoning as the per-key minimum-sample-count gate).
    """
    stats = db.list_bigram_stats(conn, learner_id)
    eligible = [
        s for s in stats if s.sample_count >= min_samples and s.accuracy_rolling is not None
    ]
    return sorted(eligible, key=lambda s: (s.accuracy_rolling, -(s.ema_time_ms or 0)))[:limit]


def daily_trend(conn, learner_id: int, days: int | None = None, now: datetime | None = None) -> list[dict]:
    """One row per calendar day with completed activity: average WPM
    and accuracy across that day's activity steps. This is the
    "detailed performance over time" view from the original brief.
    """
    rows = conn.execute(
        """
        SELECT se.started_at, se.summary_stats
        FROM session_event se
        JOIN session s ON se.session_id = s.id
        WHERE s.learner_id = ?
        ORDER BY se.started_at
        """,
        (learner_id,),
    ).fetchall()

    cutoff_day = None
    if days is not None:
        reference = now or datetime.utcnow()
        cutoff_day = (reference.date() - timedelta(days=days)).isoformat()

    by_day: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        stats = json.loads(row["summary_stats"] or "{}")
        if "wpm" not in stats or "accuracy" not in stats:
            continue
        day = row["started_at"][:10]
        if cutoff_day is not None and day < cutoff_day:
            continue
        by_day[day].append((stats["wpm"], stats["accuracy"]))

    trend = []
    for day in sorted(by_day):
        entries = by_day[day]
        trend.append(
            {
                "date": day,
                "avg_wpm": sum(w for w, _ in entries) / len(entries),
                "avg_accuracy": sum(a for _, a in entries) / len(entries),
                "count": len(entries),
            }
        )
    return trend
