"""Postgres implementation of ``AuditLogRepo``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from services.db import get_sync_session
from services.db.models import AuditLog

from ..dtos import AuditLogDoc


def _row_to_doc(r: AuditLog) -> AuditLogDoc:
    return AuditLogDoc(
        id=r.id,
        event_type=r.event_type,
        actor_uid=r.actor_uid,
        target_kind=r.target_kind,
        target_id=r.target_id,
        before=r.before,
        after=r.after,
        request_id=r.request_id,
        created_at=r.created_at,
    )


class PostgresAuditLogRepo:
    def append(
        self,
        event_type: str,
        actor_uid: str,
        target_kind: str,
        target_id: str,
        before: Optional[dict],
        after: Optional[dict],
        request_id: Optional[str],
    ) -> int:
        row = AuditLog(
            event_type=event_type,
            actor_uid=actor_uid,
            target_kind=target_kind,
            target_id=target_id,
            before=before,
            after=after,
            request_id=request_id,
            created_at=datetime.now(timezone.utc),
        )
        with get_sync_session() as s, s.begin():
            s.add(row)
            s.flush()
            return row.id

    def list_by_target(
        self, target_kind: str, target_id: str, limit: int = 50,
    ) -> list[AuditLogDoc]:
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(AuditLog)
                    .where(AuditLog.target_kind == target_kind)
                    .where(AuditLog.target_id == target_id)
                    .order_by(AuditLog.created_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [_row_to_doc(r) for r in rows]

    def list_by_actor(
        self, actor_uid: str, limit: int = 50,
    ) -> list[AuditLogDoc]:
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(AuditLog)
                    .where(AuditLog.actor_uid == actor_uid)
                    .order_by(AuditLog.created_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [_row_to_doc(r) for r in rows]

    def list_recent(self, limit: int = 100) -> list[AuditLogDoc]:
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
                )
                .scalars()
                .all()
            )
            return [_row_to_doc(r) for r in rows]


__all__ = ["PostgresAuditLogRepo"]
