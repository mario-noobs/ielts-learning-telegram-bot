#!/usr/bin/env python3
"""Populate ``users.last_active_date`` + ``users.signup_cohort`` (US-M11.2).

M11.1 added these columns with no defaults; existing rows hydrated by
``scripts/backfill_users_to_postgres.py`` (M8.2) carry NULL until this
script computes the values from the timestamps already on the row:

- ``last_active_date := last_active::date`` (or ``created_at::date`` if
  ``last_active`` is NULL)
- ``signup_cohort := to_char(created_at, 'YYYY-MM')``

These are admin-dashboard inputs (DAU/MAU + signup-cohort retention,
M11.5). Empty-or-NULL fields just mean those users won't show up in
the metrics until the script runs.

Idempotent: rows that already have non-NULL values are left alone.

Usage:
    python scripts/backfill_admin_fields.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Project root on sys.path when run directly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text  # noqa: E402

from services.db import get_sync_session  # noqa: E402

logger = logging.getLogger("backfill_admin_fields")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Single SQL statement — Postgres computes both fields server-side.
# COALESCE on last_active so users who never logged in still get a date
# (their created_at). NULLIF guard on created_at -> if a row truly has
# no created_at, leave signup_cohort NULL rather than emit '0001-01'.
_BACKFILL_SQL = text("""
    UPDATE users
    SET
        last_active_date = COALESCE(last_active::date, created_at::date),
        signup_cohort    = to_char(created_at, 'YYYY-MM')
    WHERE
        (last_active_date IS NULL OR signup_cohort IS NULL)
        AND created_at IS NOT NULL
""")


def run() -> int:
    """Apply the backfill; return number of rows updated."""
    with get_sync_session() as s, s.begin():
        result = s.execute(_BACKFILL_SQL)
        updated = result.rowcount or 0
    logger.info("backfilled %d row(s)", updated)
    return updated


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
