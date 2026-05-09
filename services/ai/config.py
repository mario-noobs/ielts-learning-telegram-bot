"""Routing config loader (US-#221).

Reads `ai_routing_config` from Postgres with a 60s in-memory cache —
identical pattern to `feature_flag_service`. Admin updates the row
(`scripts/ai_routing.py` CLI or raw SQL in Phase 1; admin UI in
Phase 2) and the router picks up the change within one TTL window.

If Postgres is unreachable (or the table doesn't exist yet — fresh
dev environment without migrations), we degrade to hardcoded defaults
so the bot path keeps working.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import config as app_config
from services.db import get_sync_session
from services.db.models import AiRoutingConfig

logger = logging.getLogger(__name__)

# Hardcoded defaults — mirror migration 0004's seed values. Used when:
#   - The table doesn't exist (fresh dev env, no migrations applied).
#   - Postgres is unreachable.
#   - A plan name we don't have a row for shows up (defensive).
DEFAULT_CHAINS: dict[str, list[dict]] = {
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


_cache: dict[str, list[dict]] = {}
_cache_loaded_at: float = 0.0


def _refresh_cache() -> None:
    """Read every row from `ai_routing_config` into the in-memory map."""
    global _cache, _cache_loaded_at
    try:
        with get_sync_session() as s:
            rows = s.query(AiRoutingConfig).all()
            _cache = {r.plan: list(r.chain) for r in rows}
            _cache_loaded_at = time.monotonic()
    except Exception:  # noqa: BLE001
        # Postgres unreachable / table missing — log once per process,
        # serve defaults until the table comes up.
        if _cache_loaded_at == 0.0:
            logger.warning(
                "ai_routing: PG unreachable, falling back to hardcoded chains",
                exc_info=True,
            )
        _cache = dict(DEFAULT_CHAINS)
        _cache_loaded_at = time.monotonic()


def _get_cache() -> dict[str, list[dict]]:
    now = time.monotonic()
    ttl = app_config.AI_ROUTING_CACHE_TTL_SECONDS
    if not _cache or (now - _cache_loaded_at) >= ttl:
        _refresh_cache()
    return _cache


def get_chain(plan: Optional[str]) -> list[dict]:
    """Return the ordered `[{provider, model}, …]` chain for `plan`.

    Falls back to the `free` chain when:
      - plan is None / unknown — defensive for half-migrated rows
      - the row was deleted by an admin who didn't know what they were doing
    """
    plan_key = plan or "free"
    cache = _get_cache()
    if plan_key in cache:
        return cache[plan_key]
    if plan_key in DEFAULT_CHAINS:
        return DEFAULT_CHAINS[plan_key]
    # Last-resort: route unknown plans through the free chain rather
    # than blowing up. The router will at least try *something*.
    return DEFAULT_CHAINS["free"]


def invalidate_cache() -> None:
    """Force the next get_chain() call to re-read from Postgres.

    Called by the admin update path (Phase 2 admin UI / scripts/ai_routing).
    """
    global _cache_loaded_at
    _cache_loaded_at = 0.0
