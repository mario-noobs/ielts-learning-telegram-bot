"""Team knowledge discussions.

Revision ID: 0017_team_knowledge_discussions
Revises: 0016_team_knowledge_posts
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_team_knowledge_discussions"
down_revision: Union[str, None] = "0016_team_knowledge_posts"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "team_knowledge_replies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("post_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("author_uid", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'deleted')",
            name="ck_team_knowledge_replies_status",
        ),
        sa.ForeignKeyConstraint(["post_id"], ["team_knowledge_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_team_knowledge_replies_author_uid",
        "team_knowledge_replies",
        ["author_uid"],
    )
    op.create_index(
        "ix_team_knowledge_replies_post",
        "team_knowledge_replies",
        ["post_id", "status", "created_at", "id"],
    )
    op.create_index(
        "ix_team_knowledge_replies_team_created",
        "team_knowledge_replies",
        ["team_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "team_knowledge_reactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_uid", sa.Text(), nullable=False),
        sa.Column("reaction", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "reaction IN ('helpful')",
            name="ck_team_knowledge_reactions_reaction",
        ),
        sa.CheckConstraint(
            "target_type IN ('post', 'reply')",
            name="ck_team_knowledge_reactions_target_type",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "target_type",
            "target_id",
            "user_uid",
            "reaction",
            name="uq_team_knowledge_reactions_user_target",
        ),
    )
    op.create_index(
        "ix_team_knowledge_reactions_target",
        "team_knowledge_reactions",
        ["target_type", "target_id", "reaction"],
    )
    op.create_index(
        "ix_team_knowledge_reactions_team_created",
        "team_knowledge_reactions",
        ["team_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_team_knowledge_reactions_team_created", table_name="team_knowledge_reactions")
    op.drop_index("ix_team_knowledge_reactions_target", table_name="team_knowledge_reactions")
    op.drop_table("team_knowledge_reactions")
    op.drop_index("ix_team_knowledge_replies_team_created", table_name="team_knowledge_replies")
    op.drop_index("ix_team_knowledge_replies_post", table_name="team_knowledge_replies")
    op.drop_index("ix_team_knowledge_replies_author_uid", table_name="team_knowledge_replies")
    op.drop_table("team_knowledge_replies")
