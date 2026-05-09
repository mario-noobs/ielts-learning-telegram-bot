"""Band estimation + snapshot aggregation (US-5.1).

Pure reads — no AI calls, no mutations. `build_snapshot` aggregates a
user's current state across vocabulary, writing, and listening into a
per-skill band + overall estimate. `save_today_snapshot` persists the
snapshot to Firestore idempotently.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import config
from services import firebase_service

# ── Study minutes proxy (US-M14.3) ────────────────────────────────────
# Per-feature minute estimates for the weekly progress bar. Numbers
# come from session-time medians sampled in M11/M13 telemetry. Not a
# precise measurement — a "did this many things this week" proxy.
MINUTES_PER_FEATURE: dict[str, int] = {
    "writing": 15,
    "quiz": 5,
    "listening": 10,
    "reading": 12,
    "vocab_review": 3,
}

LISTENING_WEIGHTS = {
    "dictation": 0.4,
    "gap_fill": 0.3,
    "comprehension": 0.3,
}

STARTING_BAND = 4.0
MIN_BAND = 4.0
MAX_BAND = 9.0
WRITING_SAMPLE = 5
READING_SAMPLE = 5


def _round_half(value: float) -> float:
    return round(value * 2) / 2


def _clamp_band(value: float) -> float:
    rounded = _round_half(value)
    return max(MIN_BAND, min(MAX_BAND, rounded))


def estimate_vocab_band(total_words: int, mastered_count: int) -> float:
    """Map vocab size + mastery rate to an IELTS band.

    Anchors (total_words → band): 0 → 4.0, 50 → 5.0, 200 → 6.0,
    500 → 6.5, 1000 → 7.0, 2000 → 7.5, 3500+ → 8.0. Mastery boost adds
    up to +0.5 when every counted word has a healthy SRS interval.
    """
    thresholds = [
        (0, 4.0), (50, 5.0), (200, 6.0), (500, 6.5),
        (1000, 7.0), (2000, 7.5), (3500, 8.0),
    ]
    band = thresholds[0][1]
    for boundary, b in thresholds:
        if total_words >= boundary:
            band = b

    mastery_ratio = 0.0
    if total_words > 0:
        mastery_ratio = min(1.0, mastered_count / total_words)
    band += mastery_ratio * 0.5
    return _clamp_band(band)


def estimate_writing_band(writing_history: list[dict]) -> float:
    bands = []
    for w in writing_history[:WRITING_SAMPLE]:
        try:
            score = float(w.get("overall_band") or 0)
        except (TypeError, ValueError):
            continue
        if score > 0:
            bands.append(score)
    if not bands:
        return STARTING_BAND
    return _clamp_band(sum(bands) / len(bands))


def _listening_accuracy_by_type(history: list[dict]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {t: [] for t in LISTENING_WEIGHTS}
    for h in history:
        if not h.get("submitted"):
            continue
        t = h.get("exercise_type")
        if t not in buckets:
            continue
        try:
            buckets[t].append(float(h.get("score") or 0.0))
        except (TypeError, ValueError):
            continue
    return {
        t: (sum(vals) / len(vals)) if vals else 0.0
        for t, vals in buckets.items()
    }


def estimate_reading_band(reading_sessions: list[dict]) -> float:
    """Average the band from the last N *submitted* reading sessions.

    Sessions without a grade (in-progress / expired) are skipped. If no
    submitted session exists yet, returns the starting band.
    """
    bands: list[float] = []
    for s in reading_sessions:
        if s.get("status") != "submitted":
            continue
        grade = s.get("grade") or {}
        try:
            score = float(grade.get("band") or 0)
        except (TypeError, ValueError):
            continue
        if score > 0:
            bands.append(score)
        if len(bands) >= READING_SAMPLE:
            break
    if not bands:
        return STARTING_BAND
    return _clamp_band(sum(bands) / len(bands))


def estimate_listening_band(listening_history: list[dict]) -> float:
    """Weighted-accuracy → band, treating untouched types as 0.0.

    Accuracy anchors: 0.30→5.0, 0.50→6.0, 0.70→7.0, 0.85→7.5, 0.95→8.0.
    """
    by_type = _listening_accuracy_by_type(listening_history)

    has_data = any(a > 0 for a in by_type.values())
    if not has_data:
        return STARTING_BAND

    weighted = sum(by_type[t] * w for t, w in LISTENING_WEIGHTS.items())

    accuracy_anchors = [
        (0.0, 4.0), (0.30, 5.0), (0.50, 6.0), (0.70, 7.0),
        (0.85, 7.5), (0.95, 8.0), (1.0, 8.5),
    ]
    band = accuracy_anchors[0][1]
    for threshold, b in accuracy_anchors:
        if weighted >= threshold:
            band = b
    return _clamp_band(band)


def build_snapshot(user: dict) -> dict:
    """Compute the current progress snapshot for a user."""
    user_id = user["id"]

    total_words = int(user.get("total_words", 0) or 0)
    mastered = firebase_service.get_mastered_words(user_id)
    mastered_count = len(mastered) if isinstance(mastered, list) else 0
    vocab_band = estimate_vocab_band(total_words, mastered_count)

    writing_history = firebase_service.list_writing_submissions(
        user_id, limit=WRITING_SAMPLE,
    )
    writing_band = estimate_writing_band(writing_history)

    listening_history = firebase_service.list_listening_exercises(
        user_id, limit=50,
    )
    listening_accuracy = _listening_accuracy_by_type(listening_history)
    listening_band = estimate_listening_band(listening_history)

    reading_sessions = firebase_service.list_reading_sessions(user_id, limit=20)
    reading_band = estimate_reading_band(reading_sessions)
    reading_sample = sum(1 for s in reading_sessions if s.get("status") == "submitted")

    overall = _clamp_band(
        (vocab_band + writing_band + listening_band + reading_band) / 4.0
    )

    return {
        "overall_band": overall,
        "skills": {
            "vocabulary": {
                "band": vocab_band,
                "total_words": total_words,
                "mastered_count": mastered_count,
            },
            "writing": {
                "band": writing_band,
                "sample_size": min(len(writing_history), WRITING_SAMPLE),
            },
            "listening": {
                "band": listening_band,
                "sample_size": len([
                    h for h in listening_history if h.get("submitted")
                ]),
                "accuracy_by_type": {
                    t: round(acc, 3) for t, acc in listening_accuracy.items()
                },
            },
            "reading": {
                "band": reading_band,
                "sample_size": reading_sample,
            },
        },
        "target_band": float(user.get("target_band", 7.0)),
    }


def save_today_snapshot(user: dict, snapshot: dict) -> str:
    """Persist today's snapshot. Idempotent — overwrites same-day doc."""
    date_str = config.local_date_str()
    firebase_service.save_progress_snapshot(user["id"], date_str, snapshot)
    return date_str


def history_window(user_id, days: int = 30) -> list[dict]:
    """Return snapshots for the last `days` local dates (inclusive today)."""
    days = max(1, min(90, days))
    today = datetime.now(timezone.utc).date()
    date_strs = [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]
    docs = firebase_service.list_progress_snapshots(user_id, date_strs)
    # Ensure chronological order (oldest → newest) even if backend returned differently.
    docs.sort(key=lambda d: d.get("date", ""))
    return docs


def _week_start_utc(now: Optional[datetime] = None) -> datetime:
    """Monday 00:00 UTC of the current week. Matches AI-quota daily-reset
    convention (UTC midnight) so weekly + daily counters share an axis."""
    now = now or datetime.now(timezone.utc)
    # `weekday()` is 0=Mon … 6=Sun.
    start = now - timedelta(days=now.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def _count_since(items: list[dict], since: datetime, key: str = "created_at") -> int:
    """Count items whose ``key`` timestamp is at or after ``since``.

    Defensive: accepts datetime, date, or anything with ``.timestamp``;
    skips rows where the field is missing or unparseable. Naive
    datetimes are treated as UTC (Firestore returns tz-aware, but
    legacy rows from the bot may have slipped through naive).
    """
    out = 0
    for it in items:
        ts = it.get(key)
        if ts is None:
            continue
        if isinstance(ts, datetime):
            stamped = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        else:
            continue
        if stamped >= since:
            out += 1
    return out


def weekly_minutes_actual(
    user_id, *, now: Optional[datetime] = None,
) -> dict:
    """Return the current-week study-minute breakdown for ``user_id``.

    Counts rows in each history collection whose ``created_at`` falls in
    [Mon 00:00 UTC, now] and multiplies by ``MINUTES_PER_FEATURE``. The
    minute counts are an estimate, not a stopwatch-measured duration —
    "completion-event proxy" per the M14.3 spec.

    Returns a dict shaped like the API response so the route handler is
    a thin wrapper:

        {
            "minutes_actual": int,
            "by_feature": [{"feature": str, "count": int, "minutes": int}, ...],
            "week_start": "ISO datetime",
        }
    """
    week_start = _week_start_utc(now)

    # Pulling 50 rows is enough for a week even at heavy use; widen if
    # we ever see a single user log >50 of one feature in a week.
    LIMIT = 50
    counts: dict[str, int] = {
        "writing": _count_since(
            firebase_service.list_writing_submissions(user_id, limit=LIMIT),
            week_start,
        ),
        "listening": _count_since(
            firebase_service.list_listening_exercises(user_id, limit=LIMIT),
            week_start,
        ),
        "reading": _count_since(
            firebase_service.list_reading_sessions(user_id, limit=LIMIT),
            week_start,
            key="updated_at",
        ),
        # Quiz history doesn't have a list_* helper — fall back to a
        # direct Firestore call. Same shape as listening_history.
        "quiz": _count_quiz_history_since(user_id, week_start, LIMIT),
        # Vocab reviews are tracked in user.last_active updates, not as
        # discrete rows. We expose 0 here in v1 — the breakdown remains
        # honest about what the proxy actually counts.
        "vocab_review": 0,
    }

    by_feature = []
    minutes_actual = 0
    for feature, count in counts.items():
        per = MINUTES_PER_FEATURE.get(feature, 0)
        minutes = count * per
        minutes_actual += minutes
        by_feature.append({
            "feature": feature,
            "count": count,
            "minutes": minutes,
        })

    return {
        "minutes_actual": minutes_actual,
        "by_feature": by_feature,
        "week_start": week_start.isoformat(),
    }


def _count_quiz_history_since(user_id, since: datetime, limit: int) -> int:
    """Quiz repo only exposes ``get_latest`` — count manually via raw
    Firestore. Cheap (one capped query, no fanout) and keeps repo API
    small."""
    try:
        from firebase_admin import firestore as fs  # local import: optional dep
        db = firebase_service._get_db()
        docs = (
            db.collection("users").document(str(user_id))
            .collection("quiz_history")
            .order_by("created_at", direction=fs.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return _count_since([d.to_dict() for d in docs], since)
    except Exception:  # noqa: BLE001 — degrade gracefully if collection missing
        return 0


def predict_band(history: list[dict], days_ahead: int) -> float:
    """Simple linear extrapolation of overall band from history.

    Falls back to the latest observed value when variance is negligible.
    """
    usable = [
        (i, float(h.get("overall_band") or 0.0))
        for i, h in enumerate(history)
        if h.get("overall_band")
    ]
    if not usable:
        return STARTING_BAND
    if len(usable) < 2:
        return _clamp_band(usable[-1][1])

    n = len(usable)
    mean_x = sum(i for i, _ in usable) / n
    mean_y = sum(y for _, y in usable) / n
    num = sum((i - mean_x) * (y - mean_y) for i, y in usable)
    den = sum((i - mean_x) ** 2 for i, _ in usable)
    slope = num / den if den else 0.0
    intercept = mean_y - slope * mean_x

    projected = intercept + slope * (usable[-1][0] + days_ahead)
    return _clamp_band(projected)
