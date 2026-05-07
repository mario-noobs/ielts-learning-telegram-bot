"""users baseline (M8.1)

Revision ID: 0001_users_baseline
Revises:
Create Date: 2026-05-07
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_users_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("username", sa.Text(), nullable=False, server_default=""),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("auth_uid", sa.Text(), nullable=True),
        sa.Column("group_id", sa.BigInteger(), nullable=True),
        sa.Column("target_band", sa.Float(), nullable=False, server_default="7.0"),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("daily_time", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_active", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_words", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_quizzes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("challenge_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exam_date", sa.Text(), nullable=True),
        sa.Column("weekly_goal_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        # M11 admin fields. team_id / org_id gain FK constraints in M11.1.
        sa.Column("role", sa.Text(), nullable=False, server_default="user"),
        sa.Column("plan", sa.Text(), nullable=False, server_default="free"),
        sa.Column("plan_expires_at", sa.Date(), nullable=True),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("org_id", sa.Text(), nullable=True),
        sa.Column("quota_override", sa.Integer(), nullable=True),
        sa.Column("last_active_date", sa.Date(), nullable=True),
        sa.Column("signup_cohort", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("auth_uid", name="uq_users_auth_uid"),
    )
    op.create_index("ix_users_role_plan", "users", ["role", "plan"], unique=False)
    op.create_index("ix_users_signup_cohort", "users", ["signup_cohort"], unique=False)
    op.create_index("ix_users_last_active_date", "users", ["last_active_date"], unique=False)
    op.create_index("ix_users_team_id", "users", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_team_id", table_name="users")
    op.drop_index("ix_users_last_active_date", table_name="users")
    op.drop_index("ix_users_signup_cohort", table_name="users")
    op.drop_index("ix_users_role_plan", table_name="users")
    op.drop_table("users")
