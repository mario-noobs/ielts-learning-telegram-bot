"""Static content + system + auth-token models (M8 cutover Block E+F).

- ReadingQuestion: AI-generated question set per passage (low write).
- EnrichedWord: shared word metadata cache (Wikipedia/dictionary).
- FeatureFlag: admin-config rollouts.
- AuthLinkCode: ephemeral DM↔web linking codes (TTL'd by cron).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class ReadingQuestion(Base):
    """Per-passage cached AI-generated question set (US-M9.3)."""

    __tablename__ = "reading_questions"

    passage_id: Mapped[str] = mapped_column(Text, primary_key=True)
    # Client-safe questions list (no answer key inline).
    questions_client: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    # Server-side answer key with explanations. NEVER serialize to client.
    answer_key: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )


class EnrichedWord(Base):
    """Shared word metadata cache (Wikipedia / dictionary lookup)."""

    __tablename__ = "enriched_words"

    word: Mapped[str] = mapped_column(Text, primary_key=True)
    ipa: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    part_of_speech: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    definition_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    definition_vi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    syllable_stress: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ielts_tip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    examples_by_band: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True,
    )
    collocations: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    word_family: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )


class FeatureFlag(Base):
    """Admin-config rollout flag with allowlist + percent rollout."""

    __tablename__ = "feature_flags"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kill_switch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollout_pct: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0,
    )
    uid_allowlist: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default=text("ARRAY[]::text[]"),
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "rollout_pct BETWEEN 0 AND 100", name="ck_feature_flags_rollout_pct",
        ),
    )


class AuthLinkCode(Base):
    """Ephemeral DM↔web link code. Cleaned by ``scripts/cleanup_expired.py``."""

    __tablename__ = "auth_link_codes"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        Index("ix_auth_link_codes_expires_at", "expires_at"),
    )


__all__ = ["AuthLinkCode", "EnrichedWord", "FeatureFlag", "ReadingQuestion"]
