"""User model — mirrors ``services.repositories.dtos.UserDoc`` plus admin fields."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    username: Mapped[str] = mapped_column(Text, nullable=False, default="")
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_uid: Mapped[Optional[str]] = mapped_column(Text, nullable=True, unique=True)
    group_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    target_band: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    daily_time: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_quizzes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    challenge_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exam_date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weekly_goal_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # M11 admin fields. team_id / org_id gain FK constraints in the M11.1 migration
    # once the teams / orgs tables exist.
    role: Mapped[str] = mapped_column(Text, nullable=False, default="user")
    plan: Mapped[str] = mapped_column(Text, nullable=False, default="free")
    plan_expires_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    team_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True, index=True,
    )
    org_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True,
    )
    quota_override: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_active_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    signup_cohort: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)

    # FIFO ring of last-N personal topics (US-#226 rotation). vocab_service
    # rewrites this on every /mydaily — keep app-side capped at
    # RECENT_TOPICS_KEEP=5 entries.
    recent_personal_topics: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]",
    )

    # #242: per-user setting for /mydaily generation count. CHECK 3..10
    # is enforced at the DB layer in migration 0009.
    daily_words_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5",
    )
    # #242: gates the first-login quick-tour dialog on the web app.
    dismissed_onboarding: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    # #dashboard-polish: explicit "user configured this" signal so the
    # readiness sub-tasks can tick on save rather than from the
    # unclearable default values (target_band 7.0, weekly_goal 150).
    target_band_set: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    weekly_goal_set: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    local_auth: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    __table_args__ = (
        Index("ix_users_role_plan", "role", "plan"),
    )
