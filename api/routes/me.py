"""Per-user metadata routes (US-M13.1).

Currently exposes ``GET /api/v1/me/ai-usage`` — the read endpoint that
backs the consumer dashboard's "AI usage today" widget. Read-only,
does NOT increment the counter (the counter is owned by
``services.admin.quota_service.check_and_increment``).
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.models.user import AiUsageFeaturePoint, MeAiUsage
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
