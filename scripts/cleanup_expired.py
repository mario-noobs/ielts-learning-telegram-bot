"""Nightly TTL cleanup for ephemeral PG tables (M8 Block C #234).

Deletes rows that exceeded their natural lifespan:
- quiz_sessions, reading_sessions: anything older than 7 days.
- auth_link_codes: anything where ``expires_at < now()``.

Designed for daily APScheduler invocation. Idempotent — re-running
within the same day is a no-op for already-cleaned rows.

Usage::

    python scripts/cleanup_expired.py [--days 7]
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import delete, text  # noqa: E402

from services.db import get_sync_session  # noqa: E402
from services.repositories import (  # noqa: E402
    get_quiz_sessions_repo,
    get_reading_sessions_repo,
)

logger = logging.getLogger("cleanup_expired")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def cleanup_auth_link_codes() -> int:
    """Delete auth_link_codes rows whose expires_at is in the past."""
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        result = s.execute(
            text("DELETE FROM auth_link_codes WHERE expires_at < :now"),
            {"now": now},
        )
    return result.rowcount or 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "--days",
        type=int,
        default=7,
        help="TTL in days for session tables (default 7)",
    )
    args = p.parse_args()

    qs = get_quiz_sessions_repo().cleanup_older_than(days=args.days)
    rs = get_reading_sessions_repo().cleanup_older_than(days=args.days)
    lc = cleanup_auth_link_codes()
    logger.info(
        "deleted: quiz_sessions=%d, reading_sessions=%d, auth_link_codes=%d",
        qs, rs, lc,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
