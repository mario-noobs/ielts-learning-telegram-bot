"""link_tokens (US-M12.2)

Revision ID: 0003_link_tokens
Revises: 0002_admin_baseline
Create Date: 2026-05-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_link_tokens"
down_revision: Union[str, None] = "0002_admin_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "link_tokens",
        sa.Column("token", sa.Text(), primary_key=True),
        # 'tg_to_web' or 'web_to_tg' — direction of the deep-link.
        sa.Column("direction", sa.Text(), nullable=False),
        # Set when direction='tg_to_web' (the originating telegram user).
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        # Set when direction='web_to_tg' (the originating Firebase Auth user).
        sa.Column("auth_uid", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # NULL = available; non-NULL = single-use already redeemed.
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        # User id of the redeemer (telegram_id or web_xxx) for audit.
        sa.Column("redeemed_by", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "direction IN ('tg_to_web', 'web_to_tg')",
            name="ck_link_tokens_direction",
        ),
    )
    # Partial index: cleanup cron scans only un-redeemed tokens, and the
    # token redemption read path (`get + check expires_at`) benefits when
    # the active set stays small.
    op.create_index(
        "ix_link_tokens_expires_at_unredeemed",
        "link_tokens",
        ["expires_at"],
        postgresql_where=sa.text("redeemed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_link_tokens_expires_at_unredeemed", table_name="link_tokens")
    op.drop_table("link_tokens")
