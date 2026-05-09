"""ai_routing chains v2 — tag premium hops, drop gemma2-9b-it (US-#221)

Revision ID: 0005_ai_routing_fix
Revises: 0004_ai_routing
Create Date: 2026-05-09

Two fixes after Phase-1 prod deploy hit issues:

  1. Router logic relied on chain *position* to decide cheap vs premium
     ("cheap = skip hop 0"). That broke for the Free chain where
     hop 0 *is* the cheap model — Free users skipped to hop 1
     (`gemma2-9b-it`) and 400'd. Fix is in
     `services/ai/router.py::_eligible_hops`: each hop carries an
     optional `tier` tag now. This migration adds `tier="premium"` to
     hop 0 of every paid plan so the new logic kicks in without a
     code-only change.

  2. `gemma2-9b-it` returned 400 from Groq's API in production. Drop
     it from the chains rather than leaving a dead hop.

Idempotent: re-running the upgrade is safe because the UPDATE
overwrites with the v2 chain wholesale.
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ai_routing_fix"
down_revision: Union[str, None] = "0004_ai_routing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CHAINS_V2 = {
    "free": [
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ],
    "personal_pro": [
        {"provider": "groq", "model": "llama-3.3-70b-versatile", "tier": "premium"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ],
    "team_member": [
        {"provider": "groq", "model": "llama-3.3-70b-versatile", "tier": "premium"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ],
    "org_member": [
        {"provider": "groq", "model": "llama-3.3-70b-versatile", "tier": "premium"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ],
}


CHAINS_V1 = {
    "free": [
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "groq", "model": "gemma2-9b-it"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ],
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


def _set_chain(plan: str, chain: list) -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO ai_routing_config (plan, chain, updated_at) "
            "VALUES (:plan, CAST(:chain AS JSONB), now()) "
            "ON CONFLICT (plan) DO UPDATE "
            "SET chain = EXCLUDED.chain, updated_at = now()"
        ),
        {"plan": plan, "chain": json.dumps(chain)},
    )


def upgrade() -> None:
    for plan, chain in CHAINS_V2.items():
        _set_chain(plan, chain)


def downgrade() -> None:
    for plan, chain in CHAINS_V1.items():
        _set_chain(plan, chain)
