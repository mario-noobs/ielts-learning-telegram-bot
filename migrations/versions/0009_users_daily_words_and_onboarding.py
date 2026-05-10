"""users.daily_words_count + users.dismissed_onboarding (#242)

Revision ID: 0009_users_daily_words_onboard
Revises: 0008_feature_flags_desc
Create Date: 2026-05-10

US #242 surfaces two per-user settings that previously had no home:
- ``daily_words_count`` — how many new words the personal daily flow
  generates. Used by ``bot.handlers.vocabulary.mydaily_command``.
  Hardcoded to ``config.DEFAULT_WORD_COUNT`` before this migration.
- ``dismissed_onboarding`` — gates the first-login quick-tour dialog
  on the web app.

CHECK keeps the range honest at the DB layer (5..50 spans the dropdown
choices 5/10/20/30/50). The API still validates with a domain-specific
error code so the UI can localize.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_users_daily_words_onboard"
down_revision: Union[str, None] = "0008_feature_flags_desc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "daily_words_count",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
    )
    op.create_check_constraint(
        "ck_users_daily_words_count_range",
        "users",
        "daily_words_count BETWEEN 5 AND 50",
    )
    op.add_column(
        "users",
        sa.Column(
            "dismissed_onboarding",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_daily_words_count_range", "users", type_="check",
    )
    op.drop_column("users", "dismissed_onboarding")
    op.drop_column("users", "daily_words_count")
