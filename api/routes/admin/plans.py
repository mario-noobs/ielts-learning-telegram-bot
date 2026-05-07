"""Admin plan CRUD endpoints (US-M11.3).

All routes require ``role == 'platform_admin'``. Mutations land an
``audit_log`` row through ``services.admin.audit_service.log_event``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from api.errors import ERR, ApiError
from api.models.admin import (
    AdminActionResponse,
    AdminPlanCreate,
    AdminPlanRow,
    AdminPlanUpdate,
)
from api.permissions import require_role
from services.admin import audit_service
from services.db import get_sync_session
from services.db.models import Plan, User

router = APIRouter()


def _row_to_doc(p: Plan) -> AdminPlanRow:
    return AdminPlanRow(
        id=p.id,
        name=p.name,
        daily_ai_quota=p.daily_ai_quota,
        monthly_ai_quota=p.monthly_ai_quota,
        max_team_seats=p.max_team_seats,
        features=list(p.features or []),
        created_at=p.created_at,
    )


@router.get(
    "/plans",
    response_model=list[AdminPlanRow],
    dependencies=[Depends(require_role("platform_admin"))],
)
def list_plans() -> list[AdminPlanRow]:
    with get_sync_session() as s:
        rows = s.execute(select(Plan).order_by(Plan.id)).scalars().all()
    return [_row_to_doc(r) for r in rows]


@router.post(
    "/plans",
    response_model=AdminActionResponse,
    status_code=201,
)
def create_plan(
    body: AdminPlanCreate,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    """Insert a new plan row. 409 if id already exists."""
    plan = Plan(
        id=body.id,
        name=body.name,
        daily_ai_quota=body.daily_ai_quota,
        monthly_ai_quota=body.monthly_ai_quota,
        max_team_seats=body.max_team_seats,
        features=list(body.features or []),
        created_at=datetime.now(timezone.utc),
    )
    try:
        with get_sync_session() as s, s.begin():
            s.add(plan)
    except IntegrityError:
        raise ApiError(
            ERR.admin_target_not_found,
            target_kind="plan",
            target_id=body.id,
            reason="duplicate_id",
        )

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.plan_created",
        target_kind="plan",
        target_id=body.id,
        before=None,
        after=body.model_dump(),
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


@router.patch(
    "/plans/{plan_id}",
    response_model=AdminActionResponse,
)
def update_plan(
    plan_id: str,
    body: AdminPlanUpdate,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return AdminActionResponse(ok=True)

    with get_sync_session() as s:
        before_row = s.get(Plan, plan_id)
    if before_row is None:
        raise ApiError(
            ERR.admin_target_not_found,
            target_kind="plan",
            target_id=plan_id,
        )

    before = {k: getattr(before_row, k) for k in patch}
    if "features" in before:
        before["features"] = list(before["features"] or [])

    with get_sync_session() as s, s.begin():
        s.execute(update(Plan).where(Plan.id == plan_id).values(**patch))

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.plan_updated",
        target_kind="plan",
        target_id=plan_id,
        before=before,
        after=patch,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


@router.delete(
    "/plans/{plan_id}",
    response_model=AdminActionResponse,
)
def delete_plan(
    plan_id: str,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    """Delete a plan. 409 if any user is still assigned to it."""
    with get_sync_session() as s:
        before_row = s.get(Plan, plan_id)
        if before_row is None:
            raise ApiError(
                ERR.admin_target_not_found,
                target_kind="plan",
                target_id=plan_id,
            )
        users_on_plan = s.execute(
            select(func.count()).select_from(User).where(User.plan == plan_id),
        ).scalar_one()

    if users_on_plan > 0:
        raise ApiError(
            ERR.admin_target_not_found,
            target_kind="plan",
            target_id=plan_id,
            reason="users_still_assigned",
            users_count=users_on_plan,
        )

    with get_sync_session() as s, s.begin():
        s.execute(delete(Plan).where(Plan.id == plan_id))

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.plan_deleted",
        target_kind="plan",
        target_id=plan_id,
        before={
            "id": before_row.id,
            "name": before_row.name,
            "daily_ai_quota": before_row.daily_ai_quota,
            "monthly_ai_quota": before_row.monthly_ai_quota,
            "max_team_seats": before_row.max_team_seats,
            "features": list(before_row.features or []),
        },
        after=None,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)
