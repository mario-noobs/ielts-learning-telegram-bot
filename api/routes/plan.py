import asyncio
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

import config
from api.auth import get_current_user
from api.models.plan import DailyPlan
from services import firebase_service, plan_service, weakness_service

router = APIRouter(prefix="/api/v1/plan", tags=["plan"])


def _parse_local_date(date_str: str) -> date:
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return date.today()


def _to_plan(doc: dict, user: dict) -> DailyPlan:
    """Shape the plan doc into the API response.

    `days_until_exam` and `exam_urgent` are computed fresh from the user's
    current profile on every read, so setting or clearing the exam date
    mid-day updates the countdown banner immediately — the cached plan's
    frozen copy is intentionally ignored for these two fields.
    """
    days_left = weakness_service.days_until_exam(user)
    exam_urgent = days_left is not None and 0 <= days_left <= plan_service.EXAM_URGENT_DAYS

    return DailyPlan(
        date=doc.get("date", ""),
        activities=doc.get("activities", []),
        total_minutes=int(doc.get("total_minutes", 0)),
        cap_minutes=int(doc.get("cap_minutes", 30)),
        exam_urgent=exam_urgent,
        days_until_exam=days_left,
        completed_count=int(doc.get("completed_count", 0)),
        generated_at=doc.get("generated_at"),
    )


@router.get("/today", response_model=DailyPlan)
async def get_today_plan(
    user: dict = Depends(get_current_user),
) -> DailyPlan:
    """Return today's plan, generating and caching it on the first call."""
    date_str = config.local_date_str()

    cached = await asyncio.to_thread(
        firebase_service.get_daily_plan, user["id"], date_str
    )
    if cached:
        return _to_plan(cached, user)

    weakness = await asyncio.to_thread(
        weakness_service.build_weakness_profile, user
    )
    plan = plan_service.generate_plan(
        user, weakness, today=_parse_local_date(date_str),
    )

    await asyncio.to_thread(
        firebase_service.save_daily_plan, user["id"], date_str, plan
    )
    return _to_plan(plan, user)


@router.post("/today/complete/{activity_id}", response_model=DailyPlan)
async def complete_activity(
    activity_id: str,
    user: dict = Depends(get_current_user),
) -> DailyPlan:
    """Mark an activity complete and return the updated plan.

    Uses a Firestore transaction so concurrent completions of different
    activities in the same plan can't clobber each other's writes.
    """
    date_str = config.local_date_str()

    result = await asyncio.to_thread(
        firebase_service.complete_plan_activity,
        user["id"], date_str, activity_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No plan exists for today; fetch /plan/today first.",
        )
    if result == "NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not in today's plan.",
        )
    return _to_plan(result, user)
