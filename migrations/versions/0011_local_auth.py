"""local auth — email/password columns + refresh token + brute-force tables

Revision ID: 0011_local_auth
Revises: 0010_users_field_set
Create Date: 2026-05-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_local_auth"
down_revision: Union[str, None] = "0010_users_field_set"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("address", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "local_auth",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_index(
        "ix_users_email_local",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("local_auth = true"),
    )
    op.create_index(
        "ix_users_username_nonempty",
        "users",
        ["username"],
        unique=True,
        postgresql_where=sa.text("username != ''"),
    )

    op.create_table(
        "local_refresh_tokens",
        sa.Column("token_hash", sa.Text(), primary_key=True),
        sa.Column("user_email", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_local_refresh_tokens_user_expires",
        "local_refresh_tokens",
        ["user_email", "expires_at"],
    )

    op.create_table(
        "login_attempts",
        sa.Column(
            "id", sa.Integer(), primary_key=True, autoincrement=True,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_login_attempts_email_attempted_at",
        "login_attempts",
        ["email", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_login_attempts_email_attempted_at", table_name="login_attempts")
    op.drop_table("login_attempts")

    op.drop_index("ix_local_refresh_tokens_user_expires", table_name="local_refresh_tokens")
    op.drop_table("local_refresh_tokens")

    op.drop_index("ix_users_username_nonempty", table_name="users")
    op.drop_index("ix_users_email_local", table_name="users")

    op.drop_column("users", "local_auth")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "address")
    op.drop_column("users", "phone")
    op.drop_column("users", "password_hash")
