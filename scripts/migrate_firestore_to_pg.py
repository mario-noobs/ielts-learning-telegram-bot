"""Transform Firestore JSONL exports → Postgres rows (M8 #234).

Reads ``.fs_export/{collection}.jsonl`` (produced by
``scripts/export_firestore.py``) and bulk-inserts into the Postgres
tables defined in ``migrations/versions/0006_full_firestore_cutover.py``.

Idempotent + block-aware. Pass ``--block=A|B|C|D|E|F`` to migrate one
logical block; ``--block=all`` runs all six in dependency order.

Block layout (must apply in this order if doing all-at-once):
  A. user_vocabulary, quiz_history, writing_history, user_daily_words,
     listening_history (FK→users; users themselves are migrated by
     ``backfill_users_to_postgres.py`` from M8.1 — verify before A.)
  B. groups, group_members (derived from users.group_id),
     group_daily_words, group_challenges, group_challenge_answers
  C. quiz_sessions, reading_sessions
  D. daily_plans, progress_snapshots, progress_recommendations
  E. reading_questions, enriched_words, feature_flags
  F. auth_link_codes

App-side improvements applied at insert time (per #234 refinement):
  * user_vocabulary.normalized_word: NFC + lower + strip punct.
  * user_vocabulary.topic_id: lookup TOPIC_DISPLAY_TO_ID for the FS
    `topic` display name; rows whose topic doesn't map fall back to
    "society" (id=10) with a warning.
  * user_vocabulary.definition_en: prefers existing `definition_en`,
    falls back to legacy `definition`. Drops `times_correct`/
    `times_incorrect` (dead fields).
  * user_vocabulary.source: defaults to 1 (daily) — historical
    provenance is unrecoverable.
  * group_challenges.id: deterministic UUIDv5 from
    (group_id, date) so re-runs map to the same id; child answers
    resolve via the same derivation.

Usage::

    python scripts/migrate_firestore_to_pg.py --block=A
    python scripts/migrate_firestore_to_pg.py --block=all
    python scripts/migrate_firestore_to_pg.py --block=B --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from services.db import get_sync_session  # noqa: E402

logger = logging.getLogger("migrate_fs")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

EXPORT_DIR = _ROOT / ".fs_export"

# ─── Topic display → slug → id ──────────────────────────────────────────

# Maps both display names (en) and slugs (lowercase) to topic_id, so the
# migrator handles whichever shape Firestore stored. Display names mirror
# 0006 TOPICS_SEED.
TOPIC_LOOKUP: dict[str, int] = {}


def _build_topic_lookup() -> None:
    seed = [
        (1, "arts", "Arts & Creativity"),
        (2, "economy", "Economy & Business"),
        (3, "education", "Education & Learning"),
        (4, "environment", "Environment & Nature"),
        (5, "food", "Food & Agriculture"),
        (6, "government", "Government & Law"),
        (7, "health", "Health & Wellbeing"),
        (8, "media", "Media & Communication"),
        (9, "science", "Science & Research"),
        (10, "society", "Society & Culture"),
        (11, "technology", "Technology & Innovation"),
        (12, "travel", "Travel & Tourism"),
    ]
    for tid, slug, display in seed:
        TOPIC_LOOKUP[slug.lower()] = tid
        TOPIC_LOOKUP[display.lower()] = tid


_FALLBACK_TOPIC_ID = 10  # society — least biased default


def _topic_id(raw: str | None) -> int:
    if not raw:
        return _FALLBACK_TOPIC_ID
    key = raw.strip().lower()
    if key in TOPIC_LOOKUP:
        return TOPIC_LOOKUP[key]
    # Some topics only match prefix (e.g. "Education & Learning" vs "education")
    for k, v in TOPIC_LOOKUP.items():
        if key.startswith(k) or k.startswith(key):
            return v
    logger.warning("  topic %r not found, using fallback id=%d", raw, _FALLBACK_TOPIC_ID)
    return _FALLBACK_TOPIC_ID


# ─── Helpers ────────────────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def normalize_word(word: str) -> str:
    """NFC normalize + lower + strip punctuation. Used as dedupe key."""
    if not word:
        return ""
    s = unicodedata.normalize("NFC", word).lower().strip()
    s = _PUNCT_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_dt(v: Any) -> datetime | None:
    """Parse ISO datetime string; return None if missing/invalid."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    try:
        s = str(v).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        logger.debug("  unparseable datetime: %r", v)
        return None


def parse_date(v: Any) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).split("T")[0]).date()
    except (ValueError, TypeError):
        return None


def parent_to_user_id(parent_path: str | None) -> str | None:
    """Extract user_id from `users/{uid}` parent path. Returns None for non-user paths."""
    if not parent_path or not parent_path.startswith("users/"):
        return None
    return parent_path.split("/", 1)[1].split("/")[0]


def parent_to_group_id(parent_path: str | None) -> int | None:
    """Extract group_id (Telegram chat_id) from `groups/{gid}` or `groups/{gid}/...`."""
    if not parent_path or not parent_path.startswith("groups/"):
        return None
    try:
        return int(parent_path.split("/", 2)[1])
    except (ValueError, IndexError):
        return None


def parent_to_group_and_date(parent_path: str | None) -> tuple[int, str] | None:
    """Extract (group_id, date_str) from `groups/{gid}/challenges/{date}`."""
    if not parent_path:
        return None
    parts = parent_path.split("/")
    if len(parts) < 4 or parts[0] != "groups" or parts[2] != "challenges":
        return None
    try:
        return int(parts[1]), parts[3]
    except ValueError:
        return None


# Stable challenge_id: UUIDv5 of (group_id, date). Re-runs of the
# migration produce identical ids so answer rows resolve correctly.
_CHALLENGE_NAMESPACE = uuid.UUID("e6a9d8bb-4c1e-5f8e-9c1a-1f2c3d4e5f60")


def challenge_id(group_id: int, date_str: str) -> str:
    return str(uuid.uuid5(_CHALLENGE_NAMESPACE, f"{group_id}:{date_str}"))


def _read_jsonl(name: str) -> list[dict]:
    path = EXPORT_DIR / f"{name}.jsonl"
    if not path.exists():
        logger.warning("  no export for %s (file missing), skipping", name)
        return []
    if path.stat().st_size == 0:
        logger.info("  %s.jsonl is empty, skipping", name)
        return []
    return [json.loads(line) for line in path.open()]


# ─── Bulk upsert helper ─────────────────────────────────────────────────


def _bulk_upsert(
    table: str,
    pk_cols: list[str],
    rows: list[dict],
    *,
    update_excluded: bool = True,
    dry_run: bool = False,
) -> int:
    if not rows:
        return 0
    if dry_run:
        logger.info("    [dry-run] would upsert %d rows into %s", len(rows), table)
        return len(rows)
    # Use raw SQL via sa.text for portability (rather than reflecting tables).
    cols = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    col_list = ", ".join(cols)
    if update_excluded:
        update_set = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in cols if c not in pk_cols
        )
        conflict_clause = (
            f"ON CONFLICT ({', '.join(pk_cols)}) DO UPDATE SET {update_set}"
            if update_set
            else f"ON CONFLICT ({', '.join(pk_cols)}) DO NOTHING"
        )
    else:
        conflict_clause = f"ON CONFLICT ({', '.join(pk_cols)}) DO NOTHING"
    stmt = text(
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) {conflict_clause}"
    )
    inserted = 0
    with get_sync_session() as s, s.begin():
        for row in rows:
            s.execute(stmt, row)
            inserted += 1
    return inserted


# ─── Migrators ──────────────────────────────────────────────────────────


def _ensure_user_exists(user_ids: Iterable[str]) -> set[str]:
    """Return the subset of user_ids that exist in PG users table.

    Rows whose user_id isn't backfilled get dropped with a warning.
    """
    ids = list({u for u in user_ids if u})
    if not ids:
        return set()
    with get_sync_session() as s:
        rows = s.execute(
            text("SELECT id FROM users WHERE id = ANY(:ids)"),
            {"ids": ids},
        ).scalars().all()
    return set(rows)


# ── Block A ──────────────────────────────────────────────────────────────


def migrate_user_vocabulary(dry_run: bool = False) -> int:
    rows = _read_jsonl("vocabulary")
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in rows)
    pg_rows: list[dict] = []
    skipped_no_user = 0
    for r in rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            skipped_no_user += 1
            continue
        word = (r.get("word") or "").strip()
        if not word:
            continue
        added = parse_dt(r.get("added_at"))
        # definition (legacy English) → definition_en if missing
        def_en = (r.get("definition_en") or r.get("definition") or "").strip()
        pg_rows.append({
            "id": r["_id"],
            "user_id": uid,
            "word": word,
            "normalized_word": normalize_word(word),
            "topic_id": _topic_id(r.get("topic")),
            "definition_en": def_en,
            "definition_vi": (r.get("definition_vi") or "").strip(),
            "ipa": (r.get("ipa") or "").strip(),
            "part_of_speech": (r.get("part_of_speech") or "").strip(),
            "example_en": (r.get("example_en") or r.get("example") or "").strip(),
            "example_vi": (r.get("example_vi") or "").strip(),
            "user_note": "",
            "source": 1,  # historical provenance unrecoverable
            "srs_interval": int(r.get("srs_interval") or 0),
            "srs_ease": float(r.get("srs_ease") or 2.5),
            "srs_reps": int(r.get("srs_reps") or 0),
            "srs_next_review": parse_dt(r.get("srs_next_review")),
            "archived_at": None,
            "created_at": added or datetime.utcnow(),
            "updated_at": added or datetime.utcnow(),
        })
    if skipped_no_user:
        logger.warning("  user_vocabulary: %d row(s) dropped (user not in PG)", skipped_no_user)
    return _bulk_upsert("user_vocabulary", ["id"], pg_rows, dry_run=dry_run)


def migrate_quiz_history(dry_run: bool = False) -> int:
    rows = _read_jsonl("quiz_history")
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in rows)
    pg_rows: list[dict] = []
    skipped = 0
    for r in rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            skipped += 1
            continue
        # Catch-all payload for fields that don't get their own column
        payload = {
            k: v for k, v in r.items()
            if not k.startswith("_") and k not in {
                "type", "is_correct", "is_challenge", "word_id", "created_at",
            }
        }
        pg_rows.append({
            "id": r["_id"],
            "user_id": uid,
            "quiz_type": r.get("type") or "unknown",
            "is_correct": bool(r.get("is_correct")),
            "is_challenge": bool(r.get("is_challenge", False)),
            "word_id": r.get("word_id"),
            "payload": json.dumps(payload, ensure_ascii=False) if payload else None,
            "created_at": parse_dt(r.get("created_at")) or datetime.utcnow(),
        })
    if skipped:
        logger.warning("  quiz_history: %d row(s) dropped (user not in PG)", skipped)
    return _bulk_upsert("quiz_history", ["id"], pg_rows, dry_run=dry_run)


def migrate_writing_history(dry_run: bool = False) -> int:
    rows = _read_jsonl("writing_history")
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in rows)
    pg_rows: list[dict] = []
    skipped = 0
    structured = {
        "task_type", "prompt", "text", "original_text", "language",
        "overall_band", "word_count", "summary_vi", "scores",
        "criterion_feedback", "paragraph_annotations", "shared_to_group",
        "created_at",
    }
    for r in rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            skipped += 1
            continue
        feedback = {k: v for k, v in r.items() if not k.startswith("_") and k not in structured}
        pg_rows.append({
            "id": r["_id"],
            "user_id": uid,
            "task_type": r.get("task_type"),
            "prompt": r.get("prompt"),
            "essay_text": r.get("text"),
            "original_text": r.get("original_text"),
            "language": r.get("language"),
            "overall_band": r.get("overall_band"),
            "word_count": r.get("word_count"),
            "summary_vi": r.get("summary_vi"),
            "scores": json.dumps(r["scores"], ensure_ascii=False) if r.get("scores") else None,
            "criterion_feedback": json.dumps(r["criterion_feedback"], ensure_ascii=False) if r.get("criterion_feedback") else None,
            "paragraph_annotations": json.dumps(r["paragraph_annotations"], ensure_ascii=False) if r.get("paragraph_annotations") else None,
            "feedback": json.dumps(feedback, ensure_ascii=False) if feedback else None,
            "shared_to_group": bool(r.get("shared_to_group", False)),
            "created_at": parse_dt(r.get("created_at")) or datetime.utcnow(),
        })
    if skipped:
        logger.warning("  writing_history: %d row(s) dropped (user not in PG)", skipped)
    return _bulk_upsert("writing_history", ["id"], pg_rows, dry_run=dry_run)


def migrate_user_daily_words(dry_run: bool = False) -> int:
    rows = _read_jsonl("daily_words")
    # Filter to user-scoped rows (not group-scoped — those go in B)
    user_rows = [r for r in rows if (r.get("_parent_path") or "").startswith("users/")]
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in user_rows)
    pg_rows: list[dict] = []
    skipped = 0
    for r in user_rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            skipped += 1
            continue
        d = parse_date(r["_id"]) or parse_date(r.get("date"))
        if not d:
            continue
        pg_rows.append({
            "user_id": uid,
            "date": d,
            "words": json.dumps(r.get("words") or [], ensure_ascii=False),
            "topic": r.get("topic"),
            "generated_at": parse_dt(r.get("generated_at")) or datetime.utcnow(),
        })
    if skipped:
        logger.warning("  user_daily_words: %d row(s) dropped (user not in PG)", skipped)
    return _bulk_upsert("user_daily_words", ["user_id", "date"], pg_rows, dry_run=dry_run)


def migrate_listening_history(dry_run: bool = False) -> int:
    rows = _read_jsonl("listening_history")
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in rows)
    pg_rows: list[dict] = []
    skipped = 0
    structured = {
        "exercise_type", "title", "topic", "band", "score", "total",
        "duration_estimate_sec", "submitted", "created_at",
    }
    for r in rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            skipped += 1
            continue
        payload = {k: v for k, v in r.items() if not k.startswith("_") and k not in structured}
        pg_rows.append({
            "id": r["_id"],
            "user_id": uid,
            "exercise_type": r.get("exercise_type"),
            "title": r.get("title"),
            "topic": r.get("topic"),
            "band": r.get("band"),
            "score": r.get("score"),
            "total": r.get("total"),
            "duration_estimate_sec": r.get("duration_estimate_sec"),
            "submitted": bool(r.get("submitted", False)),
            "payload": json.dumps(payload, ensure_ascii=False) if payload else None,
            "created_at": parse_dt(r.get("created_at")) or datetime.utcnow(),
        })
    if skipped:
        logger.warning("  listening_history: %d row(s) dropped (user not in PG)", skipped)
    return _bulk_upsert("listening_history", ["id"], pg_rows, dry_run=dry_run)


# ── Block B ──────────────────────────────────────────────────────────────


def migrate_groups(dry_run: bool = False) -> int:
    rows = _read_jsonl("groups")
    pg_rows: list[dict] = []
    seen_ids: set[int] = set()
    for r in rows:
        try:
            gid = int(r["_id"])
        except (ValueError, TypeError):
            continue
        seen_ids.add(gid)
        pg_rows.append({
            "id": gid,
            "default_band": r.get("default_band"),
            "daily_time": r.get("daily_time"),
            "challenge_time": r.get("challenge_time"),
            "timezone": r.get("timezone"),
            "challenge_question_count": r.get("challenge_question_count"),
            "word_count": r.get("word_count"),
            "owner_telegram_id": r.get("owner_telegram_id"),
            "owner_uid": r.get("owner_uid"),
            "topics": json.dumps(r.get("topics") or [], ensure_ascii=False),
            "recent_topics": json.dumps(r.get("recent_topics") or [], ensure_ascii=False),
            "created_at": parse_dt(r.get("created_at")) or datetime.utcnow(),
            "updated_at": parse_dt(r.get("updated_at")) or parse_dt(r.get("created_at")) or datetime.utcnow(),
        })
    # Discover orphan groups via subcollection parent paths (Firestore had
    # cases where the parent doc was deleted but subcollections remained).
    # Insert minimal stub rows so FK constraints in B don't fail.
    orphan_ids: set[int] = set()
    for fname in ("daily_words", "challenges", "answers"):
        for sub in _read_jsonl(fname):
            gid = parent_to_group_id(sub.get("_parent_path"))
            if gid is not None and gid not in seen_ids:
                orphan_ids.add(gid)
    for gid in sorted(orphan_ids):
        seen_ids.add(gid)
        pg_rows.append({
            "id": gid,
            "default_band": None,
            "daily_time": None,
            "challenge_time": None,
            "timezone": None,
            "challenge_question_count": None,
            "word_count": None,
            "owner_telegram_id": None,
            "owner_uid": None,
            "topics": "[]",
            "recent_topics": "[]",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
    if orphan_ids:
        logger.info(
            "  groups: %d stub row(s) inserted for orphan group_id(s) "
            "found via subcollection paths: %s",
            len(orphan_ids),
            sorted(orphan_ids),
        )
    return _bulk_upsert("groups", ["id"], pg_rows, dry_run=dry_run)


def migrate_group_members(dry_run: bool = False) -> int:
    """Derive group_members from users.group_id. Web users (id starts with 'web_') skip."""
    pg_rows: list[dict] = []
    with get_sync_session() as s:
        users = s.execute(
            text("SELECT id, group_id FROM users WHERE group_id IS NOT NULL")
        ).fetchall()
    # Owner discovery: lookup groups.owner_telegram_id
    with get_sync_session() as s:
        owners = {row[0]: row[1] for row in s.execute(
            text("SELECT id, owner_telegram_id FROM groups")
        ).fetchall()}
    skipped_web = 0
    for u in users:
        uid, group_id = u[0], u[1]
        try:
            tg_id = int(uid)  # only telegram ids are pure numeric
        except ValueError:
            skipped_web += 1
            continue
        role = "owner" if owners.get(group_id) == tg_id else "member"
        pg_rows.append({
            "group_id": group_id,
            "telegram_id": tg_id,
            "role": role,
            "joined_at": datetime.utcnow(),
        })
    if skipped_web:
        logger.info("  group_members: skipped %d web user(s) (no telegram_id)", skipped_web)
    return _bulk_upsert(
        "group_members", ["group_id", "telegram_id"], pg_rows, dry_run=dry_run,
    )


def migrate_group_daily_words(dry_run: bool = False) -> int:
    rows = _read_jsonl("daily_words")
    group_rows = [r for r in rows if (r.get("_parent_path") or "").startswith("groups/")]
    pg_rows: list[dict] = []
    for r in group_rows:
        gid = parent_to_group_id(r.get("_parent_path"))
        if gid is None:
            continue
        d = parse_date(r["_id"]) or parse_date(r.get("date"))
        if not d:
            continue
        pg_rows.append({
            "group_id": gid,
            "date": d,
            "words": json.dumps(r.get("words") or [], ensure_ascii=False),
            "topic": r.get("topic"),
            "generated_at": parse_dt(r.get("generated_at")) or datetime.utcnow(),
        })
    return _bulk_upsert(
        "group_daily_words", ["group_id", "date"], pg_rows, dry_run=dry_run,
    )


def migrate_group_challenges(dry_run: bool = False) -> int:
    rows = _read_jsonl("challenges")
    pg_rows: list[dict] = []
    for r in rows:
        gid = parent_to_group_id(r.get("_parent_path"))
        if gid is None:
            continue
        d = parse_date(r["_id"])
        if not d:
            continue
        pg_rows.append({
            "id": challenge_id(gid, r["_id"]),
            "group_id": gid,
            "date": d,
            "status": r.get("status") or "active",
            "questions": json.dumps(r.get("questions") or [], ensure_ascii=False),
            "participants": json.dumps(r.get("participants") or {}, ensure_ascii=False),
            "created_at": parse_dt(r.get("created_at")) or datetime.utcnow(),
            "expires_at": parse_dt(r.get("expires_at")),
        })
    return _bulk_upsert("group_challenges", ["id"], pg_rows, dry_run=dry_run)


def migrate_group_challenge_answers(dry_run: bool = False) -> int:
    rows = _read_jsonl("answers")
    pg_rows: list[dict] = []
    skipped_orphan = 0
    for r in rows:
        gd = parent_to_group_and_date(r.get("_parent_path"))
        if not gd:
            skipped_orphan += 1
            continue
        gid, date_str = gd
        pg_rows.append({
            "challenge_id": challenge_id(gid, date_str),
            "user_id": r["_id"],
            "responses": json.dumps(r.get("responses") or {}, ensure_ascii=False),
            "display_name": r.get("display_name"),
            "started_at": parse_dt(r.get("started_at")),
            "completed_at": parse_dt(r.get("completed_at")),
        })
    if skipped_orphan:
        logger.warning("  group_challenge_answers: %d row(s) dropped (orphan path)", skipped_orphan)
    return _bulk_upsert(
        "group_challenge_answers",
        ["challenge_id", "user_id"],
        pg_rows,
        dry_run=dry_run,
    )


# ── Block C ──────────────────────────────────────────────────────────────


def migrate_quiz_sessions(dry_run: bool = False) -> int:
    rows = _read_jsonl("quiz_sessions")
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in rows)
    pg_rows: list[dict] = []
    for r in rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            continue
        pg_rows.append({
            "id": r["_id"],
            "user_id": uid,
            "questions": json.dumps(r.get("questions") or [], ensure_ascii=False),
            "answered_ids": json.dumps(r.get("answered_ids") or [], ensure_ascii=False),
            "created_at": parse_dt(r.get("created_at")) or datetime.utcnow(),
        })
    return _bulk_upsert("quiz_sessions", ["id"], pg_rows, dry_run=dry_run)


def migrate_reading_sessions(dry_run: bool = False) -> int:
    rows = _read_jsonl("reading_sessions")
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in rows)
    pg_rows: list[dict] = []
    for r in rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            continue
        pg_rows.append({
            "id": r["_id"],
            "user_id": uid,
            "passage_id": r.get("passage_id"),
            "status": r.get("status") or "in_progress",
            "questions": json.dumps(r.get("questions") or [], ensure_ascii=False),
            "answer_key": json.dumps(r.get("answer_key") or [], ensure_ascii=False),
            "user_answers": json.dumps(r["user_answers"], ensure_ascii=False) if r.get("user_answers") else None,
            "grade": json.dumps(r["grade"], ensure_ascii=False) if r.get("grade") else None,
            "idempotency_key": r.get("idempotency_key"),
            "started_at": parse_dt(r.get("started_at")) or datetime.utcnow(),
            "submitted_at": parse_dt(r.get("submitted_at")),
            "expires_at": parse_dt(r.get("expires_at")),
            "updated_at": parse_dt(r.get("updated_at")) or datetime.utcnow(),
        })
    return _bulk_upsert("reading_sessions", ["id"], pg_rows, dry_run=dry_run)


# ── Block D ──────────────────────────────────────────────────────────────


def migrate_daily_plans(dry_run: bool = False) -> int:
    rows = _read_jsonl("daily_plans")
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in rows)
    pg_rows: list[dict] = []
    for r in rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            continue
        d = parse_date(r["_id"]) or parse_date(r.get("date"))
        if not d:
            continue
        pg_rows.append({
            "user_id": uid,
            "date": d,
            "activities": json.dumps(r.get("activities") or [], ensure_ascii=False),
            "cap_minutes": r.get("cap_minutes"),
            "completed_count": int(r.get("completed_count") or 0),
            "total_minutes": r.get("total_minutes"),
            "days_until_exam": r.get("days_until_exam"),
            "exam_urgent": bool(r.get("exam_urgent", False)),
            "generated_at": parse_dt(r.get("generated_at")) or datetime.utcnow(),
            "completed_at": parse_dt(r.get("completed_at")),
        })
    return _bulk_upsert("daily_plans", ["user_id", "date"], pg_rows, dry_run=dry_run)


def migrate_progress_snapshots(dry_run: bool = False) -> int:
    rows = _read_jsonl("progress_snapshots")
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in rows)
    pg_rows: list[dict] = []
    for r in rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            continue
        d = parse_date(r["_id"]) or parse_date(r.get("date"))
        if not d:
            continue
        pg_rows.append({
            "user_id": uid,
            "date": d,
            "overall_band": r.get("overall_band"),
            "target_band": r.get("target_band"),
            "skills": json.dumps(r.get("skills") or {}, ensure_ascii=False),
            "generated_at": parse_dt(r.get("generated_at")) or datetime.utcnow(),
        })
    return _bulk_upsert("progress_snapshots", ["user_id", "date"], pg_rows, dry_run=dry_run)


def migrate_progress_recommendations(dry_run: bool = False) -> int:
    rows = _read_jsonl("progress_recommendations")
    valid_users = _ensure_user_exists(parent_to_user_id(r.get("_parent_path")) for r in rows)
    pg_rows: list[dict] = []
    for r in rows:
        uid = parent_to_user_id(r.get("_parent_path"))
        if uid not in valid_users:
            continue
        wk = r.get("week_key") or r["_id"]
        pg_rows.append({
            "user_id": uid,
            "week_key": wk,
            "tips": json.dumps(r.get("tips") or [], ensure_ascii=False),
            "generated_at": parse_dt(r.get("generated_at")) or datetime.utcnow(),
        })
    return _bulk_upsert(
        "progress_recommendations", ["user_id", "week_key"], pg_rows, dry_run=dry_run,
    )


# ── Block E ──────────────────────────────────────────────────────────────


def migrate_reading_questions(dry_run: bool = False) -> int:
    rows = _read_jsonl("reading_questions")
    pg_rows = [{
        "passage_id": r["_id"],
        "questions_client": json.dumps(r.get("questions_client") or [], ensure_ascii=False),
        "answer_key": json.dumps(r.get("answer_key") or [], ensure_ascii=False),
        "cached_at": parse_dt(r.get("cached_at")) or datetime.utcnow(),
    } for r in rows]
    return _bulk_upsert("reading_questions", ["passage_id"], pg_rows, dry_run=dry_run)


def migrate_enriched_words(dry_run: bool = False) -> int:
    rows = _read_jsonl("enriched_words")
    pg_rows: list[dict] = []
    for r in rows:
        pg_rows.append({
            "word": r["_id"],
            "ipa": r.get("ipa"),
            "part_of_speech": r.get("part_of_speech"),
            "definition_en": r.get("definition_en"),
            "definition_vi": r.get("definition_vi"),
            "syllable_stress": r.get("syllable_stress"),
            "ielts_tip": r.get("ielts_tip"),
            "examples_by_band": json.dumps(r["examples_by_band"], ensure_ascii=False) if r.get("examples_by_band") else None,
            "collocations": json.dumps(r["collocations"], ensure_ascii=False) if r.get("collocations") else None,
            "word_family": json.dumps(r["word_family"], ensure_ascii=False) if r.get("word_family") else None,
            "cached_at": parse_dt(r.get("cached_at")) or datetime.utcnow(),
        })
    return _bulk_upsert("enriched_words", ["word"], pg_rows, dry_run=dry_run)


def migrate_feature_flags(dry_run: bool = False) -> int:
    rows = _read_jsonl("feature_flags")
    pg_rows = [{
        "name": r["_id"],
        "enabled": bool(r.get("enabled", False)),
        "kill_switch": bool(r.get("kill_switch", False)),
        "rollout_pct": int(r.get("rollout_pct") or 0),
        "uid_allowlist": list(r.get("uid_allowlist") or []),
        "updated_at": parse_dt(r.get("updated_at")) or datetime.utcnow(),
    } for r in rows]
    return _bulk_upsert("feature_flags", ["name"], pg_rows, dry_run=dry_run)


# ── Block F ──────────────────────────────────────────────────────────────


def migrate_auth_link_codes(dry_run: bool = False) -> int:
    rows = _read_jsonl("auth_link_codes")
    pg_rows: list[dict] = []
    for r in rows:
        tid = r.get("telegram_id")
        if tid is None:
            continue
        pg_rows.append({
            "code": r["_id"],
            "telegram_id": int(tid),
            "expires_at": parse_dt(r.get("expires_at")) or datetime.utcnow(),
            "created_at": parse_dt(r.get("created_at")) or datetime.utcnow(),
        })
    return _bulk_upsert("auth_link_codes", ["code"], pg_rows, dry_run=dry_run)


# ─── Block dispatch ─────────────────────────────────────────────────────

BLOCKS: dict[str, list[tuple[str, Any]]] = {
    "A": [
        ("user_vocabulary", migrate_user_vocabulary),
        ("quiz_history", migrate_quiz_history),
        ("writing_history", migrate_writing_history),
        ("user_daily_words", migrate_user_daily_words),
        ("listening_history", migrate_listening_history),
    ],
    "B": [
        ("groups", migrate_groups),
        ("group_members", migrate_group_members),
        ("group_daily_words", migrate_group_daily_words),
        ("group_challenges", migrate_group_challenges),
        ("group_challenge_answers", migrate_group_challenge_answers),
    ],
    "C": [
        ("quiz_sessions", migrate_quiz_sessions),
        ("reading_sessions", migrate_reading_sessions),
    ],
    "D": [
        ("daily_plans", migrate_daily_plans),
        ("progress_snapshots", migrate_progress_snapshots),
        ("progress_recommendations", migrate_progress_recommendations),
    ],
    "E": [
        ("reading_questions", migrate_reading_questions),
        ("enriched_words", migrate_enriched_words),
        ("feature_flags", migrate_feature_flags),
    ],
    "F": [
        ("auth_link_codes", migrate_auth_link_codes),
    ],
}


def run_block(block: str, dry_run: bool = False) -> int:
    fns = BLOCKS[block]
    total = 0
    for name, fn in fns:
        logger.info("[Block %s] %s", block, name)
        n = fn(dry_run=dry_run)
        logger.info("  → %d rows", n)
        total += n
    return total


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "--block",
        choices=["A", "B", "C", "D", "E", "F", "all"],
        default="all",
        help="Logical block to migrate (default: all in dependency order)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute row mappings but skip the INSERT.",
    )
    args = p.parse_args()

    _build_topic_lookup()

    blocks = ["A", "B", "C", "D", "E", "F"] if args.block == "all" else [args.block]
    grand_total = 0
    for b in blocks:
        logger.info("=== Block %s ===", b)
        n = run_block(b, dry_run=args.dry_run)
        grand_total += n
    logger.info(
        "done. %d rows %s across %d block(s)",
        grand_total,
        "would-upsert" if args.dry_run else "upserted",
        len(blocks),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
