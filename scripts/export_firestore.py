"""Dump all Firestore collections to local JSONL files (M8 #234).

Why a Python script (not ``gcloud firestore export``):
- ``gcloud firestore export`` needs a GCS bucket in the same region and
  Storage Admin perms — extra setup hassle for a one-shot migration.
- Admin SDK reads use the same backend but write directly to local JSONL
  files we can feed into ``migrate_firestore_to_pg.py`` without an
  intermediate ``gcloud firestore import`` round-trip.
- Per Firestore docs, document reads via Admin SDK ARE counted against
  the per-day quota. If Spark is hard-blocked, this script will fail
  with ``ResourceExhausted`` — the fallback path is the Blaze trial
  documented in the issue body.

Output layout::

    {OUT_DIR}/manifest.json          # {collection: count, exported_at}
    {OUT_DIR}/users.jsonl
    {OUT_DIR}/auth_mapping.jsonl
    {OUT_DIR}/user_vocabulary.jsonl  # collection_group query, parent_id stamped
    {OUT_DIR}/quiz_history.jsonl
    ...

Each JSONL line is a self-contained record::

    {"_path": "users/web_xxx/vocabulary/abc123",
     "_id": "abc123",
     "_parent_path": "users/web_xxx",
     "word": "abandon", ...}

Usage::

    python scripts/export_firestore.py [--out-dir /tmp/fs_export]
                                       [--collections users,vocabulary]

Re-runs are idempotent: each collection is rewritten in place. Partial
runs can be resumed by passing ``--collections`` with only the missing
ones.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Project root on sys.path so ``services`` imports work when run directly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from google.cloud.firestore_v1.base_document import DocumentSnapshot  # noqa: E402

from services.repositories.firestore.user_repo import _get_db  # noqa: E402

logger = logging.getLogger("export_firestore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Top-level collections (queried directly).
TOP_LEVEL = [
    "users",
    "auth_mapping",
    "groups",
    "reading_questions",
    "enriched_words",
    "feature_flags",
    "auth_link_codes",
]

# Subcollections under users/{uid}/ — exported via collection_group()
# (parent_id stamped per record so the migrator knows whose data this is).
USER_SUBCOLLECTIONS = [
    "vocabulary",
    "quiz_history",
    "writing_history",
    "daily_words",
    "listening_history",
    "quiz_sessions",
    "reading_sessions",
    "daily_plans",
    "progress_snapshots",
    "progress_recommendations",
]

# Subcollections under groups/{gid}/ — same collection_group treatment.
GROUP_SUBCOLLECTIONS = [
    "daily_words",  # group_daily_words after migration
    "challenges",
]

# challenges/{date}/answers/{uid} is doubly-nested. We export it as a
# separate collection_group("answers") query and resolve the challenge
# parent path per-row.
DOUBLE_NESTED = ["answers"]

ALL_COLLECTIONS = TOP_LEVEL + USER_SUBCOLLECTIONS + GROUP_SUBCOLLECTIONS + DOUBLE_NESTED


def _doc_to_record(doc: DocumentSnapshot) -> dict:
    data = doc.to_dict() or {}
    # Datetimes → ISO strings so the JSONL stays vanilla JSON. The
    # migrator parses them back when needed.
    for k, v in list(data.items()):
        if isinstance(v, datetime):
            data[k] = v.isoformat()
    parent = doc.reference.parent.parent
    return {
        "_path": doc.reference.path,
        "_id": doc.id,
        "_parent_path": parent.path if parent else None,
        **data,
    }


def _stream_top_level(name: str) -> Iterable[DocumentSnapshot]:
    db = _get_db()
    yield from db.collection(name).stream()


def _stream_collection_group(name: str) -> Iterable[DocumentSnapshot]:
    db = _get_db()
    yield from db.collection_group(name).stream()


def _write_jsonl(out_path: Path, records: Iterable[dict]) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            count += 1
    return count


def _output_filename(collection: str) -> str:
    # Disambiguate same-named subcollections under different parents.
    # daily_words appears under users/ and groups/ — split by collection
    # path prefix.
    if collection == "daily_words":
        return "daily_words.jsonl"  # mixed, parent_path discriminates rows
    return f"{collection}.jsonl"


def export_collection(name: str, out_dir: Path) -> int:
    """Export one collection to JSONL. Returns row count."""
    out_path = out_dir / _output_filename(name)
    if name in TOP_LEVEL:
        stream = _stream_top_level(name)
    else:
        # Subcollections — collection_group catches docs at any depth.
        stream = _stream_collection_group(name)
    records = (_doc_to_record(d) for d in stream)
    count = _write_jsonl(out_path, records)
    logger.info("  %s → %s (%d rows)", name, out_path.name, count)
    return count


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "--out-dir",
        type=Path,
        default=_ROOT / ".fs_export",
        help="Output directory for JSONL files (default: ./.fs_export)",
    )
    p.add_argument(
        "--collections",
        type=str,
        default=",".join(ALL_COLLECTIONS),
        help="Comma-separated collection list to export (default: all)",
    )
    args = p.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = [c.strip() for c in args.collections.split(",") if c.strip()]
    logger.info(
        "exporting %d collections → %s", len(selected), out_dir.resolve()
    )

    manifest: dict = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "collections": {},
    }
    failed: list[tuple[str, str]] = []
    for name in selected:
        try:
            count = export_collection(name, out_dir)
            manifest["collections"][name] = count
        except Exception as exc:  # noqa: BLE001 — log + continue for forensics
            logger.error("  FAILED %s: %s", name, exc)
            failed.append((name, str(exc)))

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )

    if failed:
        logger.error("%d collection(s) failed:", len(failed))
        for name, err in failed:
            logger.error("  %s: %s", name, err)
        logger.error(
            "If failure is ResourceExhausted, enable Blaze trial in Firebase "
            "Console (no charge under free tier read budget) and retry."
        )
        return 1

    total = sum(manifest["collections"].values())
    logger.info("done. %d total rows across %d collections", total, len(selected))
    return 0


if __name__ == "__main__":
    sys.exit(main())
