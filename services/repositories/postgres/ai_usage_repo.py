"""Postgres implementation of ``AiUsageRepo``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.db import get_sync_session
from services.db.models import AiUsage

from ..dtos import AiUsageDoc


def _row_to_doc(r: AiUsage) -> AiUsageDoc:
    return AiUsageDoc(
        user_uid=r.user_uid,
        date=r.date,
        feature=r.feature,
        count=r.count,
        last_call_at=r.last_call_at,
    )


class PostgresAiUsageRepo:
    def increment(
        self,
        user_uid: str,
        feature: str,
        when: Optional[datetime] = None,
    ) -> int:
        ts = when or datetime.now(timezone.utc)
        the_date = ts.date()
        stmt = (
            pg_insert(AiUsage)
            .values(
                user_uid=user_uid,
                date=the_date,
                feature=feature,
                count=1,
                last_call_at=ts,
            )
            .on_conflict_do_update(
                index_elements=["user_uid", "date", "feature"],
                set_={
                    "count": AiUsage.count + 1,
                    "last_call_at": ts,
                },
            )
            .returning(AiUsage.count)
        )
        with get_sync_session() as s, s.begin():
            return s.execute(stmt).scalar_one()

    def get_today(self, user_uid: str) -> dict[str, int]:
        today = datetime.now(timezone.utc).date()
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(AiUsage.feature, AiUsage.count)
                    .where(AiUsage.user_uid == user_uid)
                    .where(AiUsage.date == today)
                )
                .all()
            )
            return {feature: count for feature, count in rows}

    def get_window(self, user_uid: str, days: int) -> list[AiUsageDoc]:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days - 1)
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(AiUsage)
                    .where(AiUsage.user_uid == user_uid)
                    .where(AiUsage.date >= start)
                    .where(AiUsage.date <= end)
                    .order_by(AiUsage.date, AiUsage.feature)
                )
                .scalars()
                .all()
            )
            return [_row_to_doc(r) for r in rows]


__all__ = ["PostgresAiUsageRepo"]
