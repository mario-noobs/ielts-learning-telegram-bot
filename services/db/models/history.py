"""History tables — quiz, writing, listening, daily-words.

Each row is a per-user record (FK→users). Hot path: insert + recent-N
read for the user's history page.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class QuizHistory(Base):
    __tablename__ = "quiz_history"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    quiz_type: Mapped[str] = mapped_column(Text, nullable=False)  # FS field: `type`
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_challenge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    word_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        Index("ix_quiz_history_user_id_created_at", "user_id", text("created_at DESC")),
    )


class WritingHistory(Base):
    __tablename__ = "writing_history"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    task_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    essay_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overall_band: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary_vi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scores: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    criterion_feedback: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True,
    )
    paragraph_annotations: Mapped[Optional[list[Any]]] = mapped_column(
        JSONB, nullable=True,
    )
    feedback: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    shared_to_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        Index(
            "ix_writing_history_user_id_created_at",
            "user_id", text("created_at DESC"),
        ),
    )


class UserDailyWords(Base):
    __tablename__ = "user_daily_words"

    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    words: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "date", name="pk_user_daily_words"),
    )


class ListeningHistory(Base):
    __tablename__ = "listening_history"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    exercise_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    band: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_estimate_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        Index(
            "ix_listening_history_user_id_created_at",
            "user_id", text("created_at DESC"),
        ),
    )


__all__ = ["QuizHistory", "WritingHistory", "UserDailyWords", "ListeningHistory"]
