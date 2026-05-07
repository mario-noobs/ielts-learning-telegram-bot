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
from typing import Any

from sqlalchemy import func, select

from services.db import get_sync_session
from services.db.models import User
from services.repositories.firestore.user_repo import _get_db, _users_col

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


def _firestore_row(doc_id: str) -> dict | None:
    snap = _users_col().document(doc_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    return {f: data.get(f) for f in FIELDS}


def _postgres_row(doc_id: str) -> dict | None:
    with get_sync_session() as s:
        u = s.get(User, doc_id)
        if u is None:
            return None
        return {f: getattr(u, f) for f in FIELDS}


def _firestore_count() -> int:
    return sum(1 for _ in _users_col().stream())


def _postgres_count() -> int:
    with get_sync_session() as s:
        return s.execute(select(func.count()).select_from(User)).scalar_one()


def _firestore_ids() -> list[str]:
    return [snap.id for snap in _users_col().stream()]


def run(sample_size: int) -> int:
    _get_db()

    fs_count = _firestore_count()
    pg_count = _postgres_count()
    logger.info("firestore=%d postgres=%d", fs_count, pg_count)
    if fs_count != pg_count:
        logger.error("ROW COUNT MISMATCH (firestore=%d, postgres=%d)", fs_count, pg_count)
        return 1

    if fs_count == 0:
        logger.info("no rows to spot-check; verification passes vacuously")
        return 0

    ids = _firestore_ids()
    sample = random.sample(ids, min(sample_size, len(ids)))
    logger.info("spot-checking %d of %d rows", len(sample), len(ids))

    drifts = 0
    for doc_id in sample:
        fs = _firestore_row(doc_id)
        pg = _postgres_row(doc_id)
        if fs is None or pg is None:
            logger.error("MISSING ROW id=%s firestore=%s postgres=%s",
                         doc_id, fs is not None, pg is not None)
            drifts += 1
            continue
        for f in FIELDS:
            if _normalize(fs[f]) != _normalize(pg[f]):
                logger.error("DRIFT id=%s field=%s firestore=%r postgres=%r",
                             doc_id, f, fs[f], pg[f])
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
