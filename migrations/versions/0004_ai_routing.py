"""ai_routing_config + ai_provider_usage (US-#221)

Revision ID: 0004_ai_routing
Revises: 0003_link_tokens
Create Date: 2026-05-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_ai_routing"
down_revision: Union[str, None] = "0003_link_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default chains seeded on first run. Admin can edit per-row at any
# time; the chain JSONB is unbounded in shape so adding per-hop
# timeouts/temperature later won't need a migration.
DEFAULT_CHAINS = {
    # Free tier — cheap models with one Gemini fallback.
    "free": [
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "groq", "model": "gemma2-9b-it"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ],
    # Paid tiers — premium model first, cheap models on overflow.
    "personal_pro": [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ],
    "team_member": [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ],
    "org_member": [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ],
}


def upgrade() -> None:
    op.create_table(
        "ai_routing_config",
        sa.Column("plan", sa.Text(), primary_key=True),
        sa.Column(
            "chain", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "ai_provider_usage",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("provider", sa.Text(), primary_key=True),
        sa.Column("model", sa.Text(), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "error_count", sa.Integer(), nullable=False, server_default="0",
        ),
        sa.Column("last_call_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_ai_provider_usage_date", "ai_provider_usage", ["date"],
    )

    # Seed default chains. Idempotent via INSERT … ON CONFLICT DO NOTHING
    # so re-running upgrade after a partial roll-forward stays safe.
    bind = op.get_bind()
    for plan, chain in DEFAULT_CHAINS.items():
        bind.execute(
            sa.text(
                "INSERT INTO ai_routing_config (plan, chain, updated_at) "
                "VALUES (:plan, CAST(:chain AS JSONB), now()) "
                "ON CONFLICT (plan) DO NOTHING"
            ),
            {"plan": plan, "chain": _json_dumps(chain)},
        )


def downgrade() -> None:
    op.drop_index("ix_ai_provider_usage_date", table_name="ai_provider_usage")
    op.drop_table("ai_provider_usage")
    op.drop_table("ai_routing_config")


def _json_dumps(value) -> str:
    import json
    return json.dumps(value)
