"""One-shot Firestore users/ → Postgres backfill (US-M8.2).

Idempotent + resumable. Re-runs leave the table identical. The backfill
walks Firestore users/ in deterministic id order, batches them into
Postgres ``INSERT ... ON CONFLICT (id) DO UPDATE`` statements, and
checkpoints the last completed id to ``.backfill_users.cursor`` so an
interrupted run can be resumed.

Per ADR-M8-3 (revised): pre-launch one-shot. Run this once, run
``scripts/verify_user_migration.py``, then ship the cutover PR.

Usage:
    python scripts/backfill_users_to_postgres.py [--batch-size N]
                                                  [--reset-cursor]

The script reads ``DATABASE_URL`` from the environment (same as the
app). Firestore credentials follow the standard
``services.firebase_service`` resolution: emulator if
``FIRESTORE_EMULATOR_HOST`` is set, otherwise
``FIREBASE_CREDENTIALS_PATH`` / ``FIREBASE_CREDENTIALS_JSON``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.db import get_sync_session
from services.db.models import User
from services.repositories.firestore.user_repo import _get_db, _users_col

CURSOR_FILE = Path(__file__).resolve().parent.parent / ".backfill_users.cursor"

logger = logging.getLogger("backfill_users")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _read_cursor() -> str | None:
    if not CURSOR_FILE.exists():
        return None
    val = CURSOR_FILE.read_text().strip()
    return val or None


def _write_cursor(last_id: str) -> None:
    CURSOR_FILE.write_text(last_id)


def _clear_cursor() -> None:
    if CURSOR_FILE.exists():
        CURSOR_FILE.unlink()


def _firestore_doc_to_row(doc) -> dict:
    """Map a Firestore users/{id} doc to a row dict for Postgres upsert."""
    data = doc.to_dict() or {}
    # Convert Firestore timestamps to plain datetimes (already datetime
    # subclasses, but assert tz-awareness for Postgres timestamptz).
    last_active = data.get("last_active")
    if isinstance(last_active, datetime) and last_active.tzinfo is None:
        last_active = None
    created_at = data.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = None
    return {
        "id": doc.id,
        "name": data.get("name", "") or "",
        "username": data.get("username", "") or "",
        "email": data.get("email"),
        "auth_uid": data.get("auth_uid"),
        "group_id": data.get("group_id"),
        "target_band": float(data.get("target_band", 7.0)),
        "topics": list(data.get("topics") or []),
        "daily_time": data.get("daily_time"),
        "timezone": data.get("timezone"),
        "streak": int(data.get("streak", 0) or 0),
        "last_active": last_active,
        "total_words": int(data.get("total_words", 0) or 0),
        "total_quizzes": int(data.get("total_quizzes", 0) or 0),
        "total_correct": int(data.get("total_correct", 0) or 0),
        "challenge_wins": int(data.get("challenge_wins", 0) or 0),
        "exam_date": data.get("exam_date"),
        "weekly_goal_minutes": data.get("weekly_goal_minutes"),
        "created_at": created_at,
    }


def _upsert_batch(rows: list[dict]) -> None:
    """Atomic upsert of one batch into Postgres."""
    if not rows:
        return
    stmt = pg_insert(User).values(rows)
    update_cols = {c.name: c for c in stmt.excluded if c.name != "id"}
    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
    with get_sync_session() as s, s.begin():
        s.execute(stmt)


def _stream_firestore(start_after: str | None) -> Iterable[tuple[str, dict]]:
    """Yield (doc_id, doc_dict) ordered by document id, optionally
    skipping ids ≤ ``start_after`` for resume."""
    _get_db()  # ensure firebase initialized
    query = _users_col().order_by("__name__")
    if start_after is not None:
        query = query.start_after({"__name__": start_after})
    for snap in query.stream():
        yield snap.id, snap


def run(batch_size: int) -> int:
    cursor = _read_cursor()
    if cursor:
        logger.info("resuming after id=%s", cursor)
    else:
        logger.info("starting fresh backfill")

    batch: list[dict] = []
    total = 0
    last_id: str | None = cursor

    for doc_id, snap in _stream_firestore(start_after=cursor):
        batch.append(_firestore_doc_to_row(snap))
        last_id = doc_id
        if len(batch) >= batch_size:
            _upsert_batch(batch)
            total += len(batch)
            _write_cursor(last_id)
            logger.info("upserted %d (cursor=%s)", total, last_id)
            batch = []

    if batch:
        _upsert_batch(batch)
        total += len(batch)
        if last_id is not None:
            _write_cursor(last_id)
        logger.info("upserted %d (cursor=%s)", total, last_id)

    logger.info("done. total upserted: %d", total)
    return total


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument(
        "--reset-cursor",
        action="store_true",
        help="Delete the resume checkpoint and start from the beginning.",
    )
    args = p.parse_args()
    if args.reset_cursor:
        _clear_cursor()
        logger.info("cursor cleared")
    run(batch_size=args.batch_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
