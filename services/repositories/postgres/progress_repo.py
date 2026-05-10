"""Postgres analytics repos (M8 Block D #234).

Three caller-facing repos:
- PostgresDailyPlansRepo: per-user-per-date plan + atomic activity completion.
- PostgresProgressSnapshotsRepo: per-user-per-date band/skills snapshot.
- PostgresProgressRecommendationsRepo: per-user-per-week tip set.

A fourth (DailyReviewSnapshot) is populated by
``scripts/rollup_daily_review_snapshots.py`` and read by the progress
service — no caller-facing repo needed yet.

All repos return dicts so legacy callers (``firebase_service.X``) swap
through the factory without DTO churn.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.db import get_sync_session
from services.db.models import (
    DailyPlan,
    DailyReviewSnapshot,
    ProgressRecommendation,
    ProgressSnapshot,
)


def _parse_date(s) -> _date:
    if isinstance(s, _date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    return _date.fromisoformat(str(s).split("T")[0])


# ─── Daily plans ────────────────────────────────────────────────────────


_PLAN_STRUCTURED = {
    "activities", "cap_minutes", "completed_count", "total_minutes",
    "days_until_exam", "exam_urgent", "generated_at", "completed_at",
}


def _plan_to_dict(p: DailyPlan) -> dict[str, Any]:
    return {
        "date": p.date.isoformat(),
        "activities": list(p.activities or []),
        "cap_minutes": p.cap_minutes,
        "completed_count": p.completed_count,
        "total_minutes": p.total_minutes,
        "days_until_exam": p.days_until_exam,
        "exam_urgent": p.exam_urgent,
        "generated_at": p.generated_at,
        "completed_at": p.completed_at,
    }


class PostgresDailyPlansRepo:
    """Per-user daily study plan."""

    def get(self, user_id, date_str: str) -> Optional[dict]:
        d = _parse_date(date_str)
        with get_sync_session() as s:
            row = s.execute(
                select(DailyPlan).where(
                    DailyPlan.user_id == str(user_id),
                    DailyPlan.date == d,
                )
            ).scalar_one_or_none()
        return _plan_to_dict(row) if row else None

    def save(self, user_id, date_str: str, plan: dict) -> None:
        """UPSERT — re-saving the same (user, date) replaces all fields."""
        d = _parse_date(date_str)
        now = datetime.now(timezone.utc)
        values = {k: v for k, v in plan.items() if k in _PLAN_STRUCTURED}
        values.setdefault("activities", [])
        values["generated_at"] = now
        stmt = pg_insert(DailyPlan).values(
            user_id=str(user_id),
            date=d,
            **values,
        ).on_conflict_do_update(
            index_elements=["user_id", "date"],
            set_=values,
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)

    def update(self, user_id, date_str: str, data: dict) -> None:
        """Partial update — only known structured fields are written."""
        d = _parse_date(date_str)
        values = {k: v for k, v in data.items() if k in _PLAN_STRUCTURED}
        if not values:
            return
        with get_sync_session() as s, s.begin():
            s.execute(
                update(DailyPlan)
                .where(
                    DailyPlan.user_id == str(user_id),
                    DailyPlan.date == d,
                )
                .values(**values),
            )

    def complete_activity(
        self, user_id, date_str: str, activity_id: str,
    ):
        """Atomically mark a plan activity completed.

        Returns:
        - ``None`` if no plan exists for the date
        - ``"NOT_FOUND"`` if the activity_id is not in the plan
        - the updated plan dict on success (incl. idempotent re-call)

        SELECT FOR UPDATE serializes concurrent completions of different
        activities so neither side clobbers the other's flag.
        """
        d = _parse_date(date_str)
        with get_sync_session() as s, s.begin():
            row = s.execute(
                select(DailyPlan)
                .where(
                    DailyPlan.user_id == str(user_id),
                    DailyPlan.date == d,
                )
                .with_for_update(),
            ).scalar_one_or_none()
            if row is None:
                return None

            activities = list(row.activities or [])
            if not any(a.get("id") == activity_id for a in activities):
                return "NOT_FOUND"

            changed = False
            for i, a in enumerate(activities):
                if a.get("id") == activity_id and not a.get("completed"):
                    activities[i] = {**a, "completed": True}
                    changed = True
                    break

            if changed:
                row.activities = activities
                row.completed_count = sum(
                    1 for a in activities if a.get("completed")
                )

            return _plan_to_dict(row)


# ─── Progress snapshots ────────────────────────────────────────────────


_SNAPSHOT_STRUCTURED = {"overall_band", "target_band", "skills"}


def _snapshot_to_dict(p: ProgressSnapshot) -> dict[str, Any]:
    return {
        "date": p.date.isoformat(),
        "overall_band": p.overall_band,
        "target_band": p.target_band,
        "skills": dict(p.skills or {}),
        "generated_at": p.generated_at,
    }


class PostgresProgressSnapshotsRepo:
    """Per-user-per-date band/skills snapshot."""

    def save(self, user_id, date_str: str, snapshot: dict) -> None:
        d = _parse_date(date_str)
        now = datetime.now(timezone.utc)
        values = {
            k: v for k, v in snapshot.items() if k in _SNAPSHOT_STRUCTURED
        }
        values.setdefault("skills", {})
        values["generated_at"] = now
        stmt = pg_insert(ProgressSnapshot).values(
            user_id=str(user_id),
            date=d,
            **values,
        ).on_conflict_do_update(
            index_elements=["user_id", "date"],
            set_=values,
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)

    def get(self, user_id, date_str: str) -> Optional[dict]:
        d = _parse_date(date_str)
        with get_sync_session() as s:
            row = s.execute(
                select(ProgressSnapshot).where(
                    ProgressSnapshot.user_id == str(user_id),
                    ProgressSnapshot.date == d,
                )
            ).scalar_one_or_none()
        return _snapshot_to_dict(row) if row else None

    def list_for_dates(self, user_id, date_strs: list[str]) -> list[dict]:
        """Fetch the subset of date_strs that have snapshots; skip missing."""
        if not date_strs:
            return []
        dates = [_parse_date(d) for d in date_strs]
        with get_sync_session() as s:
            rows = s.execute(
                select(ProgressSnapshot).where(
                    ProgressSnapshot.user_id == str(user_id),
                    ProgressSnapshot.date.in_(dates),
                )
            ).scalars().all()
        return [_snapshot_to_dict(r) for r in rows]


# ─── Progress recommendations ──────────────────────────────────────────


def _rec_to_dict(r: ProgressRecommendation) -> dict[str, Any]:
    return {
        "week_key": r.week_key,
        "tips": list(r.tips or []),
        "generated_at": r.generated_at,
    }


class PostgresProgressRecommendationsRepo:
    """Per-user-per-week coaching recommendations."""

    def get(self, user_id, week_key: str) -> Optional[dict]:
        with get_sync_session() as s:
            row = s.execute(
                select(ProgressRecommendation).where(
                    ProgressRecommendation.user_id == str(user_id),
                    ProgressRecommendation.week_key == week_key,
                )
            ).scalar_one_or_none()
        return _rec_to_dict(row) if row else None

    def save(self, user_id, week_key: str, data: dict) -> None:
        now = datetime.now(timezone.utc)
        # ``data`` typically contains {tips: [...]}. Anything else gets
        # dropped on the floor — there's no JSONB tail column.
        tips = data.get("tips") or []
        stmt = pg_insert(ProgressRecommendation).values(
            user_id=str(user_id),
            week_key=week_key,
            tips=tips,
            generated_at=now,
        ).on_conflict_do_update(
            index_elements=["user_id", "week_key"],
            set_={"tips": tips, "generated_at": now},
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)


__all__ = [
    "PostgresDailyPlansRepo",
    "PostgresProgressRecommendationsRepo",
    "PostgresProgressSnapshotsRepo",
]
