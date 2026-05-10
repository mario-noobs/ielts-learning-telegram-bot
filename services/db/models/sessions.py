"""User session state models — quiz + reading (M8 cutover Block C).

Sessions are ephemeral by design: short-lived state for a single
exercise attempt. ``scripts/cleanup_expired.py`` deletes rows older
than 7 days nightly; the partial index on started_at keeps the cron
cheap.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    questions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    # FIFO list of question_ids the user has already answered in this
    # session — bot uses it to skip already-answered questions on retry.
    answered_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        Index("ix_quiz_sessions_created_at", "created_at"),
    )


class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    passage_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="in_progress")
    questions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    # answer_key snapshotted at session start so grading is deterministic
    # even if the underlying reading_questions row changes mid-session.
    answer_key: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    user_answers: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    grade: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'submitted', 'expired')",
            name="ck_reading_sessions_status",
        ),
        Index("ix_reading_sessions_started_at", "started_at"),
    )


__all__ = ["QuizSession", "ReadingSession"]
