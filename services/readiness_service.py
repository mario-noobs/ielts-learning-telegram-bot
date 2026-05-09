"""Exam readiness track (US-#223).

Computes a 4-step roadmap for the dashboard `<ReadinessTrack>` card.
Each step has a status (`done | active | upcoming | locked`) derived
from the user's profile + progress + plan, plus a 1-line rationale
that ties to the user's actual data ("Vocab band 5.5 → cần 6.5
trước 12/06").

The track replaces the old `ReadinessStrip` (4 floating skill cards)
on the dashboard with a single ordered narrative — what to do next,
not just where you stand.

Pure-functional. No mutations, no AI calls, no external IO. Reads
already-loaded user/progress dicts so the route handler stays a thin
adapter.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Literal, Optional, TypedDict

logger = logging.getLogger(__name__)


# Stable IDs — frontend keys i18n + analytics off these. Don't rename.
StepId = Literal["goal", "daily_plan", "skills", "mock_test"]
Status = Literal["done", "active", "upcoming", "locked"]

# Step 4 unlocks N days before the exam — short of that and the user
# isn't ready for mocks anyway, and surfacing a "do this" CTA they
# can't act on is worse than a clearly-locked tile.
MOCK_TEST_UNLOCK_DAYS = 14
# "Final stretch" copy + auto-expand of skills phase kicks in inside
# this window. Designer brief calls it the <7-days exam variant.
EXAM_URGENT_DAYS = 7


class SubTask(TypedDict, total=False):
    id: str
    label_key: str  # i18n key under `readinessTrack.subTasks.{id}`
    href: str
    done: bool


class Step(TypedDict):
    id: StepId
    status: Status
    title_key: str  # i18n key under `readinessTrack.steps.{id}.title`
    rationale_key: str  # i18n key (keys: free-form via params)
    rationale_params: dict
    sub_tasks: list[SubTask]


class ReadinessSnapshot(TypedDict):
    pct_complete: int
    days_until_exam: Optional[int]
    urgent: bool  # <= EXAM_URGENT_DAYS away
    target_band: float
    steps: list[Step]


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _days_until(exam_iso: Optional[str]) -> Optional[int]:
    if not exam_iso:
        return None
    try:
        d = date.fromisoformat(exam_iso[:10])
    except (TypeError, ValueError):
        return None
    return (d - _today_utc()).days


def _skills_at_target(progress: dict, target: float) -> int:
    """Count of skills (writing/listening/vocab/reading) ≥ target band."""
    skills = (progress or {}).get("snapshot", {}).get("skills") or {}
    hit = 0
    for key in ("writing", "listening", "vocabulary", "reading"):
        try:
            band = float((skills.get(key) or {}).get("band") or 0)
        except (TypeError, ValueError):
            band = 0.0
        if band >= target:
            hit += 1
    return hit


def _has_daily_plan_locked(user: dict) -> bool:
    """Treat "user touched their daily reminder time + has weekly goal" as
    a proxy for "daily plan locked in". Avoids a new field — both are
    already settable from /settings Practice + Goals tabs."""
    if not (user.get("weekly_goal_minutes") or 0):
        return False
    if not user.get("daily_time"):
        return False
    return True


def _step_goal(user: dict) -> Step:
    """Step 1 — set target band + exam date."""
    has_band = bool(user.get("target_band"))
    has_exam = bool(user.get("exam_date"))
    done = has_band and has_exam
    sub_tasks: list[SubTask] = [
        {
            "id": "target_band",
            "label_key": "readinessTrack.subTasks.target_band",
            "href": "/settings#target-band",
            "done": has_band,
        },
        {
            "id": "exam_date",
            "label_key": "readinessTrack.subTasks.exam_date",
            "href": "/settings#exam-date",
            "done": has_exam,
        },
    ]
    return {
        "id": "goal",
        "status": "done" if done else "active",
        "title_key": "readinessTrack.steps.goal.title",
        "rationale_key": "readinessTrack.steps.goal.rationale",
        "rationale_params": {},
        "sub_tasks": sub_tasks,
    }


def _step_daily_plan(user: dict, prev_done: bool) -> Step:
    """Step 2 — daily reminder time + weekly goal."""
    locked_in = _has_daily_plan_locked(user)
    weekly_goal = int(user.get("weekly_goal_minutes") or 0)
    if not prev_done:
        status: Status = "upcoming"
    elif locked_in:
        status = "done"
    else:
        status = "active"
    sub_tasks: list[SubTask] = [
        {
            "id": "weekly_goal",
            "label_key": "readinessTrack.subTasks.weekly_goal",
            "href": "/settings#weekly-goal",
            "done": weekly_goal > 0,
        },
        {
            "id": "daily_time",
            "label_key": "readinessTrack.subTasks.daily_time",
            "href": "/settings#daily-time",
            "done": bool(user.get("daily_time")),
        },
    ]
    return {
        "id": "daily_plan",
        "status": status,
        "title_key": "readinessTrack.steps.daily_plan.title",
        "rationale_key": "readinessTrack.steps.daily_plan.rationale",
        "rationale_params": {"min": weekly_goal // 7 if weekly_goal else 20},
        "sub_tasks": sub_tasks,
    }


def _step_skills(user: dict, progress: dict, prev_done: bool) -> Step:
    """Step 3 — practice all 4 skills until each hits target band."""
    target = float(user.get("target_band") or 7.0)
    at_target = _skills_at_target(progress, target)
    if not prev_done:
        status: Status = "upcoming"
    elif at_target >= 4:
        status = "done"
    else:
        status = "active"
    return {
        "id": "skills",
        "status": status,
        "title_key": "readinessTrack.steps.skills.title",
        "rationale_key": "readinessTrack.steps.skills.rationale",
        "rationale_params": {"done": at_target, "total": 4, "target": target},
        # Sub-tasks here are the 4 skill cards themselves — frontend
        # nests SkillBandCard components per AC1, so we don't echo
        # link tasks here (avoids duplication of the same Link href).
        "sub_tasks": [],
    }


def _step_mock_test(user: dict, progress: dict, days_until: Optional[int]) -> Step:
    """Step 4 — locked until N days before exam, then active.

    Done = user has logged ≥1 mock test row in the past 14 days. We
    don't have a dedicated `mock_tests` collection in M14, so this
    is a placeholder rule (always upcoming when days <= unlock and
    no real signal). Treat it as a forward-looking prompt rather
    than a verified completion gate.
    """
    if days_until is None:
        return {
            "id": "mock_test",
            "status": "locked",
            "title_key": "readinessTrack.steps.mock_test.title",
            "rationale_key": "readinessTrack.steps.mock_test.locked_no_date",
            "rationale_params": {},
            "sub_tasks": [],
        }
    if days_until > MOCK_TEST_UNLOCK_DAYS:
        return {
            "id": "mock_test",
            "status": "locked",
            "title_key": "readinessTrack.steps.mock_test.title",
            "rationale_key": "readinessTrack.steps.mock_test.locked",
            "rationale_params": {"days": MOCK_TEST_UNLOCK_DAYS},
            "sub_tasks": [],
        }
    if days_until < 0:
        return {
            "id": "mock_test",
            "status": "done",
            "title_key": "readinessTrack.steps.mock_test.title",
            "rationale_key": "readinessTrack.steps.mock_test.past",
            "rationale_params": {},
            "sub_tasks": [],
        }
    return {
        "id": "mock_test",
        "status": "active",
        "title_key": "readinessTrack.steps.mock_test.title",
        "rationale_key": "readinessTrack.steps.mock_test.rationale",
        "rationale_params": {"days": days_until},
        "sub_tasks": [],
    }


def _pct_complete(steps: list[Step]) -> int:
    """4 steps, 25% per step done. Active step contributes its sub-task
    progress (e.g. 1 of 2 sub-tasks done = +12.5%) so the bar moves as
    the user ticks things off, not only at step boundaries."""
    pct = 0.0
    for s in steps:
        if s["status"] == "done":
            pct += 25.0
        elif s["status"] == "active":
            tasks = s.get("sub_tasks") or []
            if tasks:
                done = sum(1 for t in tasks if t.get("done"))
                pct += 25.0 * (done / len(tasks))
    return min(100, int(round(pct)))


def compute_readiness(user: dict, progress: Optional[dict]) -> ReadinessSnapshot:
    """Build the readiness snapshot for `<ReadinessTrack>`.

    Args:
        user: dict from `/api/v1/me` (target_band, exam_date, daily_time,
              weekly_goal_minutes).
        progress: dict from `progress_service.build_snapshot(user)` or
              equivalent — used for skill bands. Pass None to render
              an "all upcoming" track (loading state).
    """
    days_until = _days_until(user.get("exam_date"))
    target = float(user.get("target_band") or 7.0)

    s1 = _step_goal(user)
    s2 = _step_daily_plan(user, prev_done=(s1["status"] == "done"))
    s3 = _step_skills(user, progress or {}, prev_done=(s2["status"] == "done"))
    s4 = _step_mock_test(user, progress or {}, days_until)
    steps: list[Step] = [s1, s2, s3, s4]

    return {
        "pct_complete": _pct_complete(steps),
        "days_until_exam": days_until,
        "urgent": bool(days_until is not None and 0 <= days_until <= EXAM_URGENT_DAYS),
        "target_band": target,
        "steps": steps,
    }
