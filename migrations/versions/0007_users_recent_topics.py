"""users.recent_personal_topics column (M8 cutover hotfix #234)

Revision ID: 0007_users_recent_topics
Revises: 0006_full_firestore_cutover
Create Date: 2026-05-10

vocab_service.generate_personal_daily_words persists the per-user FIFO
ring of last-N personal topics (US-#226 rotation logic). Firestore
tolerated the field via schema-loose docs; Postgres needs an explicit
column. No Firestore data has the field populated yet, so the default
``'[]'`` is correct for every existing row.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_users_recent_topics"
down_revision: Union[str, None] = "0006_full_firestore_cutover"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "recent_personal_topics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "recent_personal_topics")
