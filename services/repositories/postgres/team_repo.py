"""Postgres implementation of ``TeamRepo``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select, update

from services.db import get_sync_session
from services.db.models import Team, TeamMember

from ..dtos import TeamDoc, TeamMemberDoc


def _team_to_doc(t: Team) -> TeamDoc:
    return TeamDoc(
        id=t.id,
        name=t.name,
        owner_uid=t.owner_uid,
        plan_id=t.plan_id,
        plan_expires_at=t.plan_expires_at,
        seat_limit=t.seat_limit,
        created_by=t.created_by,
        created_at=t.created_at,
    )


def _member_to_doc(m: TeamMember) -> TeamMemberDoc:
    return TeamMemberDoc(
        team_id=m.team_id,
        user_uid=m.user_uid,
        role=m.role,
        joined_at=m.joined_at,
    )


class PostgresTeamRepo:
    def create(
        self,
        name: str,
        owner_uid: str,
        plan_id: str,
        seat_limit: int,
        created_by: str,
    ) -> TeamDoc:
        now = datetime.now(timezone.utc)
        t = Team(
            name=name,
            owner_uid=owner_uid,
            plan_id=plan_id,
            seat_limit=seat_limit,
            created_by=created_by,
            created_at=now,
        )
        with get_sync_session() as s, s.begin():
            s.add(t)
            s.flush()  # populate server-default id
            s.refresh(t)
        return _team_to_doc(t)

    def get(self, team_id: str) -> Optional[TeamDoc]:
        with get_sync_session() as s:
            row = s.get(Team, team_id)
            return _team_to_doc(row) if row else None

    def update(self, team_id: str, data: dict) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(update(Team).where(Team.id == team_id).values(**data))

    def delete(self, team_id: str) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(delete(Team).where(Team.id == team_id))

    def list_all(self) -> list[TeamDoc]:
        with get_sync_session() as s:
            rows = s.execute(select(Team).order_by(Team.created_at)).scalars().all()
            return [_team_to_doc(r) for r in rows]

    def list_for_user(self, user_uid: str) -> list[TeamDoc]:
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(Team)
                    .join(TeamMember, TeamMember.team_id == Team.id)
                    .where(TeamMember.user_uid == user_uid)
                )
                .scalars()
                .all()
            )
            return [_team_to_doc(r) for r in rows]

    def add_member(self, team_id: str, user_uid: str, role: str) -> None:
        m = TeamMember(
            team_id=team_id,
            user_uid=user_uid,
            role=role,
            joined_at=datetime.now(timezone.utc),
        )
        with get_sync_session() as s, s.begin():
            s.add(m)

    def remove_member(self, team_id: str, user_uid: str) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(
                delete(TeamMember)
                .where(TeamMember.team_id == team_id)
                .where(TeamMember.user_uid == user_uid)
            )

    def list_members(self, team_id: str) -> list[TeamMemberDoc]:
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(TeamMember)
                    .where(TeamMember.team_id == team_id)
                    .order_by(TeamMember.joined_at)
                )
                .scalars()
                .all()
            )
            return [_member_to_doc(r) for r in rows]


__all__ = ["PostgresTeamRepo"]
