from __future__ import annotations

import base64
import json
from typing import Any

from sqlalchemy import and_, func, select

from services.db import get_sync_session
from services.db.models import Topic, VocabularyMaster

PUBLIC_POOL_STATUSES = ("active", "candidate")
TITLE_ACRONYMS = {"ielts": "IELTS", "cefr": "CEFR"}


def encode_pool_id(source: str, source_theme: str) -> str:
    raw = json.dumps([source or "", source_theme or ""], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_pool_id(pool_id: str) -> tuple[str, str]:
    try:
        padded = pool_id + "=" * (-len(pool_id) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        source, source_theme = json.loads(decoded)
    except Exception as exc:  # noqa: BLE001 - invalid user supplied id
        raise ValueError("Invalid public vocab pool id") from exc
    return str(source), str(source_theme)


def _pool_title(source: str, source_theme: str) -> str:
    title = (source_theme or source or "Public vocabulary").replace("_", " ").strip()
    if not title:
        return "Public Vocabulary"
    words = []
    for word in title.split():
        words.append(TITLE_ACRONYMS.get(word.lower(), word.capitalize()))
    return " ".join(words)


def _pool_row_to_dict(row: Any) -> dict:
    source = row.source or ""
    source_theme = row.source_theme or ""
    difficulty_avg = row.difficulty_avg
    difficulty = int(round(float(difficulty_avg))) if difficulty_avg is not None else None
    topics = [t for t in (row.topics or []) if t]
    return {
        "id": encode_pool_id(source, source_theme),
        "title": _pool_title(source, source_theme),
        "source": source,
        "source_theme": source_theme,
        "word_count": int(row.word_count or 0),
        "difficulty": difficulty,
        "difficulty_min": int(row.difficulty_min) if row.difficulty_min is not None else None,
        "difficulty_max": int(row.difficulty_max) if row.difficulty_max is not None else None,
        "topics": sorted(set(topics)),
        "source_url": row.source_url or "",
        "license": row.license or "",
        "provenance": row.source_ref or source,
    }


def _word_row_to_dict(row: Any) -> dict:
    word = row.VocabularyMaster
    return {
        "id": word.id,
        "word": word.word,
        "definition_en": word.definition_en,
        "definition_vi": word.definition_vi,
        "ipa": word.ipa,
        "part_of_speech": word.part_of_speech,
        "example_en": word.example_en,
        "example_vi": word.example_vi,
        "difficulty": word.difficulty,
        "topic": row.topic_slug or "",
        "source_ref": word.source_ref,
    }


def list_public_pools(
    *,
    difficulty: int | None = None,
    topic: str | None = None,
) -> list[dict]:
    source_expr = func.coalesce(VocabularyMaster.source, "")
    theme_expr = func.coalesce(VocabularyMaster.source_theme, "")
    conds = [VocabularyMaster.status.in_(PUBLIC_POOL_STATUSES)]
    if difficulty is not None:
        conds.append(VocabularyMaster.difficulty == difficulty)
    if topic:
        conds.append(Topic.slug == topic)

    with get_sync_session() as session:
        rows = session.execute(
            select(
                source_expr.label("source"),
                theme_expr.label("source_theme"),
                func.count(VocabularyMaster.id).label("word_count"),
                func.avg(VocabularyMaster.difficulty).label("difficulty_avg"),
                func.min(VocabularyMaster.difficulty).label("difficulty_min"),
                func.max(VocabularyMaster.difficulty).label("difficulty_max"),
                func.array_agg(func.distinct(Topic.slug)).label("topics"),
                func.min(VocabularyMaster.source_url).label("source_url"),
                func.min(VocabularyMaster.license).label("license"),
                func.min(VocabularyMaster.source_ref).label("source_ref"),
            )
            .select_from(VocabularyMaster)
            .join(Topic, Topic.id == VocabularyMaster.topic_id, isouter=True)
            .where(and_(*conds))
            .group_by(source_expr, theme_expr)
            .order_by(
                func.coalesce(func.avg(VocabularyMaster.difficulty), 5),
                source_expr,
                theme_expr,
            )
        ).all()
    return [_pool_row_to_dict(row) for row in rows]


def get_public_pool_detail(
    pool_id: str,
    *,
    difficulty: int | None = None,
    topic: str | None = None,
    limit: int = 100,
) -> dict | None:
    source, source_theme = decode_pool_id(pool_id)
    conds = [
        VocabularyMaster.status.in_(PUBLIC_POOL_STATUSES),
        func.coalesce(VocabularyMaster.source, "") == source,
        func.coalesce(VocabularyMaster.source_theme, "") == source_theme,
    ]
    if difficulty is not None:
        conds.append(VocabularyMaster.difficulty == difficulty)
    if topic:
        conds.append(Topic.slug == topic)

    pools = list_public_pools(difficulty=difficulty, topic=topic)
    pool = next((p for p in pools if p["id"] == pool_id), None)
    if pool is None:
        return None

    with get_sync_session() as session:
        rows = session.execute(
            select(VocabularyMaster, Topic.slug.label("topic_slug"))
            .join(Topic, Topic.id == VocabularyMaster.topic_id, isouter=True)
            .where(and_(*conds))
            .order_by(
                func.coalesce(VocabularyMaster.difficulty, 5),
                VocabularyMaster.word,
            )
            .limit(limit)
        ).all()

    words = [_word_row_to_dict(row) for row in rows]
    return {"pool": pool, "words": words}


def get_public_pool_word(pool_id: str, word_id: str) -> dict | None:
    source, source_theme = decode_pool_id(pool_id)
    conds = [
        VocabularyMaster.status.in_(PUBLIC_POOL_STATUSES),
        VocabularyMaster.id == word_id,
        func.coalesce(VocabularyMaster.source, "") == source,
        func.coalesce(VocabularyMaster.source_theme, "") == source_theme,
    ]

    with get_sync_session() as session:
        row = session.execute(
            select(VocabularyMaster, Topic.slug.label("topic_slug"))
            .join(Topic, Topic.id == VocabularyMaster.topic_id, isouter=True)
            .where(and_(*conds))
            .limit(1)
        ).first()

    return _word_row_to_dict(row) if row else None
