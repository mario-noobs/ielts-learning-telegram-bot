"""Postgres implementation of ``QuizHistoryRepo``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from services.db import get_sync_session
from services.db.models import QuizHistory

from ..dtos import QuizHistoryEntry
from ..protocols import UserId


def _row_to_dto(row: QuizHistory) -> QuizHistoryEntry:
    """Hydrate DTO from row, folding payload back into top-level fields.

    QuizHistoryEntry has ``extra="allow"`` so the loose payload (question,
    user_answer, correct_answer, etc.) round-trips through model_validate.
    """
    payload = dict(row.payload or {})
    return QuizHistoryEntry.model_validate({
        "id": row.id,
        "is_correct": row.is_correct,
        "created_at": row.created_at,
        "type": row.quiz_type,
        "is_challenge": row.is_challenge,
        "word_id": row.word_id,
        **payload,
    })


_STRUCTURED_KEYS = {
    "type", "is_correct", "is_challenge", "word_id", "created_at", "id",
}


class PostgresQuizHistoryRepo:
    """Postgres-backed ``QuizHistoryRepo``."""

    def save_result(self, user_id: UserId, quiz_data: dict) -> None:
        # Atomic counter bump on the user doc — concurrent saves compose
        # without losing increments because UPDATE col=col+1 is server-side.
        from services.repositories import get_user_repo
        get_user_repo().increment_counters(
            user_id,
            total_quizzes=1,
            total_correct=1 if quiz_data.get("is_correct") else 0,
        )

        # Loose-tail payload: any field that doesn't have its own column.
        payload = {k: v for k, v in quiz_data.items() if k not in _STRUCTURED_KEYS}
        row = QuizHistory(
            id=quiz_data.get("id") or uuid.uuid4().hex,
            user_id=str(user_id),
            quiz_type=str(quiz_data.get("type") or "unknown"),
            is_correct=bool(quiz_data.get("is_correct")),
            is_challenge=bool(quiz_data.get("is_challenge", False)),
            word_id=quiz_data.get("word_id"),
            payload=payload or None,
            created_at=quiz_data.get("created_at") or datetime.now(timezone.utc),
        )
        with get_sync_session() as s, s.begin():
            s.add(row)

    def get_latest(self, user_id: UserId) -> Optional[QuizHistoryEntry]:
        with get_sync_session() as s:
            row = s.execute(
                select(QuizHistory)
                .where(QuizHistory.user_id == str(user_id))
                .order_by(QuizHistory.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        return _row_to_dto(row) if row else None


__all__ = ["PostgresQuizHistoryRepo"]
