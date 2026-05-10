"""Nightly rollup: review_events → daily_review_snapshots (M8 Block D #234).

Aggregates yesterday's review_events into per-user daily counters so
the dashboard reads a single row instead of scanning the event log.

Idempotent — re-running for the same date overwrites the snapshot.

Usage::

    python scripts/rollup_daily_review_snapshots.py [--date 2026-05-09]

Default rolls up *yesterday* (UTC).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text  # noqa: E402

from services.db import get_sync_session  # noqa: E402

logger = logging.getLogger("rollup_snapshots")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def rollup(target_date: _date) -> int:
    """Rebuild daily_review_snapshots row(s) for ``target_date``.

    Counts review_events created during the UTC day of target_date and
    upserts a per-user row. Idempotent — re-running overwrites.
    """
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    # Note: SQLAlchemy text() chokes on ``:name::type`` (PG cast next to
    # bindparam) — pass snapshot_date as a Python date so psycopg2 binds
    # it natively without an inline cast.
    sql = text("""
        INSERT INTO daily_review_snapshots
            (user_id, snapshot_date, reviews_done, reviews_correct,
             words_added, study_minutes, created_at)
        SELECT
            user_id,
            :snap_date AS snapshot_date,
            COUNT(*) AS reviews_done,
            COUNT(*) FILTER (WHERE result >= 3) AS reviews_correct,
            0 AS words_added,
            0 AS study_minutes,
            now()
        FROM review_events
        WHERE created_at >= :win_start AND created_at < :win_end
        GROUP BY user_id
        ON CONFLICT (user_id, snapshot_date) DO UPDATE SET
            reviews_done = EXCLUDED.reviews_done,
            reviews_correct = EXCLUDED.reviews_correct,
            created_at = now()
    """)
    with get_sync_session() as s, s.begin():
        result = s.execute(sql, {
            "snap_date": target_date,
            "win_start": start,
            "win_end": end,
        })
    return result.rowcount or 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "--date",
        type=str,
        default=None,
        help="ISO date to roll up (default: yesterday UTC)",
    )
    args = p.parse_args()

    if args.date:
        target = _date.fromisoformat(args.date)
    else:
        target = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    logger.info("rolling up review_events for %s", target.isoformat())
    n = rollup(target)
    logger.info("upserted %d daily_review_snapshots row(s)", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
