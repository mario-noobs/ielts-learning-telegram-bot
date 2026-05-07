"""Postgres implementation of ``PlanRepo``."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from services.db import get_sync_session
from services.db.models import Plan

from ..dtos import PlanDoc


def _row_to_doc(p: Plan) -> PlanDoc:
    return PlanDoc(
        id=p.id,
        name=p.name,
        daily_ai_quota=p.daily_ai_quota,
        monthly_ai_quota=p.monthly_ai_quota,
        max_team_seats=p.max_team_seats,
        features=list(p.features or []),
        created_at=p.created_at,
    )


class PostgresPlanRepo:
    def list_all(self) -> list[PlanDoc]:
        with get_sync_session() as s:
            rows = s.execute(select(Plan).order_by(Plan.id)).scalars().all()
            return [_row_to_doc(r) for r in rows]

    def get(self, plan_id: str) -> Optional[PlanDoc]:
        with get_sync_session() as s:
            row = s.get(Plan, plan_id)
            return _row_to_doc(row) if row else None


__all__ = ["PostgresPlanRepo"]
