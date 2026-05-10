"""Analytics tables — daily plans, progress snapshots, recommendations,
review-event rollups (M8 cutover Block D).

All four tables are user-scoped + low-traffic (computed views written
once per day or per week). Composite primary keys on (user_id, date)
match the natural shape — no surrogate ids needed.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class DailyPlan(Base):
    __tablename__ = "daily_plans"

    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    date: Mapped[_date] = mapped_column(Date, nullable=False)
    activities: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    cap_minutes: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    completed_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    total_minutes: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    days_until_exam: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    exam_urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "date", name="pk_daily_plans"),
    )


class ProgressSnapshot(Base):
    __tablename__ = "progress_snapshots"

    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    date: Mapped[_date] = mapped_column(Date, nullable=False)
    overall_band: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_band: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # {writing: {band, sample_size}, vocabulary: {...}, listening: {...}, ...}
    skills: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "date", name="pk_progress_snapshots"),
    )


class ProgressRecommendation(Base):
    __tablename__ = "progress_recommendations"

    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    # ISO week key (e.g. "2026-W18") matches the natural cadence of
    # weekly coaching tip generation.
    week_key: Mapped[str] = mapped_column(Text, nullable=False)
    tips: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "user_id", "week_key", name="pk_progress_recommendations",
        ),
    )


class DailyReviewSnapshot(Base):
    """Nightly rollup of review_events into per-user-per-day counters.

    Replaces the on-demand ``COUNT(*) ... GROUP BY user_id, date`` scan
    on ``review_events`` for dashboard reads. Cron rebuilds the previous
    day's row each night.
    """

    __tablename__ = "daily_review_snapshots"

    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_date: Mapped[_date] = mapped_column(Date, nullable=False)
    reviews_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviews_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    words_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    study_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "user_id", "snapshot_date", name="pk_daily_review_snapshots",
        ),
    )


__all__ = [
    "DailyPlan",
    "DailyReviewSnapshot",
    "ProgressRecommendation",
    "ProgressSnapshot",
]
