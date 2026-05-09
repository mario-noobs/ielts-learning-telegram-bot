"""Exam readiness track endpoint (US-#223).

Surfaces the dashboard's `<ReadinessTrack>` data — a 4-step roadmap
(goal → daily_plan → skills → mock_test) with per-step status and
i18n keys the frontend localizes.

Read-only, not gated by AI quota. Wraps `services.readiness_service`
(pure-functional) plus a progress snapshot read.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.models.readiness import (
    ReadinessResponse,
    ReadinessStep,
    ReadinessSubTask,
)
from services import progress_service, readiness_service

router = APIRouter(prefix="/api/v1", tags=["readiness"])


@router.get("/readiness", response_model=ReadinessResponse)
async def get_readiness(user: dict = Depends(get_current_user)) -> ReadinessResponse:
    # Snapshot read can swallow errors — the readiness compute degrades
    # gracefully when `progress=None` (Step 3 stays upcoming until band
    # data lands), so a Firestore hiccup doesn't 500 the dashboard.
    try:
        progress = await asyncio.to_thread(progress_service.build_snapshot, user)
    except Exception:  # noqa: BLE001 — defensive
        progress = None

    snapshot = readiness_service.compute_readiness(user, progress)
    return ReadinessResponse(
        pct_complete=snapshot["pct_complete"],
        days_until_exam=snapshot["days_until_exam"],
        urgent=snapshot["urgent"],
        target_band=snapshot["target_band"],
        steps=[
            ReadinessStep(
                id=s["id"],
                status=s["status"],
                title_key=s["title_key"],
                rationale_key=s["rationale_key"],
                rationale_params=s["rationale_params"],
                sub_tasks=[ReadinessSubTask(**t) for t in s["sub_tasks"]],
            )
            for s in snapshot["steps"]
        ],
    )
