"""Admin platform metrics (US-M11.5).

Read-only endpoints that back the ``/admin`` dashboard. Each delegates
to ``services.admin.metrics_service`` so the SQL/Firestore mix lives in
one place. All routes are gated by ``platform_admin``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.models.admin import (
    AdminAiUsagePoint,
    AdminCohortRow,
    AdminDauPoint,
    AdminPlanDistribution,
)
from api.permissions import require_role
from services.admin import metrics_service

router = APIRouter()


@router.get(
    "/metrics/dau",
    response_model=list[AdminDauPoint],
    dependencies=[Depends(require_role("platform_admin"))],
)
def get_dau(days: int = Query(30, ge=1, le=365)) -> list[AdminDauPoint]:
    return [AdminDauPoint(**p) for p in metrics_service.dau_series(days)]


@router.get(
    "/metrics/ai-usage",
    response_model=list[AdminAiUsagePoint],
    dependencies=[Depends(require_role("platform_admin"))],
)
def get_ai_usage(days: int = Query(30, ge=1, le=365)) -> list[AdminAiUsagePoint]:
    return [AdminAiUsagePoint(**p) for p in metrics_service.ai_usage_series(days)]


@router.get(
    "/metrics/plans",
    response_model=list[AdminPlanDistribution],
    dependencies=[Depends(require_role("platform_admin"))],
)
def get_plan_distribution() -> list[AdminPlanDistribution]:
    return [
        AdminPlanDistribution(plan_id=plan, count=count)
        for plan, count in sorted(metrics_service.plan_distribution().items())
    ]


@router.get(
    "/metrics/cohorts",
    response_model=list[AdminCohortRow],
    dependencies=[Depends(require_role("platform_admin"))],
)
def get_cohorts(weeks: int = Query(8, ge=1, le=52)) -> list[AdminCohortRow]:
    return [AdminCohortRow(**row) for row in metrics_service.signup_cohorts(weeks)]
