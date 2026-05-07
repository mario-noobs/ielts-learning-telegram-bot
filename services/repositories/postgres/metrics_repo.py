"""Postgres implementation of ``MetricsRepo``."""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.db import get_sync_session
from services.db.models import PlatformMetric

from ..dtos import PlatformMetricDoc


def _row_to_doc(r: PlatformMetric) -> PlatformMetricDoc:
    return PlatformMetricDoc(
        date=r.date,
        total_users=r.total_users,
        dau=r.dau,
        signups=r.signups,
        ai_calls=r.ai_calls,
        plan_distribution=dict(r.plan_distribution or {}),
        errors_count=r.errors_count,
        created_at=r.created_at,
    )


class PostgresMetricsRepo:
    def upsert_daily(
        self,
        date: _date,
        total_users: int,
        dau: int,
        signups: int,
        ai_calls: int,
        plan_distribution: dict,
        errors_count: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(PlatformMetric)
            .values(
                date=date,
                total_users=total_users,
                dau=dau,
                signups=signups,
                ai_calls=ai_calls,
                plan_distribution=plan_distribution,
                errors_count=errors_count,
                created_at=now,
            )
            .on_conflict_do_update(
                index_elements=["date"],
                set_={
                    "total_users": total_users,
                    "dau": dau,
                    "signups": signups,
                    "ai_calls": ai_calls,
                    "plan_distribution": plan_distribution,
                    "errors_count": errors_count,
                    "created_at": now,
                },
            )
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)

    def get_range(self, start: _date, end: _date) -> list[PlatformMetricDoc]:
        with get_sync_session() as s:
            rows = (
                s.execute(
                    select(PlatformMetric)
                    .where(PlatformMetric.date >= start)
                    .where(PlatformMetric.date <= end)
                    .order_by(PlatformMetric.date)
                )
                .scalars()
                .all()
            )
            return [_row_to_doc(r) for r in rows]

    def get_latest(self) -> Optional[PlatformMetricDoc]:
        with get_sync_session() as s:
            row = s.execute(
                select(PlatformMetric).order_by(PlatformMetric.date.desc()).limit(1)
            ).scalar_one_or_none()
            return _row_to_doc(row) if row else None


__all__ = ["PostgresMetricsRepo"]
