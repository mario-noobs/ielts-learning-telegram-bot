"""add vocabulary master source table

Revision ID: 0013_vocabulary_master
Revises: 0012_vocab_enhancements
Create Date: 2026-05-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0013_vocabulary_master"
down_revision: Union[str, None] = "0012_vocab_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vocabulary_master",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("word", sa.Text(), nullable=False),
        sa.Column("normalized_word", sa.Text(), nullable=False),
        sa.Column("part_of_speech", sa.Text(), nullable=False, server_default=""),
        sa.Column("difficulty", sa.SmallInteger(), nullable=True),
        sa.Column("cefr_level", sa.Text(), nullable=True),
        sa.Column("topic_id", sa.SmallInteger(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("source_theme", sa.Text(), nullable=False, server_default=""),
        sa.Column("definition_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("definition_vi", sa.Text(), nullable=False, server_default=""),
        sa.Column("ipa", sa.Text(), nullable=False, server_default=""),
        sa.Column("example_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("example_vi", sa.Text(), nullable=False, server_default=""),
        sa.Column("synonyms", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("antonyms", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "collocations",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("word_family", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("license", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Text(), nullable=False, server_default="candidate"),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "normalized_word",
            name="uq_vocabulary_master_normalized_word",
        ),
        sa.UniqueConstraint("source", "source_ref", name="uq_vocabulary_master_source_ref"),
        sa.CheckConstraint(
            "difficulty IS NULL OR difficulty BETWEEN 1 AND 5",
            name="ck_vocabulary_master_difficulty",
        ),
        sa.CheckConstraint(
            "status IN ('candidate', 'active', 'rejected')",
            name="ck_vocabulary_master_status",
        ),
    )
    op.create_index("ix_vocabulary_master_status", "vocabulary_master", ["status"])
    op.create_index(
        "ix_vocabulary_master_topic_status",
        "vocabulary_master",
        ["topic_id", "status"],
    )
    op.create_index(
        "ix_vocabulary_master_source_theme",
        "vocabulary_master",
        ["source_theme"],
    )
    op.execute(
        "CREATE TRIGGER trg_vocabulary_master_updated_at "
        "BEFORE UPDATE ON vocabulary_master "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_vocabulary_master_updated_at ON vocabulary_master")
    op.drop_index("ix_vocabulary_master_source_theme", table_name="vocabulary_master")
    op.drop_index("ix_vocabulary_master_topic_status", table_name="vocabulary_master")
    op.drop_index("ix_vocabulary_master_status", table_name="vocabulary_master")
    op.drop_table("vocabulary_master")
