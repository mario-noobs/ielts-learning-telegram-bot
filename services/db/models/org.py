"""Org + OrgAdmin + OrgTeam models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class Org(Base):
    __tablename__ = "orgs"

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrgAdmin(Base):
    __tablename__ = "org_admins"

    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_uid: Mapped[str] = mapped_column(Text, primary_key=True)


class OrgTeam(Base):
    __tablename__ = "org_teams"

    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    team_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
