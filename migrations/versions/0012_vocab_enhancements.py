"""vocab enhancements — image_url, synonyms, antonyms on enriched_words; is_favourite on user_vocabulary

Revision ID: 0012_vocab_enhancements
Revises: 0011_local_auth
Create Date: 2026-05-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0012_vocab_enhancements"
down_revision: Union[str, None] = "0011_local_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enriched_words", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("enriched_words", sa.Column("synonyms", JSONB(), nullable=True))
    op.add_column("enriched_words", sa.Column("antonyms", JSONB(), nullable=True))

    op.add_column(
        "user_vocabulary",
        sa.Column(
            "is_favourite",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "ix_user_vocabulary_favourite",
        "user_vocabulary",
        ["user_id"],
        postgresql_where=sa.text("is_favourite = TRUE AND archived_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_user_vocabulary_favourite", table_name="user_vocabulary")
    op.drop_column("user_vocabulary", "is_favourite")

    op.drop_column("enriched_words", "antonyms")
    op.drop_column("enriched_words", "synonyms")
    op.drop_column("enriched_words", "image_url")
