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
from sqlalchemy.dialects.postgresql import JSONB, UUID
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


class TeamInvite(Base):
    __tablename__ = "team_invites"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    team_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="member")
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}",
    )

    __table_args__ = (
        CheckConstraint("role IN ('member', 'admin')", name="ck_team_invites_role"),
        Index("ix_team_invites_expires_at", "expires_at"),
    )


class TeamKnowledgePost(Base):
    __tablename__ = "team_knowledge_posts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    team_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_uid: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_user_vocab_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    word_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('question', 'shared_word', 'note')",
            name="ck_team_knowledge_posts_type",
        ),
        CheckConstraint(
            "status IN ('active', 'deleted')",
            name="ck_team_knowledge_posts_status",
        ),
        Index(
            "ix_team_knowledge_posts_feed",
            "team_id",
            "status",
            text("created_at DESC"),
            text("id DESC"),
        ),
        Index("ix_team_knowledge_posts_author_uid", "author_uid"),
    )
