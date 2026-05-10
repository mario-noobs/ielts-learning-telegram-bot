"""Postgres implementation of ``WritingHistoryRepo``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from services.db import get_sync_session
from services.db.models import WritingHistory

from ..dtos import WritingHistoryEntry
from ..protocols import UserId


def _row_to_dto(row: WritingHistory) -> WritingHistoryEntry:
    """Hydrate DTO from row + JSONB tails.

    DTO has ``extra="allow"`` so the structured columns merge with the
    catch-all feedback dict without conflict.
    """
    extras: dict = {}
    if row.scores:
        extras["scores"] = dict(row.scores)
    if row.criterion_feedback:
        extras["criterion_feedback"] = dict(row.criterion_feedback)
    if row.paragraph_annotations:
        extras["paragraph_annotations"] = list(row.paragraph_annotations)
    if row.feedback:
        extras.update(row.feedback)
    if row.summary_vi is not None:
        extras["summary_vi"] = row.summary_vi
    if row.original_text is not None:
        extras["original_text"] = row.original_text
    if row.language is not None:
        extras["language"] = row.language
    extras["shared_to_group"] = row.shared_to_group
    return WritingHistoryEntry.model_validate({
        "id": row.id,
        "text": row.essay_text or "",
        "task_type": row.task_type or "task2",
        "prompt": row.prompt or "",
        "overall_band": row.overall_band or 0.0,
        "word_count": row.word_count or 0,
        "created_at": row.created_at,
        **extras,
    })


_STRUCTURED_KEYS = {
    "id", "text", "task_type", "prompt", "essay_text", "original_text",
    "language", "overall_band", "word_count", "summary_vi", "scores",
    "criterion_feedback", "paragraph_annotations", "shared_to_group",
    "created_at",
}


class PostgresWritingHistoryRepo:
    """Postgres-backed ``WritingHistoryRepo``."""

    def _build_row(self, user_id: UserId, writing_data: dict) -> WritingHistory:
        feedback_tail = {
            k: v for k, v in writing_data.items() if k not in _STRUCTURED_KEYS
        }
        return WritingHistory(
            id=writing_data.get("id") or uuid.uuid4().hex,
            user_id=str(user_id),
            task_type=writing_data.get("task_type"),
            prompt=writing_data.get("prompt"),
            essay_text=writing_data.get("text") or writing_data.get("essay_text"),
            original_text=writing_data.get("original_text"),
            language=writing_data.get("language"),
            overall_band=writing_data.get("overall_band"),
            word_count=writing_data.get("word_count"),
            summary_vi=writing_data.get("summary_vi"),
            scores=writing_data.get("scores"),
            criterion_feedback=writing_data.get("criterion_feedback"),
            paragraph_annotations=writing_data.get("paragraph_annotations"),
            feedback=feedback_tail or None,
            shared_to_group=bool(writing_data.get("shared_to_group", False)),
            created_at=writing_data.get("created_at") or datetime.now(timezone.utc),
        )

    def save(self, user_id: UserId, writing_data: dict) -> None:
        with get_sync_session() as s, s.begin():
            s.add(self._build_row(user_id, writing_data))

    def save_submission(self, user_id: UserId, writing_data: dict) -> str:
        row = self._build_row(user_id, writing_data)
        with get_sync_session() as s, s.begin():
            s.add(row)
        return row.id

    def get_submission(
        self, user_id: UserId, submission_id: str,
    ) -> Optional[WritingHistoryEntry]:
        with get_sync_session() as s:
            row = s.execute(
                select(WritingHistory).where(
                    WritingHistory.user_id == str(user_id),
                    WritingHistory.id == submission_id,
                )
            ).scalar_one_or_none()
        return _row_to_dto(row) if row else None

    def list_submissions(
        self, user_id: UserId, limit: int = 50,
    ) -> list[WritingHistoryEntry]:
        with get_sync_session() as s:
            rows = s.execute(
                select(WritingHistory)
                .where(WritingHistory.user_id == str(user_id))
                .order_by(WritingHistory.created_at.desc())
                .limit(limit)
            ).scalars().all()
        return [_row_to_dto(r) for r in rows]


__all__ = ["PostgresWritingHistoryRepo"]
