"""Postgres implementation of ``OrgRepo``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select, update

from services.db import get_sync_session
from services.db.models import Org, OrgAdmin, OrgTeam

from ..dtos import OrgDoc


def _org_to_doc(o: Org) -> OrgDoc:
    return OrgDoc(
        id=o.id,
        name=o.name,
        owner_uid=o.owner_uid,
        plan_id=o.plan_id,
        plan_expires_at=o.plan_expires_at,
        created_at=o.created_at,
    )


class PostgresOrgRepo:
    def create(self, name: str, owner_uid: str, plan_id: str) -> OrgDoc:
        o = Org(
            name=name,
            owner_uid=owner_uid,
            plan_id=plan_id,
            created_at=datetime.now(timezone.utc),
        )
        with get_sync_session() as s, s.begin():
            s.add(o)
            s.flush()
            s.refresh(o)
        return _org_to_doc(o)

    def get(self, org_id: str) -> Optional[OrgDoc]:
        with get_sync_session() as s:
            row = s.get(Org, org_id)
            return _org_to_doc(row) if row else None

    def update(self, org_id: str, data: dict) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(update(Org).where(Org.id == org_id).values(**data))

    def delete(self, org_id: str) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(delete(Org).where(Org.id == org_id))

    def list_all(self) -> list[OrgDoc]:
        with get_sync_session() as s:
            rows = s.execute(select(Org).order_by(Org.created_at)).scalars().all()
            return [_org_to_doc(r) for r in rows]

    def add_admin(self, org_id: str, user_uid: str) -> None:
        with get_sync_session() as s, s.begin():
            s.add(OrgAdmin(org_id=org_id, user_uid=user_uid))

    def remove_admin(self, org_id: str, user_uid: str) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(
                delete(OrgAdmin)
                .where(OrgAdmin.org_id == org_id)
                .where(OrgAdmin.user_uid == user_uid)
            )

    def list_admins(self, org_id: str) -> list[str]:
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(OrgAdmin.user_uid).where(OrgAdmin.org_id == org_id)
                )
                .scalars()
                .all()
            )
            return list(rows)

    def link_team(self, org_id: str, team_id: str) -> None:
        with get_sync_session() as s, s.begin():
            s.add(OrgTeam(org_id=org_id, team_id=team_id))

    def unlink_team(self, org_id: str, team_id: str) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(
                delete(OrgTeam)
                .where(OrgTeam.org_id == org_id)
                .where(OrgTeam.team_id == team_id)
            )

    def list_teams(self, org_id: str) -> list[str]:
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(OrgTeam.team_id).where(OrgTeam.org_id == org_id)
                )
                .scalars()
                .all()
            )
            return list(rows)


__all__ = ["PostgresOrgRepo"]
