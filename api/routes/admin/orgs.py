"""Admin org CRUD + admins + team-links (US-M11.4).

All routes require ``role == 'platform_admin'``. Mutations land an
``audit_log`` row through ``services.admin.audit_service.log_event``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select, update

from api.errors import ERR, ApiError
from api.models.admin import (
    AdminActionResponse,
    AdminOrgAdminAdd,
    AdminOrgCreate,
    AdminOrgSummary,
    AdminOrgTeamLink,
    AdminOrgUpdate,
)
from api.permissions import require_role
from services.admin import audit_service
from services.db import get_sync_session
from services.db.models import Org, OrgAdmin, OrgTeam

router = APIRouter()


def _org_to_summary(o: Org, admin_count: int = 0, team_count: int = 0) -> AdminOrgSummary:
    return AdminOrgSummary(
        id=o.id, name=o.name, owner_uid=o.owner_uid, plan_id=o.plan_id,
        plan_expires_at=o.plan_expires_at, created_at=o.created_at,
        admin_count=admin_count, team_count=team_count,
    )


@router.get(
    "/orgs",
    response_model=list[AdminOrgSummary],
    dependencies=[Depends(require_role("platform_admin"))],
)
def list_orgs() -> list[AdminOrgSummary]:
    with get_sync_session() as s:
        rows = s.execute(select(Org).order_by(Org.created_at.desc())).scalars().all()
        admin_counts = dict(s.execute(
            select(OrgAdmin.org_id, func.count()).group_by(OrgAdmin.org_id),
        ).all())
        team_counts = dict(s.execute(
            select(OrgTeam.org_id, func.count()).group_by(OrgTeam.org_id),
        ).all())
    return [
        _org_to_summary(o, admin_counts.get(o.id, 0), team_counts.get(o.id, 0))
        for o in rows
    ]


@router.post(
    "/orgs",
    response_model=AdminActionResponse,
    status_code=201,
    dependencies=[Depends(require_role("platform_admin"))],
)
def create_org(
    body: AdminOrgCreate,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    o = Org(
        name=body.name, owner_uid=body.owner_uid, plan_id=body.plan_id,
        created_at=datetime.now(timezone.utc),
    )
    with get_sync_session() as s, s.begin():
        s.add(o)
        s.flush()
        org_id = o.id

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.org_created",
        target_kind="org",
        target_id=org_id,
        before=None, after={**body.model_dump(), "id": org_id},
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id, extra={"id": org_id})


@router.get(
    "/orgs/{org_id}",
    response_model=AdminOrgSummary,
    dependencies=[Depends(require_role("platform_admin"))],
)
def get_org(org_id: str) -> AdminOrgSummary:
    with get_sync_session() as s:
        row = s.get(Org, org_id)
        if row is None:
            raise ApiError(
                ERR.admin_target_not_found, target_kind="org", target_id=org_id,
            )
        admin_count = s.execute(
            select(func.count()).select_from(OrgAdmin).where(OrgAdmin.org_id == org_id),
        ).scalar_one()
        team_count = s.execute(
            select(func.count()).select_from(OrgTeam).where(OrgTeam.org_id == org_id),
        ).scalar_one()
    return _org_to_summary(row, admin_count, team_count)


@router.patch(
    "/orgs/{org_id}",
    response_model=AdminActionResponse,
    dependencies=[Depends(require_role("platform_admin"))],
)
def update_org(
    org_id: str,
    body: AdminOrgUpdate,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return AdminActionResponse(ok=True)
    with get_sync_session() as s:
        before_row = s.get(Org, org_id)
    if before_row is None:
        raise ApiError(
            ERR.admin_target_not_found, target_kind="org", target_id=org_id,
        )
    before = {k: getattr(before_row, k) for k in patch}
    if "plan_expires_at" in before and before["plan_expires_at"]:
        before["plan_expires_at"] = before["plan_expires_at"].isoformat()
    after = {**patch}
    if "plan_expires_at" in after and after["plan_expires_at"]:
        after["plan_expires_at"] = after["plan_expires_at"].isoformat()

    with get_sync_session() as s, s.begin():
        s.execute(update(Org).where(Org.id == org_id).values(**patch))

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.org_updated",
        target_kind="org",
        target_id=org_id,
        before=before, after=after,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


@router.delete(
    "/orgs/{org_id}",
    response_model=AdminActionResponse,
    dependencies=[Depends(require_role("platform_admin"))],
)
def delete_org(
    org_id: str,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    with get_sync_session() as s:
        before_row = s.get(Org, org_id)
    if before_row is None:
        raise ApiError(
            ERR.admin_target_not_found, target_kind="org", target_id=org_id,
        )
    with get_sync_session() as s, s.begin():
        s.execute(delete(Org).where(Org.id == org_id))
    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.org_deleted",
        target_kind="org",
        target_id=org_id,
        before={"id": before_row.id, "name": before_row.name},
        after=None,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


# ─── Org admins ─────────────────────────────────────────────────────


@router.get(
    "/orgs/{org_id}/admins",
    response_model=list[str],
    dependencies=[Depends(require_role("platform_admin"))],
)
def list_admins(org_id: str) -> list[str]:
    with get_sync_session() as s:
        rows = s.execute(
            select(OrgAdmin.user_uid).where(OrgAdmin.org_id == org_id),
        ).scalars().all()
    return list(rows)


@router.post(
    "/orgs/{org_id}/admins",
    response_model=AdminActionResponse,
    status_code=201,
    dependencies=[Depends(require_role("platform_admin"))],
)
def add_admin(
    org_id: str,
    body: AdminOrgAdminAdd,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    with get_sync_session() as s, s.begin():
        s.add(OrgAdmin(org_id=org_id, user_uid=body.user_uid))

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.org_admin_added",
        target_kind="org",
        target_id=org_id,
        before=None,
        after={"user_uid": body.user_uid},
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


@router.delete(
    "/orgs/{org_id}/admins/{user_uid}",
    response_model=AdminActionResponse,
    dependencies=[Depends(require_role("platform_admin"))],
)
def remove_admin(
    org_id: str,
    user_uid: str,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    with get_sync_session() as s, s.begin():
        s.execute(
            delete(OrgAdmin)
            .where(OrgAdmin.org_id == org_id)
            .where(OrgAdmin.user_uid == user_uid),
        )
    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.org_admin_removed",
        target_kind="org",
        target_id=org_id,
        before={"user_uid": user_uid}, after=None,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


# ─── Org → team links ───────────────────────────────────────────────


@router.get(
    "/orgs/{org_id}/teams",
    response_model=list[str],
    dependencies=[Depends(require_role("platform_admin"))],
)
def list_org_teams(org_id: str) -> list[str]:
    with get_sync_session() as s:
        rows = s.execute(
            select(OrgTeam.team_id).where(OrgTeam.org_id == org_id),
        ).scalars().all()
    return list(rows)


@router.post(
    "/orgs/{org_id}/teams",
    response_model=AdminActionResponse,
    status_code=201,
    dependencies=[Depends(require_role("platform_admin"))],
)
def link_team(
    org_id: str,
    body: AdminOrgTeamLink,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    with get_sync_session() as s, s.begin():
        s.add(OrgTeam(org_id=org_id, team_id=body.team_id))
    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.org_team_linked",
        target_kind="org",
        target_id=org_id,
        before=None,
        after={"team_id": body.team_id},
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


@router.delete(
    "/orgs/{org_id}/teams/{team_id}",
    response_model=AdminActionResponse,
    dependencies=[Depends(require_role("platform_admin"))],
)
def unlink_team(
    org_id: str,
    team_id: str,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    with get_sync_session() as s, s.begin():
        s.execute(
            delete(OrgTeam)
            .where(OrgTeam.org_id == org_id)
            .where(OrgTeam.team_id == team_id),
        )
    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.org_team_unlinked",
        target_kind="org",
        target_id=org_id,
        before={"team_id": team_id},
        after=None,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)
