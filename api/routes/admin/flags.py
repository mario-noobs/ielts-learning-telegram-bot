"""Admin feature-flag endpoints (US-M11.3).

Thin wrapper around ``services.feature_flag_service`` — no Firestore
logic duplicated. Mutations land an ``audit_log`` row through
``services.admin.audit_service.log_event``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.errors import ERR, ApiError
from api.models.admin import (
    AdminActionResponse,
    AdminFlagRow,
    AdminFlagUpsert,
)
from api.permissions import require_role
from services import feature_flag_service as ffs
from services.admin import audit_service

router = APIRouter()


def _flag_to_row(f: ffs.FeatureFlag) -> AdminFlagRow:
    return AdminFlagRow(
        name=f.name,
        enabled=f.enabled,
        rollout_pct=f.rollout_pct,
        uid_allowlist=list(f.uid_allowlist),
        description=f.description or "",
        updated_at=f.updated_at,
    )


@router.get(
    "/flags",
    response_model=list[AdminFlagRow],
    dependencies=[Depends(require_role("platform_admin"))],
)
def list_flags() -> list[AdminFlagRow]:
    return [_flag_to_row(f) for f in ffs.list_flags()]


@router.put(
    "/flags/{flag_name}",
    response_model=AdminActionResponse,
)
def upsert_flag(
    flag_name: str,
    body: AdminFlagUpsert,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    """Create or update a flag. Invalidates the 60s cache."""
    before_flag = ffs.get_flag(flag_name)
    before = (
        {
            "enabled": before_flag.enabled,
            "rollout_pct": before_flag.rollout_pct,
            "uid_allowlist": list(before_flag.uid_allowlist),
            "description": before_flag.description,
        }
        if before_flag is not None
        else None
    )

    ffs.set_flag(
        flag_name,
        enabled=body.enabled,
        rollout_pct=body.rollout_pct,
        uid_allowlist=body.uid_allowlist,
        description=body.description,
    )

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.flag_upserted",
        target_kind="flag",
        target_id=flag_name,
        before=before,
        after=body.model_dump(),
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


@router.delete(
    "/flags/{flag_name}",
    response_model=AdminActionResponse,
)
def delete_flag(
    flag_name: str,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    before_flag = ffs.get_flag(flag_name)
    if before_flag is None:
        raise ApiError(
            ERR.admin_target_not_found,
            target_kind="flag",
            target_id=flag_name,
        )

    ffs.delete_flag(flag_name)

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.flag_deleted",
        target_kind="flag",
        target_id=flag_name,
        before={
            "enabled": before_flag.enabled,
            "rollout_pct": before_flag.rollout_pct,
            "uid_allowlist": list(before_flag.uid_allowlist),
            "description": before_flag.description,
        },
        after=None,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)
