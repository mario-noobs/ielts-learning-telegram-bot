"""allow public pool user vocabulary source

Revision ID: 0014_public_pool_vocab_source
Revises: 0013_vocabulary_master
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0014_public_pool_vocab_source"
down_revision: Union[str, None] = "0013_vocabulary_master"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_user_vocabulary_source",
        "user_vocabulary",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_vocabulary_source",
        "user_vocabulary",
        "source BETWEEN 1 AND 5",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_vocabulary_source",
        "user_vocabulary",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_vocabulary_source",
        "user_vocabulary",
        "source BETWEEN 1 AND 4",
    )
