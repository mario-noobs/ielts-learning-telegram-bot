import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

import config
from api.auth import get_current_user
from api.models.plan import DailyPlan
from services import firebase_service, plan_service, weakness_service

router = APIRouter(prefix="/api/v1/plan", tags=["plan"])


def _to_plan(doc: dict) -> DailyPlan:
    return DailyPlan(
        date=doc.get("date", ""),
        activities=doc.get("activities", []),
        total_minutes=int(doc.get("total_minutes", 0)),
        cap_minutes=int(doc.get("cap_minutes", 30)),
        exam_urgent=bool(doc.get("exam_urgent", False)),
        days_until_exam=doc.get("days_until_exam"),
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
        return _to_plan(cached)

    weakness = await asyncio.to_thread(
        weakness_service.build_weakness_profile, user
    )
    plan = plan_service.generate_plan(user, weakness)

    await asyncio.to_thread(
        firebase_service.save_daily_plan, user["id"], date_str, plan
    )
    return _to_plan(plan)


@router.post("/today/complete/{activity_id}", response_model=DailyPlan)
async def complete_activity(
    activity_id: str,
    user: dict = Depends(get_current_user),
) -> DailyPlan:
    """Mark an activity complete and return the updated plan."""
    date_str = config.local_date_str()

    cached = await asyncio.to_thread(
        firebase_service.get_daily_plan, user["id"], date_str
    )
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No plan exists for today; fetch /plan/today first.",
        )

    updated = plan_service.mark_completed(cached, activity_id)
    if updated is cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not in today's plan.",
        )

    await asyncio.to_thread(
        firebase_service.update_daily_plan,
        user["id"], date_str,
        {
            "activities": updated["activities"],
            "completed_count": updated["completed_count"],
        },
    )
    return _to_plan(updated)
