"""User model — mirrors ``services.repositories.dtos.UserDoc`` plus admin fields."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
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

    __table_args__ = (
        Index("ix_users_role_plan", "role", "plan"),
    )
