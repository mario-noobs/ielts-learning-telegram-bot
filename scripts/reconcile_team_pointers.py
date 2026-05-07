#!/usr/bin/env python3
"""Rebuild Firestore ``users.team_id`` pointers from the Postgres
``team_members`` table (US-M11.4).

Postgres is the source of truth for team membership. ``users.team_id``
in Firestore is a denormalized hot-path pointer — the M11.3+ admin
routes write it second, after the Postgres mutation succeeds. If
those writes ever drift (network blip, dead host, or a bulk Postgres
seed that bypassed the admin routes), this script rebuilds Firestore
pointers from Postgres in one pass.

Idempotent. Safe to re-run any time.

Usage:
    python scripts/reconcile_team_pointers.py [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Project root on sys.path when run directly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select  # noqa: E402

from services.db import get_sync_session  # noqa: E402
from services.db.models import TeamMember  # noqa: E402
from services.repositories.firestore.user_repo import _get_db, _users_col  # noqa: E402

logger = logging.getLogger("reconcile_team_pointers")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _firestore_team_ids() -> dict[str, str | None]:
    """Return {user_doc_id: current users.team_id} for every Firestore user."""
    _get_db()
    out: dict[str, str | None] = {}
    for snap in _users_col().stream():
        data = snap.to_dict() or {}
        out[snap.id] = data.get("team_id")
    return out


def _postgres_team_assignments() -> dict[str, str]:
    """Return {user_uid: team_id}. A user can technically be in multiple
    teams in Postgres; this picks the first joined team as the "primary"
    pointer. Multi-team membership is fine; the Firestore pointer is
    just a hot-path hint."""
    with get_sync_session() as s:
        rows = s.execute(
            select(TeamMember.user_uid, TeamMember.team_id, TeamMember.joined_at)
            .order_by(TeamMember.user_uid, TeamMember.joined_at),
        ).all()
    # First (oldest) team per user.
    first: dict[str, str] = {}
    seen: set[str] = set()
    for user_uid, team_id, _ in rows:
        if user_uid not in seen:
            first[user_uid] = team_id
            seen.add(user_uid)
    return first


def reconcile(dry_run: bool = False) -> tuple[int, int, int]:
    """Compute the diff between Postgres and Firestore, optionally apply.

    Returns (set_count, cleared_count, unchanged_count).
    """
    logger.info("loading…")
    pg = _postgres_team_assignments()
    fs = _firestore_team_ids()

    set_count = 0
    cleared_count = 0
    unchanged = 0

    db = _get_db()
    batch = db.batch()
    pending = 0

    for user_id, current in fs.items():
        desired = pg.get(user_id)  # None means user has no team
        if str(current or "") == str(desired or ""):
            unchanged += 1
            continue
        if desired is None:
            cleared_count += 1
        else:
            set_count += 1
        if not dry_run:
            batch.update(_users_col().document(user_id), {"team_id": desired})
            pending += 1
            if pending >= 400:  # Firestore batch cap is 500
                batch.commit()
                batch = db.batch()
                pending = 0

    if not dry_run and pending > 0:
        batch.commit()

    logger.info(
        "set=%d cleared=%d unchanged=%d (dry_run=%s)",
        set_count, cleared_count, unchanged, dry_run,
    )
    return set_count, cleared_count, unchanged


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Only print the diff; don't write to Firestore.")
    args = p.parse_args()
    reconcile(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
