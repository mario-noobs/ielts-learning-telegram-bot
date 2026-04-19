"""Deterministic daily study plan generator (US-4.1).

Given a user and weakness profile, build an ordered list of 3-5 activities
that rotate across skills and respect the daily time cap.
"""

from datetime import date, datetime, timezone

from services import reading_service, weakness_service

DEFAULT_CAP_MIN = 30
INTENSIFIED_CAP_MIN = 45
EXAM_URGENT_DAYS = 30

# Canonical activity shape:
# {
#   "id":          stable id within the plan (string)
#   "type":        srs_review | daily_words | listening | writing | quiz
#   "title":       Vietnamese title
#   "description": Vietnamese one-liner
#   "estimated_minutes": int
#   "route":       frontend path to navigate to
#   "meta":        extra params (optional)
#   "completed":   false by default
# }

LISTENING_TITLES = {
    "dictation": "Dictation",
    "gap_fill": "Gap Fill",
    "comprehension": "Listening Comprehension",
}


def _activity(
    *,
    aid: str,
    atype: str,
    title: str,
    description: str,
    minutes: int,
    route: str,
    meta: dict | None = None,
) -> dict:
    return {
        "id": aid,
        "type": atype,
        "title": title,
        "description": description,
        "estimated_minutes": int(minutes),
        "route": route,
        "meta": meta or {},
        "completed": False,
    }


def _pick_writing_task(today: date) -> str:
    """Alternate Task 1 and Task 2 so consecutive writing days exercise
    different essay types.

    Uses ``(toordinal // 2) % 2`` rather than plain parity because the
    reading-vs-writing alternation (US-M9.5) means writing only appears
    on odd-ordinal days — plain parity would always pick the same task.
    """
    return "task1" if (today.toordinal() // 2) % 2 == 0 else "task2"


def _pick_reading_passage(target_band: float) -> dict | None:
    """Return the best band-matched passage summary, or None if no corpus.

    Preference order (widening window):
        1. exact target_band match
        2. target ±0.5
        3. target ±1.0
    Within a window, pick the first id ordered by the corpus sort (stable).
    """
    summaries = reading_service.list_summaries()
    if not summaries:
        return None

    def _at(delta: float) -> list[dict]:
        return [p for p in summaries if abs(p["band"] - target_band) <= delta + 1e-6]

    for window in (0.0, 0.5, 1.0):
        matches = _at(window)
        if matches:
            return matches[0]
    return summaries[0]


def generate_plan(
    user: dict,
    weakness: dict,
    *,
    today: date | None = None,
) -> dict:
    """Build a plan dict with `activities` and a few header fields.

    The caller is responsible for persistence and completion tracking.
    """
    today = today or datetime.now(timezone.utc).date()
    days_left = weakness_service.days_until_exam(user)
    exam_close = days_left is not None and 0 <= days_left <= EXAM_URGENT_DAYS
    cap = INTENSIFIED_CAP_MIN if exam_close else DEFAULT_CAP_MIN

    activities: list[dict] = []

    # AC1: SRS always included when due words > 0
    due = int(weakness.get("due_srs_count", 0) or 0)
    if due > 0:
        activities.append(_activity(
            aid="srs_review",
            atype="srs_review",
            title="Ôn từ đến hạn",
            description=f"Có {due} từ cần ôn hôm nay",
            minutes=min(15, max(4, 2 + due // 3)),
            route="/review",
        ))

    # Daily words (if not already generated today)
    if not weakness.get("daily_words_done_today"):
        activities.append(_activity(
            aid="daily_words",
            atype="daily_words",
            title="10 từ mới hôm nay",
            description="Học từ vựng theo band mục tiêu",
            minutes=6,
            route="/vocab",
        ))

    # Listening — weakest type surfaces first
    listen_type = weakness.get("weakest_listening_type", "dictation")
    activities.append(_activity(
        aid=f"listening_{listen_type}",
        atype="listening",
        title=LISTENING_TITLES.get(listen_type, "Listening"),
        description="Luyện nghe ở band mục tiêu",
        minutes=8,
        route="/listening",
        meta={"exercise_type": listen_type},
    ))

    # Big-block skill (reading OR writing), alternating by day parity so
    # learners hit both in a week without blowing the time cap (US-M9.5).
    # Reading is offered only when a seeded corpus is present; fall back
    # to writing on both parities if reading is unavailable.
    do_reading = today.toordinal() % 2 == 0
    target_band = float(user.get("target_band", 7.0))
    passage = _pick_reading_passage(target_band) if do_reading else None

    if passage is not None:
        activities.append(_activity(
            aid=f"reading_{passage['id']}",
            atype="reading",
            title="Luyện Reading 20m",
            description=f"Band {passage['band']:.1f} · {passage['title']}",
            minutes=20,
            route=f"/reading/{passage['id']}",
            meta={"passage_id": passage["id"], "band": passage["band"]},
        ))
    else:
        task_type = _pick_writing_task(today)
        activities.append(_activity(
            aid=f"writing_{task_type}",
            atype="writing",
            title=f"Viết IELTS {task_type.upper()}",
            description="Chấm tự động với AI",
            minutes=20 if task_type == "task2" else 15,
            route="/write",
            meta={"task_type": task_type},
        ))

    # Trim from the end to respect the cap while keeping at least 3 items.
    while (
        sum(a["estimated_minutes"] for a in activities) > cap
        and len(activities) > 3
    ):
        activities.pop()

    # When exam is urgent, backfill to 5 items with a quick win.
    if exam_close and len(activities) < 5:
        activities.append(_activity(
            aid="sprint_quiz",
            atype="quiz",
            title="Flashcard nhanh",
            description="5 câu ngẫu nhiên để duy trì streak",
            minutes=5,
            route="/review",
        ))

    # Final clamp: 3–5 items.
    activities = activities[:5]

    return {
        "date": today.isoformat(),
        "activities": activities,
        "total_minutes": sum(a["estimated_minutes"] for a in activities),
        "cap_minutes": cap,
        "exam_urgent": bool(exam_close),
        "days_until_exam": days_left,
        "completed_count": 0,
    }


def mark_completed(plan: dict, activity_id: str) -> dict:
    """Return a new plan dict with the matching activity marked completed.

    If no activity matches, the plan is returned unchanged.
    """
    found = False
    new_activities: list[dict] = []
    for a in plan.get("activities", []):
        if a.get("id") == activity_id and not a.get("completed"):
            new_activities.append({**a, "completed": True})
            found = True
        else:
            new_activities.append(a)
    if not found:
        return plan
    completed_count = sum(1 for a in new_activities if a.get("completed"))
    return {**plan, "activities": new_activities, "completed_count": completed_count}
