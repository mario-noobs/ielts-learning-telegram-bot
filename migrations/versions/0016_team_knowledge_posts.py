"""Team knowledge feed posts.

Revision ID: 0016_team_knowledge_posts
Revises: 0015_team_invites
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_team_knowledge_posts"
down_revision: Union[str, None] = "0015_team_invites"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "team_knowledge_posts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("author_uid", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("source_user_vocab_id", sa.Text(), nullable=True),
        sa.Column(
            "word_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'deleted')",
            name="ck_team_knowledge_posts_status",
        ),
        sa.CheckConstraint(
            "type IN ('question', 'shared_word', 'note')",
            name="ck_team_knowledge_posts_type",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_team_knowledge_posts_author_uid",
        "team_knowledge_posts",
        ["author_uid"],
    )
    op.create_index(
        "ix_team_knowledge_posts_feed",
        "team_knowledge_posts",
        ["team_id", "status", sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_team_knowledge_posts_feed", table_name="team_knowledge_posts")
    op.drop_index("ix_team_knowledge_posts_author_uid", table_name="team_knowledge_posts")
    op.drop_table("team_knowledge_posts")
