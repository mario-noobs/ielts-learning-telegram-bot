"""team invites

Revision ID: 0015_team_invites
Revises: 0014_public_pool_vocab_source
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_team_invites"
down_revision: Union[str, None] = "0014_public_pool_vocab_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_invites",
        sa.Column(
            "id", postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json", postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default="{}",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_team_invites"),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"],
            name="fk_team_invites_team_id_teams", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name="uq_team_invites_token_hash"),
        sa.CheckConstraint(
            "role IN ('member', 'admin')", name="ck_team_invites_role",
        ),
    )
    op.create_index("ix_team_invites_team_id", "team_invites", ["team_id"])
    op.create_index("ix_team_invites_expires_at", "team_invites", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_team_invites_expires_at", table_name="team_invites")
    op.drop_index("ix_team_invites_team_id", table_name="team_invites")
    op.drop_table("team_invites")
