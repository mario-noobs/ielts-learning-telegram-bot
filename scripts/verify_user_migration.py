"""Verify Firestore users/ ≡ Postgres users (US-M8.2).

Runs after ``scripts/backfill_users_to_postgres.py``. Two checks:

1. **Row count parity**: Firestore total == Postgres total.
2. **Spot check**: 50 random ids (or all, if fewer than 50) must match
   field-by-field between Firestore and Postgres.

Exits 0 on parity, 1 on any drift. Drift detail is logged so CI / a
human can see exactly which field on which row diverged.

Usage:
    python scripts/verify_user_migration.py [--sample-size N]
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path when this file is run directly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import func, select  # noqa: E402

from services.db import get_sync_session  # noqa: E402
from services.db.models import User  # noqa: E402
from services.repositories.firestore.user_repo import _get_db, _users_col  # noqa: E402

logger = logging.getLogger("verify_users")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Fields compared field-by-field. Must mirror the backfill mapping.
FIELDS: list[str] = [
    "name",
    "username",
    "email",
    "auth_uid",
    "group_id",
    "target_band",
    "topics",
    "daily_time",
    "timezone",
    "streak",
    "last_active",
    "total_words",
    "total_quizzes",
    "total_correct",
    "challenge_wins",
    "exam_date",
    "weekly_goal_minutes",
    "created_at",
]


def _normalize(v: Any) -> Any:
    """Return a comparable form of v for cross-store equality."""
    if isinstance(v, datetime):
        # Strip naive vs aware mismatch by normalizing to UTC instant.
        return v.astimezone(tz=None).isoformat() if v.tzinfo else v.isoformat()
    if isinstance(v, list):
        return list(v)
    return v


def _postgres_row(doc_id: str) -> dict | None:
    with get_sync_session() as s:
        u = s.get(User, doc_id)
        if u is None:
            return None
        return {f: getattr(u, f) for f in FIELDS}


def _postgres_count() -> int:
    with get_sync_session() as s:
        return s.execute(select(func.count()).select_from(User)).scalar_one()


def _load_firestore_winners() -> dict[str, dict]:
    """Stream Firestore users, apply the same dedup as the backfill, return
    {id: row_dict}. Used so verify compares the deduped set, not the raw set."""
    from scripts.backfill_users_to_postgres import (  # noqa: E402
        _dedupe_by_auth_uid,
        _firestore_doc_to_row,
    )

    rows = [_firestore_doc_to_row(snap) for snap in _users_col().stream()]
    winners, losers = _dedupe_by_auth_uid(rows)
    if losers:
        logger.info("verify: %d firestore row(s) considered duplicates and excluded",
                    len(losers))
    return {w["id"]: w for w in winners}


def run(sample_size: int) -> int:
    _get_db()

    fs_winners = _load_firestore_winners()
    fs_count = len(fs_winners)
    pg_count = _postgres_count()
    logger.info("firestore_winners=%d postgres=%d", fs_count, pg_count)
    if fs_count != pg_count:
        logger.error("ROW COUNT MISMATCH (firestore=%d, postgres=%d)", fs_count, pg_count)
        return 1

    if fs_count == 0:
        logger.info("no rows to spot-check; verification passes vacuously")
        return 0

    ids = list(fs_winners.keys())
    sample = random.sample(ids, min(sample_size, len(ids)))
    logger.info("spot-checking %d of %d rows", len(sample), len(ids))

    drifts = 0
    for doc_id in sample:
        fs_row = fs_winners.get(doc_id)
        pg_row = _postgres_row(doc_id)
        fs = {f: fs_row.get(f) for f in FIELDS} if fs_row else None
        if fs is None or pg_row is None:
            logger.error("MISSING ROW id=%s firestore=%s postgres=%s",
                         doc_id, fs is not None, pg_row is not None)
            drifts += 1
            continue
        for f in FIELDS:
            if _normalize(fs[f]) != _normalize(pg_row[f]):
                logger.error("DRIFT id=%s field=%s firestore=%r postgres=%r",
                             doc_id, f, fs[f], pg_row[f])
                drifts += 1

    if drifts:
        logger.error("verification FAILED: %d drift(s)", drifts)
        return 1
    logger.info("verification PASSED: row count + %d-row spot check clean", len(sample))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sample-size", type=int, default=50)
    args = p.parse_args()
    return run(sample_size=args.sample_size)


if __name__ == "__main__":
    sys.exit(main())
