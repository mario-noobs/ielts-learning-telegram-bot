"""Admin user listing + edit endpoints (US-M11.3).

All routes require ``role == 'platform_admin'``. Mutations land an
``audit_log`` row through ``services.admin.audit_service.log_event``.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update

from api.errors import ERR, ApiError
from api.models.admin import (
    AdminActionResponse,
    AdminUsersListResponse,
    AdminUserSummary,
    AdminUserUpdate,
)
from api.permissions import require_role
from services.admin import audit_service
from services.db import get_sync_session
from services.db.models import User

router = APIRouter()

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


def _row_to_summary(u: User) -> AdminUserSummary:
    return AdminUserSummary(
        id=u.id,
        name=u.name,
        email=u.email,
        auth_uid=u.auth_uid,
        role=u.role,
        plan=u.plan,
        plan_expires_at=u.plan_expires_at,
        quota_override=u.quota_override,
        last_active_date=u.last_active_date,
        created_at=u.created_at,
    )


@router.get(
    "/users",
    response_model=AdminUsersListResponse,
    dependencies=[Depends(require_role("platform_admin"))],
)
def list_users(
    role: Optional[str] = Query(default=None),
    plan: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, description="ILIKE on name or email"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
) -> AdminUsersListResponse:
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    if plan:
        stmt = stmt.where(User.plan == plan)
        count_stmt = count_stmt.where(User.plan == plan)
    if q:
        like = f"%{q}%"
        cond = User.name.ilike(like) | User.email.ilike(like)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    stmt = stmt.order_by(User.created_at.desc()).limit(page_size).offset(
        (page - 1) * page_size,
    )

    with get_sync_session() as s:
        total = s.execute(count_stmt).scalar_one()
        rows = s.execute(stmt).scalars().all()

    return AdminUsersListResponse(
        items=[_row_to_summary(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserSummary,
    dependencies=[Depends(require_role("platform_admin"))],
)
def get_user(user_id: str) -> AdminUserSummary:
    with get_sync_session() as s:
        row = s.get(User, user_id)
    if row is None:
        raise ApiError(
            ERR.admin_target_not_found,
            target_kind="user",
            target_id=user_id,
        )
    return _row_to_summary(row)


@router.patch(
    "/users/{user_id}",
    response_model=AdminActionResponse,
)
def update_user(
    user_id: str,
    body: AdminUserUpdate,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    """Mutate a user's role / plan / expiry / quota_override."""
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return AdminActionResponse(ok=True)

    with get_sync_session() as s:
        before_row = s.get(User, user_id)
    if before_row is None:
        raise ApiError(
            ERR.admin_target_not_found,
            target_kind="user",
            target_id=user_id,
        )

    before = {k: getattr(before_row, k) for k in patch}

    with get_sync_session() as s, s.begin():
        s.execute(update(User).where(User.id == user_id).values(**patch))

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.user_updated",
        target_kind="user",
        target_id=user_id,
        before=_jsonify(before),
        after=_jsonify(patch),
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


def _jsonify(d: dict) -> dict:
    """Convert dates/datetimes to ISO strings for JSONB storage."""
    out: dict = {}
    for k, v in d.items():
        out[k] = v.isoformat() if hasattr(v, "isoformat") else v
    return out
