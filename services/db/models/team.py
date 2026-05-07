"""Team + TeamMember models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_uid: Mapped[str] = mapped_column(Text, nullable=False)
    plan_id: Mapped[str] = mapped_column(
        Text, ForeignKey("plans.id"), nullable=False,
    )
    plan_expires_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    seat_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TeamMember(Base):
    __tablename__ = "team_members"

    team_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_uid: Mapped[str] = mapped_column(Text, primary_key=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('member', 'admin')", name="ck_team_members_role"),
        Index("ix_team_members_user_uid", "user_uid"),
    )
