"""Postgres implementation of ``ListeningHistoryRepo``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update

from services.db import get_sync_session
from services.db.models import ListeningHistory

from ..protocols import UserId

# Listening history doesn't yet have a typed DTO — callers consume dicts
# (see ``firebase_service.list_listening_exercises``). We keep the same
# dict-returning shape here so the cutover is a behaviour-preserving swap.

_STRUCTURED_KEYS = {
    "id", "exercise_type", "title", "topic", "band", "score", "total",
    "duration_estimate_sec", "submitted", "created_at",
}


def _row_to_dict(row: ListeningHistory) -> dict[str, Any]:
    payload = dict(row.payload or {})
    return {
        "id": row.id,
        "exercise_type": row.exercise_type,
        "title": row.title,
        "topic": row.topic,
        "band": row.band,
        "score": row.score,
        "total": row.total,
        "duration_estimate_sec": row.duration_estimate_sec,
        "submitted": row.submitted,
        "created_at": row.created_at,
        **payload,
    }


class PostgresListeningHistoryRepo:
    """Postgres-backed listening history repo.

    Mirrors the shape of the legacy ``firebase_service.{save,get,update,
    list}_listening_exercise`` helpers — returns dicts, not DTOs.
    """

    def save(self, user_id: UserId, exercise_data: dict) -> str:
        payload_tail = {
            k: v for k, v in exercise_data.items() if k not in _STRUCTURED_KEYS
        }
        row = ListeningHistory(
            id=exercise_data.get("id") or uuid.uuid4().hex,
            user_id=str(user_id),
            exercise_type=exercise_data.get("exercise_type"),
            title=exercise_data.get("title"),
            topic=exercise_data.get("topic"),
            band=exercise_data.get("band"),
            score=exercise_data.get("score"),
            total=exercise_data.get("total"),
            duration_estimate_sec=exercise_data.get("duration_estimate_sec"),
            submitted=bool(exercise_data.get("submitted", False)),
            payload=payload_tail or None,
            created_at=exercise_data.get("created_at") or datetime.now(timezone.utc),
        )
        with get_sync_session() as s, s.begin():
            s.add(row)
        return row.id

    def get(self, user_id: UserId, exercise_id: str) -> Optional[dict]:
        with get_sync_session() as s:
            row = s.execute(
                select(ListeningHistory).where(
                    ListeningHistory.user_id == str(user_id),
                    ListeningHistory.id == exercise_id,
                )
            ).scalar_one_or_none()
        return _row_to_dict(row) if row else None

    def update(self, user_id: UserId, exercise_id: str, data: dict) -> None:
        # Split structured fields from loose-tail. Tail merges into payload
        # so the next read sees the same shape Firestore would have.
        structured = {k: v for k, v in data.items() if k in _STRUCTURED_KEYS}
        tail = {k: v for k, v in data.items() if k not in _STRUCTURED_KEYS}

        with get_sync_session() as s, s.begin():
            if tail:
                row = s.execute(
                    select(ListeningHistory).where(
                        ListeningHistory.user_id == str(user_id),
                        ListeningHistory.id == exercise_id,
                    )
                ).scalar_one_or_none()
                if row is None:
                    return
                merged = dict(row.payload or {})
                merged.update(tail)
                row.payload = merged
                for k, v in structured.items():
                    setattr(row, k, v)
            elif structured:
                s.execute(
                    update(ListeningHistory)
                    .where(
                        ListeningHistory.user_id == str(user_id),
                        ListeningHistory.id == exercise_id,
                    )
                    .values(**structured),
                )

    def list(self, user_id: UserId, limit: int = 50) -> list[dict]:
        with get_sync_session() as s:
            rows = s.execute(
                select(ListeningHistory)
                .where(ListeningHistory.user_id == str(user_id))
                .order_by(ListeningHistory.created_at.desc())
                .limit(limit)
            ).scalars().all()
        return [_row_to_dict(r) for r in rows]


__all__ = ["PostgresListeningHistoryRepo"]
