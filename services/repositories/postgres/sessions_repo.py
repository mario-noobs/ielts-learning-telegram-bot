"""Postgres repos for ephemeral session state (M8 Block C #234).

Two repos:
- PostgresQuizSessionsRepo: short-lived bot quiz state.
- PostgresReadingSessionsRepo: web reading-lab attempt state.

Both expose dict-shaped APIs so legacy callers
(``firebase_service.{save,get,update}_*_session``) swap through the
factory without churn.

Cleanup of stale sessions is handled by ``scripts/cleanup_expired.py``
(registered as a daily cron in ``services.scheduler_service``). Default
TTL is 7 days from ``started_at`` / ``created_at``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.db import get_sync_session
from services.db.models import QuizSession, ReadingSession


# ─── Quiz sessions ──────────────────────────────────────────────────────


def _quiz_to_dict(s: QuizSession) -> dict[str, Any]:
    return {
        "questions": list(s.questions or []),
        "answered_ids": list(s.answered_ids or []),
        "created_at": s.created_at,
    }


class PostgresQuizSessionsRepo:
    """Bot-side quiz session: full question docs + answered_ids."""

    def save(self, user_id, session_id: str, questions: list[dict]) -> None:
        """Create/replace a session row.

        Idempotent: re-saving the same session_id replaces the questions
        list and resets answered_ids — matches Firestore .set() semantics.
        """
        now = datetime.now(timezone.utc)
        stmt = pg_insert(QuizSession).values(
            id=session_id,
            user_id=str(user_id),
            questions=questions,
            answered_ids=[],
            created_at=now,
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={
                "user_id": str(user_id),
                "questions": questions,
                "answered_ids": [],
                "created_at": now,
            },
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)

    def get(self, user_id, session_id: str) -> Optional[dict]:
        with get_sync_session() as s:
            row = s.execute(
                select(QuizSession).where(
                    QuizSession.id == session_id,
                    QuizSession.user_id == str(user_id),
                )
            ).scalar_one_or_none()
        return _quiz_to_dict(row) if row else None

    def mark_question_answered(
        self, user_id, session_id: str, question_id: str,
    ) -> None:
        """Append question_id to answered_ids if not already present.

        SELECT FOR UPDATE + Python-side merge — race-safe because the row
        lock serializes concurrent answer callbacks.
        """
        with get_sync_session() as s, s.begin():
            row = s.execute(
                select(QuizSession)
                .where(
                    QuizSession.id == session_id,
                    QuizSession.user_id == str(user_id),
                )
                .with_for_update(),
            ).scalar_one_or_none()
            if row is None:
                return
            answered = list(row.answered_ids or [])
            if question_id not in answered:
                answered.append(question_id)
                row.answered_ids = answered

    def cleanup_older_than(self, days: int = 7) -> int:
        """Delete sessions whose created_at is older than ``days`` days.

        Returns the row count deleted. Called by the nightly cleanup cron.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with get_sync_session() as s, s.begin():
            result = s.execute(
                delete(QuizSession).where(QuizSession.created_at < cutoff),
            )
        return result.rowcount or 0


# ─── Reading sessions ───────────────────────────────────────────────────


_READING_STRUCTURED = {
    "passage_id", "status", "questions", "answer_key", "user_answers",
    "grade", "idempotency_key", "started_at", "submitted_at",
    "expires_at", "updated_at",
}


def _reading_to_dict(s: ReadingSession) -> dict[str, Any]:
    return {
        "id": s.id,
        "passage_id": s.passage_id,
        "status": s.status,
        "questions": list(s.questions or []),
        "answer_key": list(s.answer_key or []),
        "user_answers": list(s.user_answers or []) if s.user_answers else None,
        "grade": dict(s.grade) if s.grade else None,
        "idempotency_key": s.idempotency_key,
        "started_at": s.started_at,
        "submitted_at": s.submitted_at,
        "expires_at": s.expires_at,
        "updated_at": s.updated_at,
    }


class PostgresReadingSessionsRepo:
    """Web reading-lab session: passage attempt with answer_key snapshot."""

    def save(self, user_id, session_id: str, data: dict) -> None:
        """Insert or replace a session row.

        Replicates Firestore .set() semantics (full overwrite). Callers
        passing a partial ``data`` should use ``update`` instead.
        """
        now = datetime.now(timezone.utc)
        values = {k: v for k, v in data.items() if k in _READING_STRUCTURED}
        values.setdefault("status", "in_progress")
        values.setdefault("questions", [])
        values.setdefault("answer_key", [])
        values.setdefault("started_at", now)
        values["updated_at"] = now
        stmt = pg_insert(ReadingSession).values(
            id=session_id,
            user_id=str(user_id),
            **values,
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={**values, "user_id": str(user_id)},
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)

    def get(self, user_id, session_id: str) -> Optional[dict]:
        with get_sync_session() as s:
            row = s.execute(
                select(ReadingSession).where(
                    ReadingSession.id == session_id,
                    ReadingSession.user_id == str(user_id),
                )
            ).scalar_one_or_none()
        return _reading_to_dict(row) if row else None

    def update(self, user_id, session_id: str, data: dict) -> None:
        """Partial update — only fields present in ``data`` are written.

        Mirrors Firestore .update() (selective field write). updated_at
        always refreshes.
        """
        values = {k: v for k, v in data.items() if k in _READING_STRUCTURED}
        if not values:
            return
        values["updated_at"] = datetime.now(timezone.utc)
        with get_sync_session() as s, s.begin():
            s.execute(
                update(ReadingSession)
                .where(
                    ReadingSession.id == session_id,
                    ReadingSession.user_id == str(user_id),
                )
                .values(**values),
            )

    def list_for_user(self, user_id, limit: int = 10) -> list[dict]:
        """Recent sessions newest-first (submitted + in_progress)."""
        with get_sync_session() as s:
            rows = s.execute(
                select(ReadingSession)
                .where(ReadingSession.user_id == str(user_id))
                .order_by(ReadingSession.updated_at.desc())
                .limit(limit)
            ).scalars().all()
        return [_reading_to_dict(r) for r in rows]

    def cleanup_older_than(self, days: int = 7) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with get_sync_session() as s, s.begin():
            result = s.execute(
                delete(ReadingSession).where(ReadingSession.started_at < cutoff),
            )
        return result.rowcount or 0


__all__ = ["PostgresQuizSessionsRepo", "PostgresReadingSessionsRepo"]
