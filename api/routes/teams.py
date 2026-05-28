from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update

from api.auth import get_current_user
from api.errors import ERR, ApiError
from api.models.team import (
    TeamCreateRequest,
    TeamCreateResponse,
    TeamInviteAcceptResponse,
    TeamInviteCreateRequest,
    TeamInviteCreateResponse,
    TeamInvitePreviewResponse,
    TeamMeResponse,
    TeamSummary,
)
from services.admin import audit_service
from services.db import get_sync_session
from services.db.models import Team, TeamInvite, TeamMember, User

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])

BETA_TEAM_SEAT_LIMIT = 5
INVITE_TTL_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _member_count(session, team_id: str) -> int:
    return int(
        session.execute(
            select(func.count()).select_from(TeamMember)
            .where(TeamMember.team_id == team_id),
        ).scalar_one()
    )


def _membership(session, user_id: str) -> TeamMember | None:
    return session.execute(
        select(TeamMember).where(TeamMember.user_uid == user_id),
    ).scalar_one_or_none()


def _team_summary(
    session,
    team: Team,
    user_id: str,
    membership: TeamMember | None = None,
) -> TeamSummary:
    role = None
    if team.owner_uid == user_id:
        role = "owner"
    elif membership is not None:
        role = membership.role
    return TeamSummary(
        id=team.id,
        name=team.name,
        owner_uid=team.owner_uid,
        plan_id=team.plan_id,
        seat_limit=team.seat_limit,
        member_count=_member_count(session, team.id),
        my_role=role,
        created_at=team.created_at,
    )


def _assert_team_admin(session, team_id: str, user_id: str) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise ApiError(ERR.admin_target_not_found, target_kind="team", target_id=team_id)
    if team.owner_uid == user_id:
        return team
    membership = session.get(TeamMember, {"team_id": team_id, "user_uid": user_id})
    if membership is None or membership.role != "admin":
        raise ApiError(ERR.forbidden)
    return team


def _load_active_invite(token: str) -> tuple[TeamInvite, Team]:
    token_hash = _hash_token(token)
    with get_sync_session() as session:
        row = session.execute(
            select(TeamInvite, Team)
            .join(Team, Team.id == TeamInvite.team_id)
            .where(TeamInvite.token_hash == token_hash),
        ).first()
        if row is None:
            raise ApiError(ERR.team_invite_not_found)
        invite, team = row
        if invite.revoked_at is not None:
            raise ApiError(ERR.team_invite_not_found)
        if invite.expires_at < _now():
            raise ApiError(ERR.team_invite_expired)
        return invite, team


@router.get("/me", response_model=TeamMeResponse)
def get_my_team(user: dict = Depends(get_current_user)) -> TeamMeResponse:
    user_id = str(user["id"])
    with get_sync_session() as session:
        membership = _membership(session, user_id)
        team_id = user.get("team_id") or (membership.team_id if membership else None)
        if not team_id:
            return TeamMeResponse(team=None)
        team = session.get(Team, team_id)
        if team is None:
            return TeamMeResponse(team=None)
        return TeamMeResponse(team=_team_summary(session, team, user_id, membership))


@router.post("", response_model=TeamCreateResponse, status_code=201)
def create_team(
    body: TeamCreateRequest,
    user: dict = Depends(get_current_user),
) -> TeamCreateResponse:
    user_id = str(user["id"])
    name = body.name.strip()
    if not name:
        raise ApiError(ERR.validation)

    with get_sync_session() as session:
        existing_membership = _membership(session, user_id)
        existing_owned = session.execute(
            select(func.count()).select_from(Team).where(Team.owner_uid == user_id),
        ).scalar_one()
        if user.get("team_id") or existing_membership or existing_owned:
            raise ApiError(ERR.team_already_joined)

    created_at = _now()
    with get_sync_session() as session, session.begin():
        team = Team(
            name=name,
            owner_uid=user_id,
            plan_id="free",
            seat_limit=BETA_TEAM_SEAT_LIMIT,
            created_by=user_id,
            created_at=created_at,
        )
        session.add(team)
        session.flush()
        session.add(
            TeamMember(
                team_id=team.id,
                user_uid=user_id,
                role="admin",
                joined_at=created_at,
            )
        )
        session.execute(
            update(User).where(User.id == user_id).values(team_id=team.id),
        )
        summary = _team_summary(session, team, user_id)

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.created",
        target_kind="team",
        target_id=summary.id,
        before=None,
        after={"name": summary.name, "seat_limit": summary.seat_limit},
    )
    return TeamCreateResponse(team=summary)


@router.post(
    "/{team_id}/invites",
    response_model=TeamInviteCreateResponse,
    status_code=201,
)
def create_team_invite(
    team_id: str,
    body: TeamInviteCreateRequest,
    user: dict = Depends(get_current_user),
) -> TeamInviteCreateResponse:
    user_id = str(user["id"])
    token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(days=INVITE_TTL_DAYS)

    with get_sync_session() as session, session.begin():
        team = _assert_team_admin(session, team_id, user_id)
        invite = TeamInvite(
            team_id=team.id,
            token_hash=_hash_token(token),
            role=body.role,
            created_by=user_id,
            created_at=_now(),
            expires_at=expires_at,
            metadata_json={},
        )
        session.add(invite)

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.invite_created",
        target_kind="team",
        target_id=team_id,
        before=None,
        after={"role": body.role, "expires_at": expires_at.isoformat()},
    )
    return TeamInviteCreateResponse(
        token=token,
        invite_url=f"/team/invite/{token}",
        expires_at=expires_at,
    )


@router.get("/invites/{token}", response_model=TeamInvitePreviewResponse)
def preview_team_invite(token: str) -> TeamInvitePreviewResponse:
    _invite, team = _load_active_invite(token)
    with get_sync_session() as session:
        return TeamInvitePreviewResponse(
            team_id=team.id,
            team_name=team.name,
            expires_at=_invite.expires_at,
            member_count=_member_count(session, team.id),
            seat_limit=team.seat_limit,
            already_member=False,
        )


@router.post("/invites/{token}/accept", response_model=TeamInviteAcceptResponse)
def accept_team_invite(
    token: str,
    user: dict = Depends(get_current_user),
) -> TeamInviteAcceptResponse:
    user_id = str(user["id"])
    token_hash = _hash_token(token)
    joined_at = _now()

    with get_sync_session() as session, session.begin():
        row = session.execute(
            select(TeamInvite, Team)
            .join(Team, Team.id == TeamInvite.team_id)
            .where(TeamInvite.token_hash == token_hash),
        ).first()
        if row is None:
            raise ApiError(ERR.team_invite_not_found)
        invite, team = row
        if invite.revoked_at is not None:
            raise ApiError(ERR.team_invite_not_found)
        if invite.expires_at < joined_at:
            raise ApiError(ERR.team_invite_expired)

        membership = _membership(session, user_id)
        if membership is not None and membership.team_id != team.id:
            raise ApiError(ERR.team_already_joined)
        if user.get("team_id") and user.get("team_id") != team.id:
            raise ApiError(ERR.team_already_joined)
        if membership is None:
            current_count = _member_count(session, team.id)
            if current_count >= team.seat_limit:
                raise ApiError(
                    ERR.team_seat_limit_reached,
                    team_id=team.id,
                    seat_limit=team.seat_limit,
                )
            membership = TeamMember(
                team_id=team.id,
                user_uid=user_id,
                role=invite.role,
                joined_at=joined_at,
            )
            session.add(membership)
            session.execute(
                update(User).where(User.id == user_id).values(team_id=team.id),
            )
        summary = _team_summary(session, team, user_id, membership)

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.invite_accepted",
        target_kind="team",
        target_id=summary.id,
        before=None,
        after={"user_uid": user_id, "role": membership.role},
    )
    return TeamInviteAcceptResponse(team=summary)
