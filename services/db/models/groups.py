"""Bot-owned group state models (M8 cutover Block B).

Tables created by ``0006_full_firestore_cutover``:
- groups: per-group settings (band, daily/challenge times, topics, owner)
- group_members: explicit membership ledger (alternative to users.group_id)
- group_daily_words: per-group daily vocab set
- group_challenges: per-group quiz challenge (1/day)
- group_challenge_answers: per-user answers within a challenge

challenge_id is a deterministic UUIDv5 of (group_id, date) so callers
can compute it from (group_id, date_str) without a DB roundtrip — see
``services.repositories.postgres.group_challenges_repo.challenge_id_for``.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram chat_id
    default_band: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_time: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    challenge_time: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    challenge_question_count: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True,
    )
    word_count: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    owner_telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # M14 web-auth owner uid (NULL until creator runs /start in group)
    owner_uid: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # FIFO ring of last-N topics for rotation (US-#226), capped app-side.
    recent_topics: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False,
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        PrimaryKeyConstraint("group_id", "telegram_id", name="pk_group_members"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')", name="ck_group_members_role",
        ),
    )


class GroupDailyWords(Base):
    __tablename__ = "group_daily_words"

    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False,
    )
    date: Mapped[_date] = mapped_column(Date, nullable=False)
    words: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        PrimaryKeyConstraint("group_id", "date", name="pk_group_daily_words"),
    )


class GroupChallenge(Base):
    __tablename__ = "group_challenges"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # UUIDv5(group_id, date)
    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False,
    )
    date: Mapped[_date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    questions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    participants: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("group_id", "date", name="uq_group_challenges_per_day"),
        CheckConstraint(
            "status IN ('active', 'closed', 'cancelled')",
            name="ck_group_challenges_status",
        ),
    )


class GroupChallengeAnswer(Base):
    __tablename__ = "group_challenge_answers"

    challenge_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("group_challenges.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    # {"0": true, "1": false, ...} per-question correctness map
    responses: Mapped[dict[str, bool]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "challenge_id", "user_id", name="pk_group_challenge_answers",
        ),
    )


__all__ = [
    "Group",
    "GroupChallenge",
    "GroupChallengeAnswer",
    "GroupDailyWords",
    "GroupMember",
]
