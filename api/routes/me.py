"""Per-user metadata routes (US-M13.1, US-M13.4).

Exposes:
  - ``GET /api/v1/me/ai-usage`` — today snapshot, backs the consumer
    dashboard's "AI usage today" widget.
  - ``GET /api/v1/me/ai-usage/history?days=N`` — 30-day (max 90) per-day
    per-feature counts, backs the ``/settings/usage`` page.

Both are read-only, do NOT increment the counter (the counter is owned
by ``services.admin.quota_service.check_and_increment``).
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from api.auth import get_current_user
from api.models.user import (
    AiUsageFeaturePoint,
    AiUsageHistoryPoint,
    MeAiUsage,
    MeStudyWeek,
    StudyWeekFeaturePoint,
)
from services import progress_service
from services.admin import quota_service
from services.repositories import get_ai_usage_repo

router = APIRouter(prefix="/api/v1/me", tags=["me"])


def _next_utc_midnight() -> str:
    """ISO timestamp at the next UTC midnight (matches `ai_usage.date` rollover)."""
    today: _date = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=timezone.utc).isoformat()


@router.get("/ai-usage", response_model=MeAiUsage)
def get_my_ai_usage(user: dict = Depends(get_current_user)) -> MeAiUsage:
    by_feature_dict = get_ai_usage_repo().get_today(str(user["id"]))
    quota = quota_service.effective_daily_cap(
        user.get("plan", "free"),
        user.get("quota_override"),
    )
    return MeAiUsage(
        plan=user.get("plan", "free"),
        quota_daily=quota,
        used_today=sum(by_feature_dict.values()),
        by_feature=[
            AiUsageFeaturePoint(feature=f, count=c)
            for f, c in sorted(by_feature_dict.items())
        ],
        reset_at=_next_utc_midnight(),
    )


@router.get("/study-week", response_model=MeStudyWeek)
def get_my_study_week(user: dict = Depends(get_current_user)) -> MeStudyWeek:
    """Weekly study-minutes breakdown (US-M14.3 completion-event proxy).

    Counts rows in writing / quiz / listening / reading history since
    Monday 00:00 UTC and multiplies by ``MINUTES_PER_FEATURE``. Reset
    is implicit — once a row falls out of the [Mon, now] window it stops
    being counted, so no migration or cron is needed.

    Read-only; not gated by AI quota (no Gemini calls). Goal field
    falls back to the schema default (150 min) if the user hasn't set
    one yet.
    """
    payload = progress_service.weekly_minutes_actual(user["id"])
    return MeStudyWeek(
        minutes_actual=payload["minutes_actual"],
        minutes_goal=int(user.get("weekly_goal_minutes") or 150),
        by_feature=[StudyWeekFeaturePoint(**row) for row in payload["by_feature"]],
        week_start=payload["week_start"],
    )


@router.get("/ai-usage/history", response_model=list[AiUsageHistoryPoint])
def get_my_ai_usage_history(
    days: int = Query(default=30, ge=1, le=90),
    user: dict = Depends(get_current_user),
) -> list[AiUsageHistoryPoint]:
    """Per-user (date, feature, count) rows for the last ``days`` days.

    ``days`` is clamped to 1..90 by FastAPI's ``Query`` validator (out-of-
    range → 422). Default is 30 to match the chart on
    ``/settings/usage``. Reuses ``AiUsageRepo.get_window`` so the existing
    admin metric and this endpoint share the same window semantics.
    """
    docs = get_ai_usage_repo().get_window(str(user["id"]), days)
    return [
        AiUsageHistoryPoint(
            date=d.date.isoformat(),
            feature=d.feature,
            count=d.count,
        )
        for d in docs
    ]
