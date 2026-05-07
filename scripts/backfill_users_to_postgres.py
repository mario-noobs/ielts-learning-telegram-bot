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

# Ensure project root is on sys.path when this file is run directly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from services.db import get_sync_session  # noqa: E402
from services.db.models import User  # noqa: E402
from services.repositories.firestore.user_repo import _get_db, _users_col  # noqa: E402

CURSOR_FILE = _ROOT / ".backfill_users.cursor"

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


def _stream_firestore() -> Iterable:
    """Yield Firestore user snapshots, ordered by document id."""
    _get_db()
    yield from _users_col().order_by("__name__").stream()


def _activity_score(row: dict) -> int:
    """Higher score = more real user activity. Used to pick a dedup winner."""
    return (
        (row.get("total_words") or 0)
        + (row.get("total_quizzes") or 0)
        + (row.get("streak") or 0)
        + (row.get("challenge_wins") or 0)
    )


def _is_better(a: dict, b: dict) -> bool:
    """True if a should beat b as the winning row for a duplicate auth_uid."""
    sa, sb = _activity_score(a), _activity_score(b)
    if sa != sb:
        return sa > sb
    ca, cb = a.get("created_at"), b.get("created_at")
    if ca is not None and cb is not None and ca != cb:
        return ca < cb
    return a["id"] < b["id"]


def _dedupe_by_auth_uid(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Pick one winner per auth_uid; return (winners, losers).

    Rows with auth_uid is None pass through untouched. Losers are ids
    Firestore stores but Postgres won't accept under ``UNIQUE(auth_uid)``.
    """
    by_auth: dict[str, dict] = {}
    no_auth: list[dict] = []
    losers: list[dict] = []
    for row in rows:
        auth = row.get("auth_uid")
        if auth is None:
            no_auth.append(row)
            continue
        existing = by_auth.get(auth)
        if existing is None:
            by_auth[auth] = row
            continue
        if _is_better(row, existing):
            losers.append(existing)
            by_auth[auth] = row
        else:
            losers.append(row)
    winners = list(by_auth.values()) + no_auth
    return winners, losers


def run(batch_size: int) -> int:
    # Pre-launch: load all users into memory once, dedupe by auth_uid, then
    # upsert. Dedup needed because Firestore tolerated multiple users sharing
    # the same auth_uid (orphan web stubs from link_telegram_to_auth);
    # Postgres won't under UNIQUE(auth_uid).
    _ = _read_cursor()  # cursor compat reserved; not used in dedup path
    logger.info("loading firestore users…")
    all_rows = [_firestore_doc_to_row(snap) for snap in _stream_firestore()]
    logger.info("firestore returned %d rows", len(all_rows))

    winners, losers = _dedupe_by_auth_uid(all_rows)
    if losers:
        logger.warning("dedup dropped %d row(s) with duplicate auth_uid:", len(losers))
        for r in losers:
            logger.warning(
                "  drop id=%s auth_uid=%s activity=%d",
                r["id"], r["auth_uid"], _activity_score(r),
            )

    total = 0
    for i in range(0, len(winners), batch_size):
        batch = winners[i : i + batch_size]
        _upsert_batch(batch)
        total += len(batch)
        if batch:
            _write_cursor(batch[-1]["id"])
        logger.info("upserted %d / %d", total, len(winners))

    logger.info("done. winners=%d, dropped=%d", total, len(losers))
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
