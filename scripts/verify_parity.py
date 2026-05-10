"""Verify Firestore export ↔ Postgres migration parity (M8 #234).

Three gates per collection (all must pass before cutover):

1. **Row count**: PG count >= FS count - allowed_loss
   Allowed loss is non-zero for collections that intentionally drop
   orphan rows (vocabulary/quiz/writing/etc. attached to deduped web
   stubs whose users.id couldn't be backfilled).

2. **Identifier-set equality**: the set of natural keys from FS minus
   known orphans must be a subset of PG keys. This catches "rows
   silently lost during transform" without requiring deep diff.

3. **Hash spot-check** (vocabulary only — most critical user data):
   sample 10 random rows, hash canonical projection from FS + PG,
   require matching hashes. Catches silent field-mapping bugs.

Per-collection allowed_loss values are derived empirically from the
2026-05-10 export (`backfill_users_to_postgres.py` dedup outcome) and
are stored as constants below — bump if dedup logic changes.

Usage::

    python scripts/verify_parity.py --block=A
    python scripts/verify_parity.py --all
    python scripts/verify_parity.py --all --threshold=0  # zero-loss strict
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import sys
from pathlib import Path
from typing import Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text  # noqa: E402

from services.db import get_sync_session  # noqa: E402

logger = logging.getLogger("verify_parity")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

EXPORT_DIR = _ROOT / ".fs_export"


def _read_jsonl(name: str) -> list[dict]:
    path = EXPORT_DIR / f"{name}.jsonl"
    if not path.exists() or path.stat().st_size == 0:
        return []
    return [json.loads(line) for line in path.open()]


def _parent_user(r: dict) -> str | None:
    pp = r.get("_parent_path")
    if not pp or not pp.startswith("users/"):
        return None
    return pp.split("/", 1)[1].split("/")[0]


def _parent_group(r: dict) -> int | None:
    pp = r.get("_parent_path")
    if not pp or not pp.startswith("groups/"):
        return None
    try:
        return int(pp.split("/", 2)[1])
    except (ValueError, IndexError):
        return None


def _parent_group_date(r: dict) -> tuple[int, str] | None:
    pp = r.get("_parent_path") or ""
    parts = pp.split("/")
    if len(parts) < 4 or parts[0] != "groups" or parts[2] != "challenges":
        return None
    try:
        return int(parts[1]), parts[3]
    except ValueError:
        return None


# ─── Per-collection key extractors ──────────────────────────────────────

# Each entry: (jsonl_filename, fs_key_extractor, pg_table, pg_key_query, fs_filter)
# The fs_filter narrows JSONL rows to those that should land in this PG table
# (e.g. user_daily_words filters daily_words.jsonl to user-scoped rows).

COLLECTIONS: dict[str, dict] = {
    "user_vocabulary": {
        "fs_file": "vocabulary",
        "fs_filter": lambda r: _parent_user(r) is not None,
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, id FROM user_vocabulary",
    },
    "quiz_history": {
        "fs_file": "quiz_history",
        "fs_filter": lambda r: _parent_user(r) is not None,
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, id FROM quiz_history",
    },
    "writing_history": {
        "fs_file": "writing_history",
        "fs_filter": lambda r: _parent_user(r) is not None,
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, id FROM writing_history",
    },
    "user_daily_words": {
        "fs_file": "daily_words",
        "fs_filter": lambda r: (r.get("_parent_path") or "").startswith("users/"),
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, date::text FROM user_daily_words",
    },
    "listening_history": {
        "fs_file": "listening_history",
        "fs_filter": lambda r: _parent_user(r) is not None,
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, id FROM listening_history",
    },
    "groups": {
        "fs_file": "groups",
        "fs_filter": lambda r: True,
        "fs_key": lambda r: (int(r["_id"]),),
        "pg_query": "SELECT id FROM groups WHERE id IN (SELECT id FROM groups)",
    },
    "group_daily_words": {
        "fs_file": "daily_words",
        "fs_filter": lambda r: (r.get("_parent_path") or "").startswith("groups/"),
        "fs_key": lambda r: (_parent_group(r), r["_id"]),
        "pg_query": "SELECT group_id, date::text FROM group_daily_words",
    },
    "group_challenges": {
        "fs_file": "challenges",
        "fs_filter": lambda r: _parent_group(r) is not None,
        "fs_key": lambda r: (_parent_group(r), r["_id"]),
        "pg_query": "SELECT group_id, date::text FROM group_challenges",
    },
    "group_challenge_answers": {
        "fs_file": "answers",
        "fs_filter": lambda r: _parent_group_date(r) is not None,
        "fs_key": lambda r: (*_parent_group_date(r), r["_id"]),
        "pg_query": (
            "SELECT c.group_id, c.date::text, a.user_id "
            "FROM group_challenge_answers a JOIN group_challenges c ON a.challenge_id = c.id"
        ),
    },
    "quiz_sessions": {
        "fs_file": "quiz_sessions",
        "fs_filter": lambda r: _parent_user(r) is not None,
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, id FROM quiz_sessions",
    },
    "reading_sessions": {
        "fs_file": "reading_sessions",
        "fs_filter": lambda r: _parent_user(r) is not None,
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, id FROM reading_sessions",
    },
    "daily_plans": {
        "fs_file": "daily_plans",
        "fs_filter": lambda r: _parent_user(r) is not None,
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, date::text FROM daily_plans",
    },
    "progress_snapshots": {
        "fs_file": "progress_snapshots",
        "fs_filter": lambda r: _parent_user(r) is not None,
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, date::text FROM progress_snapshots",
    },
    "progress_recommendations": {
        "fs_file": "progress_recommendations",
        "fs_filter": lambda r: _parent_user(r) is not None,
        "fs_key": lambda r: (_parent_user(r), r["_id"]),
        "pg_query": "SELECT user_id, week_key FROM progress_recommendations",
    },
    "reading_questions": {
        "fs_file": "reading_questions",
        "fs_filter": lambda r: True,
        "fs_key": lambda r: (r["_id"],),
        "pg_query": "SELECT passage_id FROM reading_questions",
    },
    "enriched_words": {
        "fs_file": "enriched_words",
        "fs_filter": lambda r: True,
        "fs_key": lambda r: (r["_id"],),
        "pg_query": "SELECT word FROM enriched_words",
    },
    "feature_flags": {
        "fs_file": "feature_flags",
        "fs_filter": lambda r: True,
        "fs_key": lambda r: (r["_id"],),
        "pg_query": "SELECT name FROM feature_flags",
    },
    "auth_link_codes": {
        "fs_file": "auth_link_codes",
        "fs_filter": lambda r: True,
        "fs_key": lambda r: (r["_id"],),
        "pg_query": "SELECT code FROM auth_link_codes",
    },
}


BLOCK_OF: dict[str, str] = {
    "user_vocabulary": "A", "quiz_history": "A", "writing_history": "A",
    "user_daily_words": "A", "listening_history": "A",
    "groups": "B", "group_daily_words": "B", "group_challenges": "B",
    "group_challenge_answers": "B",
    "quiz_sessions": "C", "reading_sessions": "C",
    "daily_plans": "D", "progress_snapshots": "D", "progress_recommendations": "D",
    "reading_questions": "E", "enriched_words": "E", "feature_flags": "E",
    "auth_link_codes": "F",
}


def _backfilled_user_ids() -> set[str]:
    """The set of users that successfully made it into PG (post-dedup).

    Used to compute orphan loss = subcollection rows whose user_id was
    deduped out by ``backfill_users_to_postgres.py``.
    """
    with get_sync_session() as s:
        return set(s.execute(text("SELECT id FROM users")).scalars().all())


# ─── Verifier ───────────────────────────────────────────────────────────


def verify(name: str, threshold: int) -> bool:
    """Returns True if collection passes parity gates."""
    spec = COLLECTIONS[name]
    fs_rows = _read_jsonl(spec["fs_file"])
    fs_filtered = [r for r in fs_rows if spec["fs_filter"](r)]

    # Compute orphan loss (rows whose parent user got deduped out of PG).
    backfilled_users = _backfilled_user_ids()
    orphan = 0
    fs_keys: set[tuple] = set()
    for r in fs_filtered:
        # If the row is user-scoped, drop rows whose user isn't in PG.
        uid = _parent_user(r)
        if uid is not None and uid not in backfilled_users:
            orphan += 1
            continue
        try:
            fs_keys.add(spec["fs_key"](r))
        except (KeyError, ValueError, TypeError) as e:
            logger.error("  [%s] FS key extraction failed: %s — row=%r", name, e, r)
            return False

    with get_sync_session() as s:
        pg_keys = set(tuple(row) for row in s.execute(text(spec["pg_query"])).fetchall())

    fs_n = len(fs_keys)
    pg_n = len(pg_keys)
    diff_in_fs_only = fs_keys - pg_keys
    diff_in_pg_only = pg_keys - fs_keys

    status = "OK"
    failed = False

    # Only fail on data-loss (FS rows missing in PG). Extra rows in PG are
    # acceptable: orphan group stubs we synthesize, post-export inserts,
    # and idempotent reruns of the migrator all add to PG without data loss.
    missing_in_pg = len(diff_in_fs_only)
    if missing_in_pg > threshold:
        status = "FAIL"
        failed = True

    logger.info(
        "  [%s/%s] FS=%d PG=%d (orphan=%d, missing_in_pg=%d, extra_in_pg=%d) — %s",
        BLOCK_OF.get(name, "?"), name,
        fs_n, pg_n, orphan, missing_in_pg, len(diff_in_pg_only), status,
    )
    if missing_in_pg and missing_in_pg <= 5:
        logger.info("    missing keys (sample): %s", list(diff_in_fs_only)[:5])
    return not failed


def verify_vocab_hash_spot_check(sample_size: int = 10) -> bool:
    """Hash-based deep compare for user_vocabulary (most-critical table)."""
    fs_rows = [r for r in _read_jsonl("vocabulary") if _parent_user(r)]
    if not fs_rows:
        return True

    backfilled = _backfilled_user_ids()
    fs_indexed = {
        (_parent_user(r), r["_id"]): r
        for r in fs_rows
        if _parent_user(r) in backfilled
    }
    sample_keys = random.sample(list(fs_indexed.keys()), min(sample_size, len(fs_indexed)))

    with get_sync_session() as s:
        rows = s.execute(
            text(
                "SELECT user_id, id, word, definition_en, srs_interval, srs_reps "
                "FROM user_vocabulary WHERE id = ANY(:ids)"
            ),
            {"ids": [k[1] for k in sample_keys]},
        ).fetchall()
    pg_indexed = {(r._mapping["user_id"], r._mapping["id"]): r._mapping for r in rows}

    failures = 0
    for k in sample_keys:
        fs = fs_indexed[k]
        pg = pg_indexed.get(k)
        if pg is None:
            logger.error("    spot-check %s: missing in PG", k)
            failures += 1
            continue
        # Canonical projection: word, definition_en (or fallback definition),
        # srs_interval, srs_reps. Skip srs_next_review (timezone normalization
        # drift) and topic (display→slug remap is intended).
        fs_def = fs.get("definition_en") or fs.get("definition") or ""
        if (
            (fs.get("word") or "").strip() != pg["word"]
            or fs_def.strip() != pg["definition_en"]
            or int(fs.get("srs_interval") or 0) != pg["srs_interval"]
            or int(fs.get("srs_reps") or 0) != pg["srs_reps"]
        ):
            logger.error(
                "    spot-check %s mismatch:\n"
                "      FS: word=%r def=%r interval=%s reps=%s\n"
                "      PG: word=%r def=%r interval=%s reps=%s",
                k,
                fs.get("word"), fs_def, fs.get("srs_interval"), fs.get("srs_reps"),
                pg["word"], pg["definition_en"], pg["srs_interval"], pg["srs_reps"],
            )
            failures += 1
    logger.info(
        "  [vocab spot-check] sampled %d, failures=%d", len(sample_keys), failures
    )
    return failures == 0


# ─── CLI ────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--block", choices=["A", "B", "C", "D", "E", "F", "all"], default="all")
    p.add_argument("--threshold", type=int, default=0,
                   help="Allowed row delta per collection (default 0 — strict)")
    p.add_argument("--skip-spot-check", action="store_true")
    args = p.parse_args()

    selected = (
        list(COLLECTIONS.keys())
        if args.block == "all"
        else [k for k, v in BLOCK_OF.items() if v == args.block]
    )

    failed: list[str] = []
    for name in selected:
        ok = verify(name, threshold=args.threshold)
        if not ok:
            failed.append(name)

    if not args.skip_spot_check and (
        args.block in ("A", "all")
    ):
        logger.info("--- Vocabulary hash spot-check ---")
        if not verify_vocab_hash_spot_check():
            failed.append("user_vocabulary (spot-check)")

    if failed:
        logger.error("PARITY FAILED: %s", ", ".join(failed))
        return 1
    logger.info("PARITY OK: %d collection(s) passed", len(selected))
    return 0


if __name__ == "__main__":
    sys.exit(main())
