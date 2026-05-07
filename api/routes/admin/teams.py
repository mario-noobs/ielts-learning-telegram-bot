"""Admin team CRUD + members (US-M11.4).

All routes require ``role == 'platform_admin'`` for now. Team-scoped
``team_admin`` access (manage own team, can't escalate cross-team) is
enforced inline by checking ``team_members`` for the actor before
mutating; ``platform_admin`` bypasses the membership check.

Mutations land an ``audit_log`` row through
``services.admin.audit_service.log_event``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select, update

from api.auth import get_current_user
from api.errors import ERR, ApiError
from api.models.admin import (
    AdminActionResponse,
    AdminTeamCreate,
    AdminTeamMemberAdd,
    AdminTeamMemberRow,
    AdminTeamSummary,
    AdminTeamUpdate,
)
from api.permissions import require_role
from services.admin import audit_service
from services.db import get_sync_session
from services.db.models import Team, TeamMember

router = APIRouter()


def _team_to_summary(t: Team, member_count: int = 0) -> AdminTeamSummary:
    return AdminTeamSummary(
        id=t.id, name=t.name, owner_uid=t.owner_uid, plan_id=t.plan_id,
        plan_expires_at=t.plan_expires_at, seat_limit=t.seat_limit,
        created_by=t.created_by, created_at=t.created_at,
        member_count=member_count,
    )


def _is_platform_admin(user: dict) -> bool:
    return user.get("role") == "platform_admin"


def _assert_can_manage_team(user: dict, team_id: str) -> None:
    """Allow platform_admin or any user who is admin of this team."""
    if _is_platform_admin(user):
        return
    user_uid = str(user["id"])
    with get_sync_session() as s:
        is_team_admin = s.execute(
            select(func.count())
            .select_from(TeamMember)
            .where(TeamMember.team_id == team_id)
            .where(TeamMember.user_uid == user_uid)
            .where(TeamMember.role == "admin"),
        ).scalar_one()
    if not is_team_admin:
        raise ApiError(ERR.admin_forbidden_role, role=user.get("role", "user"),
                       required="team_admin@team")


# ─── Teams ──────────────────────────────────────────────────────────


@router.get(
    "/teams",
    response_model=list[AdminTeamSummary],
    dependencies=[Depends(require_role("platform_admin"))],
)
def list_teams() -> list[AdminTeamSummary]:
    with get_sync_session() as s:
        rows = s.execute(select(Team).order_by(Team.created_at.desc())).scalars().all()
        # Attach a per-team member count
        counts: dict[str, int] = {}
        for tid, c in s.execute(
            select(TeamMember.team_id, func.count())
            .group_by(TeamMember.team_id),
        ).all():
            counts[tid] = c
    return [_team_to_summary(r, counts.get(r.id, 0)) for r in rows]


@router.post(
    "/teams",
    response_model=AdminActionResponse,
    status_code=201,
)
def create_team(
    body: AdminTeamCreate,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    t = Team(
        name=body.name, owner_uid=body.owner_uid, plan_id=body.plan_id,
        seat_limit=body.seat_limit, created_by=str(actor["id"]),
        created_at=datetime.now(timezone.utc),
    )
    with get_sync_session() as s, s.begin():
        s.add(t)
        s.flush()
        team_id = t.id

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.team_created",
        target_kind="team",
        target_id=team_id,
        before=None,
        after={**body.model_dump(), "id": team_id},
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id, extra={"id": team_id})


@router.get(
    "/teams/{team_id}",
    response_model=AdminTeamSummary,
)
def get_team(
    team_id: str,
    actor: dict = Depends(get_current_user),
) -> AdminTeamSummary:
    _assert_can_manage_team(actor, team_id)
    with get_sync_session() as s:
        row = s.get(Team, team_id)
        if row is None:
            raise ApiError(
                ERR.admin_target_not_found, target_kind="team", target_id=team_id,
            )
        member_count = s.execute(
            select(func.count()).select_from(TeamMember)
            .where(TeamMember.team_id == team_id),
        ).scalar_one()
    return _team_to_summary(row, member_count)


@router.patch(
    "/teams/{team_id}",
    response_model=AdminActionResponse,
)
def update_team(
    team_id: str,
    body: AdminTeamUpdate,
    actor: dict = Depends(get_current_user),
) -> AdminActionResponse:
    _assert_can_manage_team(actor, team_id)
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return AdminActionResponse(ok=True)

    with get_sync_session() as s:
        before_row = s.get(Team, team_id)
    if before_row is None:
        raise ApiError(
            ERR.admin_target_not_found, target_kind="team", target_id=team_id,
        )
    before = {k: getattr(before_row, k) for k in patch}
    if "plan_expires_at" in before and before["plan_expires_at"]:
        before["plan_expires_at"] = before["plan_expires_at"].isoformat()

    with get_sync_session() as s, s.begin():
        s.execute(update(Team).where(Team.id == team_id).values(**patch))

    after = {**patch}
    if "plan_expires_at" in after and after["plan_expires_at"]:
        after["plan_expires_at"] = after["plan_expires_at"].isoformat()

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.team_updated",
        target_kind="team",
        target_id=team_id,
        before=before, after=after,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


@router.delete(
    "/teams/{team_id}",
    response_model=AdminActionResponse,
    dependencies=[Depends(require_role("platform_admin"))],
)
def delete_team(
    team_id: str,
    actor: dict = Depends(require_role("platform_admin")),
) -> AdminActionResponse:
    """Drop a team (and ON DELETE CASCADE clears its members)."""
    with get_sync_session() as s:
        before_row = s.get(Team, team_id)
    if before_row is None:
        raise ApiError(
            ERR.admin_target_not_found, target_kind="team", target_id=team_id,
        )

    with get_sync_session() as s, s.begin():
        s.execute(delete(Team).where(Team.id == team_id))

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.team_deleted",
        target_kind="team",
        target_id=team_id,
        before={"id": before_row.id, "name": before_row.name},
        after=None,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


# ─── Members ────────────────────────────────────────────────────────


@router.get(
    "/teams/{team_id}/members",
    response_model=list[AdminTeamMemberRow],
)
def list_members(
    team_id: str,
    actor: dict = Depends(get_current_user),
) -> list[AdminTeamMemberRow]:
    _assert_can_manage_team(actor, team_id)
    with get_sync_session() as s:
        rows = s.execute(
            select(TeamMember).where(TeamMember.team_id == team_id)
            .order_by(TeamMember.joined_at),
        ).scalars().all()
    return [
        AdminTeamMemberRow(
            user_uid=m.user_uid, role=m.role, joined_at=m.joined_at,
        )
        for m in rows
    ]


@router.post(
    "/teams/{team_id}/members",
    response_model=AdminActionResponse,
    status_code=201,
)
def add_member(
    team_id: str,
    body: AdminTeamMemberAdd,
    actor: dict = Depends(get_current_user),
) -> AdminActionResponse:
    _assert_can_manage_team(actor, team_id)

    with get_sync_session() as s:
        team = s.get(Team, team_id)
        if team is None:
            raise ApiError(
                ERR.admin_target_not_found, target_kind="team", target_id=team_id,
            )
        existing_count = s.execute(
            select(func.count()).select_from(TeamMember)
            .where(TeamMember.team_id == team_id),
        ).scalar_one()
        already = s.execute(
            select(func.count()).select_from(TeamMember)
            .where(TeamMember.team_id == team_id)
            .where(TeamMember.user_uid == body.user_uid),
        ).scalar_one()

    if already:
        raise ApiError(
            ERR.team_member_already_exists,
            team_id=team_id, user_uid=body.user_uid,
        )
    if existing_count >= team.seat_limit:
        raise ApiError(
            ERR.team_seat_limit_reached,
            team_id=team_id, seat_limit=team.seat_limit,
        )

    m = TeamMember(
        team_id=team_id, user_uid=body.user_uid, role=body.role,
        joined_at=datetime.now(timezone.utc),
    )
    with get_sync_session() as s, s.begin():
        s.add(m)

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.team_member_added",
        target_kind="team",
        target_id=team_id,
        before=None,
        after={"user_uid": body.user_uid, "role": body.role},
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)


@router.delete(
    "/teams/{team_id}/members/{user_uid}",
    response_model=AdminActionResponse,
)
def remove_member(
    team_id: str,
    user_uid: str,
    actor: dict = Depends(get_current_user),
) -> AdminActionResponse:
    _assert_can_manage_team(actor, team_id)
    with get_sync_session() as s:
        existing = s.execute(
            select(TeamMember)
            .where(TeamMember.team_id == team_id)
            .where(TeamMember.user_uid == user_uid),
        ).scalar_one_or_none()
    if existing is None:
        raise ApiError(
            ERR.team_not_member, team_id=team_id, user_uid=user_uid,
        )

    with get_sync_session() as s, s.begin():
        s.execute(
            delete(TeamMember)
            .where(TeamMember.team_id == team_id)
            .where(TeamMember.user_uid == user_uid),
        )

    log_id = audit_service.log_event(
        actor_uid=str(actor["id"]),
        event_type="admin.team_member_removed",
        target_kind="team",
        target_id=team_id,
        before={"user_uid": user_uid, "role": existing.role},
        after=None,
    )
    return AdminActionResponse(ok=True, audit_log_id=log_id)
