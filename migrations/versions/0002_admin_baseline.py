"""admin baseline (M11.1)

Revision ID: 0002_admin_baseline
Revises: 0001_users_baseline
Create Date: 2026-05-07
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_admin_baseline"
down_revision: Union[str, None] = "0001_users_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PLAN_SEEDS = [
    {
        "id": "free",
        "name": "Free",
        "daily_ai_quota": 10,
        "monthly_ai_quota": 200,
        "max_team_seats": None,
        "features": [],
    },
    {
        "id": "personal_pro",
        "name": "Personal Pro",
        "daily_ai_quota": 200,
        "monthly_ai_quota": 5000,
        "max_team_seats": None,
        "features": ["unlimited_writing", "unlimited_listening", "adaptive_plan"],
    },
    {
        "id": "team_member",
        "name": "Team Member",
        "daily_ai_quota": 200,
        "monthly_ai_quota": 5000,
        "max_team_seats": 25,
        "features": ["unlimited_writing", "unlimited_listening", "adaptive_plan"],
    },
    {
        "id": "org_member",
        "name": "Org Member",
        "daily_ai_quota": 500,
        "monthly_ai_quota": 12000,
        "max_team_seats": 200,
        "features": ["unlimited_writing", "unlimited_listening", "adaptive_plan", "priority_support"],
    },
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    plans_table = op.create_table(
        "plans",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("daily_ai_quota", sa.Integer(), nullable=False),
        sa.Column("monthly_ai_quota", sa.Integer(), nullable=False),
        sa.Column("max_team_seats", sa.Integer(), nullable=True),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_plans"),
    )

    now = datetime.now(timezone.utc)
    op.bulk_insert(
        plans_table,
        [{**p, "created_at": now} for p in PLAN_SEEDS],
    )

    op.create_table(
        "teams",
        sa.Column(
            "id", postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_uid", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("plan_expires_at", sa.Date(), nullable=True),
        sa.Column("seat_limit", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_teams"),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name="fk_teams_plan_id_plans",
        ),
    )

    op.create_table(
        "team_members",
        sa.Column("team_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_uid", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("team_id", "user_uid", name="pk_team_members"),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"],
            name="fk_team_members_team_id_teams", ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "role IN ('member', 'admin')", name="ck_team_members_role",
        ),
    )
    op.create_index("ix_team_members_user_uid", "team_members", ["user_uid"])

    op.create_table(
        "orgs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_uid", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("plan_expires_at", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_orgs"),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name="fk_orgs_plan_id_plans",
        ),
    )

    op.create_table(
        "org_admins",
        sa.Column("org_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_uid", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("org_id", "user_uid", name="pk_org_admins"),
        sa.ForeignKeyConstraint(
            ["org_id"], ["orgs.id"],
            name="fk_org_admins_org_id_orgs", ondelete="CASCADE",
        ),
    )

    op.create_table(
        "org_teams",
        sa.Column("org_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.PrimaryKeyConstraint("org_id", "team_id", name="pk_org_teams"),
        sa.ForeignKeyConstraint(
            ["org_id"], ["orgs.id"],
            name="fk_org_teams_org_id_orgs", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"],
            name="fk_org_teams_team_id_teams", ondelete="CASCADE",
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_uid", sa.Text(), nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index(
        "ix_audit_log_actor_uid_created_at", "audit_log",
        ["actor_uid", "created_at"],
    )
    op.create_index(
        "ix_audit_log_target_kind_target_id_created_at", "audit_log",
        ["target_kind", "target_id", "created_at"],
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    op.create_table(
        "ai_usage",
        sa.Column("user_uid", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_call_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_uid", "date", "feature", name="pk_ai_usage"),
    )
    op.create_index("ix_ai_usage_date", "ai_usage", ["date"])

    op.create_table(
        "platform_metrics",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_users", sa.Integer(), nullable=False),
        sa.Column("dau", sa.Integer(), nullable=False),
        sa.Column("signups", sa.Integer(), nullable=False),
        sa.Column("ai_calls", sa.Integer(), nullable=False),
        sa.Column("plan_distribution", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default="{}"),
        sa.Column("errors_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("date", name="pk_platform_metrics"),
    )

    # users.team_id / org_id were declared as text in 0001 (pre-team/org).
    # Convert to uuid so the FKs to teams/orgs (uuid PK) resolve. All
    # existing values are NULL pre-launch, so the cast is a no-op.
    op.execute("DROP INDEX IF EXISTS ix_users_team_id")
    op.alter_column(
        "users", "team_id",
        type_=postgresql.UUID(as_uuid=False),
        postgresql_using="team_id::uuid",
        existing_nullable=True,
    )
    op.alter_column(
        "users", "org_id",
        type_=postgresql.UUID(as_uuid=False),
        postgresql_using="org_id::uuid",
        existing_nullable=True,
    )
    op.create_index("ix_users_team_id", "users", ["team_id"])

    # FKs from users.* — added LAST so referenced tables already exist and
    # existing users.plan='free' (default) resolves cleanly to the seed.
    op.create_foreign_key(
        "fk_users_plan_plans", "users", "plans", ["plan"], ["id"],
    )
    op.create_foreign_key(
        "fk_users_team_id_teams", "users", "teams", ["team_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_users_org_id_orgs", "users", "orgs", ["org_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_org_id_orgs", "users", type_="foreignkey")
    op.drop_constraint("fk_users_team_id_teams", "users", type_="foreignkey")
    op.drop_constraint("fk_users_plan_plans", "users", type_="foreignkey")

    op.drop_index("ix_users_team_id", table_name="users")
    op.alter_column(
        "users", "org_id", type_=sa.Text(),
        postgresql_using="org_id::text", existing_nullable=True,
    )
    op.alter_column(
        "users", "team_id", type_=sa.Text(),
        postgresql_using="team_id::text", existing_nullable=True,
    )
    op.create_index("ix_users_team_id", "users", ["team_id"])

    op.drop_table("platform_metrics")
    op.drop_index("ix_ai_usage_date", table_name="ai_usage")
    op.drop_table("ai_usage")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_target_kind_target_id_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_uid_created_at", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("org_teams")
    op.drop_table("org_admins")
    op.drop_table("orgs")
    op.drop_index("ix_team_members_user_uid", table_name="team_members")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_table("plans")
