"""Aggregate user signals for the daily plan (US-4.1).

Pure reads — no AI calls, no mutations. Produces a flat dict that plan_service
consumes to decide which activities to propose.
"""

from datetime import datetime, timezone

import config
from services import firebase_service

LISTENING_TYPES = ("dictation", "gap_fill", "comprehension")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _count_due_srs(telegram_id) -> int:
    """Count vocabulary words whose srs_next_review is <= now."""
    # Reuse existing bounded query; cap at 200 to avoid full-collection scans.
    due = firebase_service.get_due_words(telegram_id, limit=200)
    return len(due)


def _weakest_listening_type(history: list[dict]) -> str:
    """Return the exercise type with the lowest mean score; fallback dictation."""
    by_type: dict[str, list[float]] = {t: [] for t in LISTENING_TYPES}
    for h in history:
        t = h.get("exercise_type")
        s = h.get("score")
        if t in by_type and isinstance(s, (int, float)):
            by_type[t].append(float(s))

    means: list[tuple[str, float, int]] = []
    for t in LISTENING_TYPES:
        vals = by_type[t]
        if not vals:
            # Unseen types have priority (need data)
            means.append((t, -1.0, 0))
        else:
            means.append((t, sum(vals) / len(vals), len(vals)))

    # Lowest mean first; ties broken by fewer samples.
    means.sort(key=lambda x: (x[1], x[2]))
    return means[0][0]


def build_weakness_profile(user: dict) -> dict:
    """Return a flat dict of weakness signals for the current user."""
    user_id = user["id"]
    date_str = config.local_date_str()

    due_srs = _count_due_srs(user_id)
    total_words = int(user.get("total_words", 0) or 0)

    daily_doc = firebase_service.get_user_daily_words(user_id, date_str)
    daily_words_done_today = bool(daily_doc)

    writing_history = firebase_service.list_writing_submissions(user_id, limit=5)
    writing_bands = [_safe_float(w.get("overall_band"), 0.0) for w in writing_history]
    writing_bands = [b for b in writing_bands if b > 0]
    last_writing_band = (
        round(sum(writing_bands) / len(writing_bands), 1) if writing_bands else 0.0
    )

    listening_history = firebase_service.list_listening_exercises(user_id, limit=30)
    listening_scores = [
        _safe_float(h.get("score"), 0.0)
        for h in listening_history
        if h.get("submitted")
    ]
    last_listening_score = (
        sum(listening_scores) / len(listening_scores) if listening_scores else 0.0
    )

    return {
        "due_srs_count": due_srs,
        "total_vocab": total_words,
        "daily_words_done_today": daily_words_done_today,
        "last_writing_band": last_writing_band,
        "writing_sample_size": len(writing_bands),
        "last_listening_score": round(last_listening_score, 3),
        "listening_sample_size": len(listening_scores),
        "weakest_listening_type": _weakest_listening_type(listening_history),
        "streak": int(user.get("streak", 0) or 0),
    }


def days_until_exam(user: dict) -> int | None:
    """Return days until exam_date, or None if not set."""
    raw = user.get("exam_date")
    if not raw:
        return None
    try:
        if isinstance(raw, str):
            exam = datetime.strptime(raw, "%Y-%m-%d").date()
        elif isinstance(raw, datetime):
            exam = raw.date()
        else:
            exam = raw  # date-like
    except (TypeError, ValueError):
        return None
    today = datetime.now(timezone.utc).date()
    return (exam - today).days
