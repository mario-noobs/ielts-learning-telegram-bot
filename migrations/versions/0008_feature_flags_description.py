"""feature_flags.description column (M8 Block E #234)

Revision ID: 0008_feature_flags_desc
Revises: 0007_users_recent_topics
Create Date: 2026-05-10

services.feature_flag_service.set_flag persists a free-form description
string used by /admin/flags. The original 0006 schema omitted the
column; this migration adds it so the Postgres feature-flag repo can
round-trip the field without dropping it on the floor.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_feature_flags_desc"
down_revision: Union[str, None] = "0007_users_recent_topics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feature_flags",
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("feature_flags", "description")
