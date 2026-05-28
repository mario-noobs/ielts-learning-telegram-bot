from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Response
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
    TeamMemberProgressResponse,
    TeamMemberProgressRow,
    TeamMembersResponse,
    TeamMemberSummary,
    TeamMemberUpdateRequest,
    TeamMemberUpdateResponse,
    TeamMeResponse,
    TeamOverviewResponse,
    TeamSummary,
)
from services import progress_service
from services.admin import audit_service
from services.db import get_sync_session
from services.db.models import (
    ListeningHistory,
    QuizHistory,
    ReadingSession,
    ReviewEvent,
    Team,
    TeamInvite,
    TeamMember,
    User,
    UserVocabulary,
    WritingHistory,
)

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


def _assert_team_member(
    session, team_id: str, user_id: str,
) -> tuple[Team, TeamMember | None]:
    team = session.get(Team, team_id)
    if team is None:
        raise ApiError(ERR.admin_target_not_found, target_kind="team", target_id=team_id)
    membership = session.get(TeamMember, {"team_id": team_id, "user_uid": user_id})
    if membership is None and team.owner_uid != user_id:
        raise ApiError(ERR.forbidden)
    return team, membership


def _member_summary(
    team: Team,
    membership: TeamMember,
    profile: User | None,
    current_user_id: str,
) -> TeamMemberSummary:
    role = "owner" if membership.user_uid == team.owner_uid else membership.role
    return TeamMemberSummary(
        user_id=membership.user_uid,
        name=(profile.name if profile else "") or membership.user_uid,
        email=profile.email if profile else None,
        role=role,
        joined_at=membership.joined_at,
        is_current_user=membership.user_uid == current_user_id,
    )


def _team_members(session, team: Team, current_user_id: str) -> list[TeamMemberSummary]:
    rows = session.execute(
        select(TeamMember, User)
        .outerjoin(User, User.id == TeamMember.user_uid)
        .where(TeamMember.team_id == team.id)
        .order_by(TeamMember.joined_at.asc()),
    ).all()
    members = [
        _member_summary(team, membership, profile, current_user_id)
        for membership, profile in rows
    ]
    if not any(member.user_id == team.owner_uid for member in members):
        owner = session.get(User, team.owner_uid)
        members.append(
            TeamMemberSummary(
                user_id=team.owner_uid,
                name=(owner.name if owner else "") or team.owner_uid,
                email=owner.email if owner else None,
                role="owner",
                joined_at=team.created_at,
                is_current_user=team.owner_uid == current_user_id,
            )
        )
    return sorted(members, key=lambda m: (m.role != "owner", m.name.lower()))


def _count_rows(session, model, user_ids: list[str], time_field, week_start: datetime) -> int:
    if not user_ids:
        return 0
    return int(
        session.execute(
            select(func.count()).select_from(model).where(
                model.user_id.in_(user_ids),
                time_field >= week_start,
            ),
        ).scalar_one()
    )


def _active_users(session, model, user_ids: list[str], time_field, week_start: datetime) -> set[str]:
    if not user_ids:
        return set()
    return set(
        session.execute(
            select(model.user_id).where(
                model.user_id.in_(user_ids),
                time_field >= week_start,
            ),
        ).scalars()
    )


def _counts_by_user(
    session,
    model,
    user_ids: list[str],
    time_field,
    week_start: datetime,
) -> dict[str, int]:
    if not user_ids:
        return {}
    rows = session.execute(
        select(model.user_id, func.count())
        .where(model.user_id.in_(user_ids), time_field >= week_start)
        .group_by(model.user_id),
    ).all()
    return {str(user_id): int(count) for user_id, count in rows}


def _team_user_ids(session, team: Team) -> list[str]:
    user_ids = list(
        session.execute(
            select(TeamMember.user_uid).where(TeamMember.team_id == team.id),
        ).scalars()
    )
    if team.owner_uid not in user_ids:
        user_ids.append(team.owner_uid)
    return user_ids


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


@router.get("/{team_id}/members", response_model=TeamMembersResponse)
def list_team_members(
    team_id: str,
    user: dict = Depends(get_current_user),
) -> TeamMembersResponse:
    user_id = str(user["id"])
    with get_sync_session() as session:
        team, membership = _assert_team_member(session, team_id, user_id)
        return TeamMembersResponse(
            team=_team_summary(session, team, user_id, membership),
            members=_team_members(session, team, user_id),
        )


@router.patch(
    "/{team_id}/members/{member_uid}",
    response_model=TeamMemberUpdateResponse,
)
def update_team_member(
    team_id: str,
    member_uid: str,
    body: TeamMemberUpdateRequest,
    user: dict = Depends(get_current_user),
) -> TeamMemberUpdateResponse:
    user_id = str(user["id"])
    with get_sync_session() as session, session.begin():
        team = session.get(Team, team_id)
        if team is None:
            raise ApiError(ERR.admin_target_not_found, target_kind="team", target_id=team_id)
        if team.owner_uid != user_id:
            raise ApiError(ERR.forbidden)
        if member_uid == team.owner_uid:
            raise ApiError(ERR.forbidden)

        membership = session.get(TeamMember, {"team_id": team_id, "user_uid": member_uid})
        if membership is None:
            raise ApiError(ERR.team_not_member, team_id=team_id, user_uid=member_uid)
        before_role = membership.role
        membership.role = body.role
        profile = session.get(User, member_uid)
        member = _member_summary(team, membership, profile, user_id)

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.member_role_updated",
        target_kind="team",
        target_id=team_id,
        before={"user_uid": member_uid, "role": before_role},
        after={"user_uid": member_uid, "role": body.role},
    )
    return TeamMemberUpdateResponse(member=member)


@router.delete("/{team_id}/members/{member_uid}", status_code=204)
def remove_team_member(
    team_id: str,
    member_uid: str,
    user: dict = Depends(get_current_user),
) -> Response:
    user_id = str(user["id"])
    with get_sync_session() as session, session.begin():
        team = _assert_team_admin(session, team_id, user_id)
        if member_uid == team.owner_uid:
            raise ApiError(ERR.forbidden)

        actor = session.get(TeamMember, {"team_id": team_id, "user_uid": user_id})
        target = session.get(TeamMember, {"team_id": team_id, "user_uid": member_uid})
        if target is None:
            raise ApiError(ERR.team_not_member, team_id=team_id, user_uid=member_uid)
        if team.owner_uid != user_id and target.role == "admin":
            raise ApiError(ERR.forbidden)

        removed_role = target.role
        session.delete(target)
        session.execute(update(User).where(User.id == member_uid).values(team_id=None))

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.member_removed",
        target_kind="team",
        target_id=team_id,
        before={"user_uid": member_uid, "role": removed_role},
        after={"removed_by_role": "owner" if team.owner_uid == user_id else actor.role},
    )
    return Response(status_code=204)


@router.get("/{team_id}/overview", response_model=TeamOverviewResponse)
def get_team_overview(
    team_id: str,
    user: dict = Depends(get_current_user),
) -> TeamOverviewResponse:
    user_id = str(user["id"])
    week_start = progress_service._week_start_utc()
    with get_sync_session() as session:
        team, _membership = _assert_team_member(session, team_id, user_id)
        user_ids = _team_user_ids(session, team)

        writing_count = _count_rows(
            session, WritingHistory, user_ids, WritingHistory.created_at, week_start,
        )
        listening_count = _count_rows(
            session, ListeningHistory, user_ids, ListeningHistory.created_at, week_start,
        )
        quiz_count = _count_rows(
            session, QuizHistory, user_ids, QuizHistory.created_at, week_start,
        )
        reading_count = int(
            session.execute(
                select(func.count()).select_from(ReadingSession).where(
                    ReadingSession.user_id.in_(user_ids),
                    ReadingSession.status == "submitted",
                    ReadingSession.submitted_at >= week_start,
                ),
            ).scalar_one()
        ) if user_ids else 0
        words_reviewed = _count_rows(
            session, ReviewEvent, user_ids, ReviewEvent.created_at, week_start,
        )
        words_mastered = int(
            session.execute(
                select(func.count(func.distinct(ReviewEvent.user_vocab_id)))
                .where(
                    ReviewEvent.user_id.in_(user_ids),
                    ReviewEvent.created_at >= week_start,
                    ReviewEvent.srs_interval_after > 30,
                ),
            ).scalar_one()
        ) if user_ids else 0

        active = set()
        active |= _active_users(
            session, WritingHistory, user_ids, WritingHistory.created_at, week_start,
        )
        active |= _active_users(
            session, ListeningHistory, user_ids, ListeningHistory.created_at, week_start,
        )
        active |= _active_users(
            session, QuizHistory, user_ids, QuizHistory.created_at, week_start,
        )
        active |= _active_users(
            session, ReviewEvent, user_ids, ReviewEvent.created_at, week_start,
        )
        if user_ids:
            active |= set(
                session.execute(
                    select(ReadingSession.user_id).where(
                        ReadingSession.user_id.in_(user_ids),
                        ReadingSession.status == "submitted",
                        ReadingSession.submitted_at >= week_start,
                    ),
                ).scalars()
            )

        study_minutes = (
            writing_count * progress_service.MINUTES_PER_FEATURE["writing"]
            + listening_count * progress_service.MINUTES_PER_FEATURE["listening"]
            + quiz_count * progress_service.MINUTES_PER_FEATURE["quiz"]
            + reading_count * progress_service.MINUTES_PER_FEATURE["reading"]
            + words_reviewed * progress_service.MINUTES_PER_FEATURE["vocab_review"]
        )
        return TeamOverviewResponse(
            week_start=week_start,
            weekly_active_members=len(active),
            study_minutes=study_minutes,
            words_reviewed=words_reviewed,
            words_mastered=words_mastered,
            quiz_count=quiz_count,
            member_count=len(user_ids),
            seat_limit=team.seat_limit,
        )


@router.post("/{team_id}/views", status_code=204)
def track_team_workspace_view(
    team_id: str,
    user: dict = Depends(get_current_user),
) -> Response:
    user_id = str(user["id"])
    with get_sync_session() as session:
        team, membership = _assert_team_member(session, team_id, user_id)
        role = "owner" if team.owner_uid == user_id or membership is None else membership.role
        member_count = _member_count(session, team.id)

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.dashboard_viewed",
        target_kind="team",
        target_id=team_id,
        before=None,
        after={"role": role, "member_count": member_count},
    )
    return Response(status_code=204)


@router.get("/{team_id}/member-progress", response_model=TeamMemberProgressResponse)
def get_team_member_progress(
    team_id: str,
    user: dict = Depends(get_current_user),
) -> TeamMemberProgressResponse:
    user_id = str(user["id"])
    week_start = progress_service._week_start_utc()
    now = _now()
    with get_sync_session() as session:
        team = _assert_team_admin(session, team_id, user_id)
        members = _team_members(session, team, user_id)
        user_ids = [member.user_id for member in members]

        writing_counts = _counts_by_user(
            session, WritingHistory, user_ids, WritingHistory.created_at, week_start,
        )
        listening_counts = _counts_by_user(
            session, ListeningHistory, user_ids, ListeningHistory.created_at, week_start,
        )
        quiz_counts = _counts_by_user(
            session, QuizHistory, user_ids, QuizHistory.created_at, week_start,
        )
        review_counts = _counts_by_user(
            session, ReviewEvent, user_ids, ReviewEvent.created_at, week_start,
        )
        reading_counts = {
            str(member_id): int(count)
            for member_id, count in session.execute(
                select(ReadingSession.user_id, func.count())
                .where(
                    ReadingSession.user_id.in_(user_ids),
                    ReadingSession.status == "submitted",
                    ReadingSession.submitted_at >= week_start,
                )
                .group_by(ReadingSession.user_id),
            ).all()
        } if user_ids else {}
        due_counts = {
            str(member_id): int(count)
            for member_id, count in session.execute(
                select(UserVocabulary.user_id, func.count())
                .where(
                    UserVocabulary.user_id.in_(user_ids),
                    UserVocabulary.archived_at.is_(None),
                    UserVocabulary.srs_next_review.is_not(None),
                    UserVocabulary.srs_next_review <= now,
                )
                .group_by(UserVocabulary.user_id),
            ).all()
        } if user_ids else {}
        profiles = {
            profile.id: profile
            for profile in session.execute(
                select(User).where(User.id.in_(user_ids)),
            ).scalars()
        } if user_ids else {}

        rows: list[TeamMemberProgressRow] = []
        for member in members:
            profile = profiles.get(member.user_id)
            weekly_minutes = (
                writing_counts.get(member.user_id, 0)
                * progress_service.MINUTES_PER_FEATURE["writing"]
                + listening_counts.get(member.user_id, 0)
                * progress_service.MINUTES_PER_FEATURE["listening"]
                + quiz_counts.get(member.user_id, 0)
                * progress_service.MINUTES_PER_FEATURE["quiz"]
                + reading_counts.get(member.user_id, 0)
                * progress_service.MINUTES_PER_FEATURE["reading"]
                + review_counts.get(member.user_id, 0)
                * progress_service.MINUTES_PER_FEATURE["vocab_review"]
            )
            rows.append(
                TeamMemberProgressRow(
                    user_id=member.user_id,
                    name=member.name,
                    email=member.email,
                    role=member.role,
                    last_active_date=profile.last_active_date if profile else None,
                    weekly_minutes=weekly_minutes,
                    words_reviewed=review_counts.get(member.user_id, 0),
                    due_words=due_counts.get(member.user_id, 0),
                    current_streak=int((profile.streak if profile else 0) or 0),
                )
            )

    return TeamMemberProgressResponse(week_start=week_start, members=rows)


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
