"""User-vocabulary, topics, and review-events models (M8 cutover).

Schema lives in ``migrations/versions/0006_full_firestore_cutover.py``.
The model classes below mirror that schema 1-1 so SQLAlchemy queries
type-check against the table and Alembic ``--autogenerate`` recognises
them as no-ops.

Naming note: ``user_vocabulary`` is *state*, not canonical-vocabulary.
Each row is one user's saved card. Future schemas may split a separate
``vocabulary_master`` table; the rename to ``user_vocabulary`` reserves
that path.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.db.base import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    name_vi: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class UserVocabulary(Base):
    __tablename__ = "user_vocabulary"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    word: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_word: Mapped[str] = mapped_column(Text, nullable=False)
    topic_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("topics.id"), nullable=False,
    )
    definition_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    definition_vi: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ipa: Mapped[str] = mapped_column(Text, nullable=False, default="")
    part_of_speech: Mapped[str] = mapped_column(Text, nullable=False, default="")
    example_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    example_vi: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 1=daily, 2=quiz, 3=manual, 4=reading, 5=public_pool
    source: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    # SRS state — in-place updates
    srs_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    srs_ease: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    srs_reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    srs_next_review: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    is_favourite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))

    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    topic: Mapped[Topic] = relationship("Topic", lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "normalized_word", name="uq_user_vocab_normalized"),
        CheckConstraint("source BETWEEN 1 AND 5", name="ck_user_vocabulary_source"),
        # Partial indexes (match 0006 migration)
        Index(
            "ix_user_vocabulary_due",
            "user_id", "srs_next_review",
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index(
            "ix_user_vocabulary_topic",
            "user_id", "topic_id",
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index(
            "ix_user_vocabulary_favourite",
            "user_id",
            postgresql_where=text("is_favourite = TRUE AND archived_at IS NULL"),
        ),
    )


class VocabularyMaster(Base):
    """Canonical vocabulary content shared across users.

    ``user_vocabulary`` remains per-user SRS state. This table is the
    reproducible source pool that daily generation can select from before
    falling back to AI-generated candidates.
    """

    __tablename__ = "vocabulary_master"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    word: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_word: Mapped[str] = mapped_column(Text, nullable=False)
    part_of_speech: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    cefr_level: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topic_id: Mapped[Optional[int]] = mapped_column(
        SmallInteger, ForeignKey("topics.id"), nullable=True,
    )
    source_theme: Mapped[str] = mapped_column(Text, nullable=False, default="")
    definition_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    definition_vi: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ipa: Mapped[str] = mapped_column(Text, nullable=False, default="")
    example_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    example_vi: Mapped[str] = mapped_column(Text, nullable=False, default="")
    synonyms: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"),
    )
    antonyms: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"),
    )
    collocations: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"),
    )
    word_family: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"),
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    license: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="candidate")
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    topic: Mapped[Optional[Topic]] = relationship("Topic", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "normalized_word", name="uq_vocabulary_master_normalized_word",
        ),
        UniqueConstraint("source", "source_ref", name="uq_vocabulary_master_source_ref"),
        CheckConstraint(
            "difficulty IS NULL OR difficulty BETWEEN 1 AND 5",
            name="ck_vocabulary_master_difficulty",
        ),
        CheckConstraint(
            "status IN ('candidate', 'active', 'rejected')",
            name="ck_vocabulary_master_status",
        ),
        Index("ix_vocabulary_master_status", "status"),
        Index("ix_vocabulary_master_topic_status", "topic_id", "status"),
        Index("ix_vocabulary_master_source_theme", "source_theme"),
    )


class ReviewEvent(Base):
    """Append-only audit log of SRS reviews.

    Postgres RULEs (set up in 0006 migration) make UPDATE/DELETE no-ops
    even at the SQL level, so app code can't accidentally mutate the log.
    """

    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # No FK to users.id: audit log persists past user deletion, and the
    # DO-INSTEAD-NOTHING rules collide with cascade-delete RI checks.
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_vocab_id: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0..5 SM-2 grade
    source: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1=review, 2=quiz, …
    srs_interval_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    srs_interval_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint("result BETWEEN 0 AND 5", name="ck_review_events_result"),
        CheckConstraint("source BETWEEN 1 AND 4", name="ck_review_events_source"),
        Index(
            "ix_review_events_user_id_created_at",
            "user_id", text("created_at DESC"),
        ),
        Index(
            "ix_review_events_user_vocab_id_created_at",
            "user_vocab_id", text("created_at DESC"),
        ),
    )


__all__ = ["Topic", "UserVocabulary", "VocabularyMaster", "ReviewEvent"]
