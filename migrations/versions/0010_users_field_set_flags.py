"""users.target_band_set + users.weekly_goal_set flags (#dashboard-polish)

Revision ID: 0010_users_field_set
Revises: 0009_users_daily_words_onboard
Create Date: 2026-05-10

target_band has a non-null default of 7.0 and weekly_goal_minutes has
a UI default of 150 — both unclearable. The dashboard <ReadinessTrack>
sub-tasks need to distinguish "user explicitly configured this" from
"the row defaulted on signup". A pair of boolean flags is the
lightest-touch signal: PATCH /me stamps them on save, the readiness
service reads them to decide ✓ vs ○. No schema migration of the
underlying value fields, no impact on the eight call sites that read
``user.get("target_band", 7.0)``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_users_field_set"
down_revision: Union[str, None] = "0009_users_daily_words_onboard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "target_band_set",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "weekly_goal_set",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "weekly_goal_set")
    op.drop_column("users", "target_band_set")
