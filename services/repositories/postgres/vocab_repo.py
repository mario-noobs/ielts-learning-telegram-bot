"""Postgres implementation of ``VocabRepo`` (M8 cutover)."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

import config
from services.db import get_sync_session
from services.db.models import Topic, User, UserVocabulary

from ..dtos import VocabularyItem
from ..protocols import UserId

_FALLBACK_TOPIC_SLUG = "society"
_PUNCT_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def _normalize(word: str) -> str:
    """NFC + lower + strip-punct dedupe key. Mirrors migrate_firestore_to_pg.py."""
    if not word:
        return ""
    s = unicodedata.normalize("NFC", word).lower().strip()
    s = _PUNCT_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


# Process-wide topic lookup. Built lazily on first query so importing
# this module doesn't require the DB to be reachable.
_TOPIC_LOOKUP: dict[str, int] = {}
_TOPIC_NAME_BY_ID: dict[int, str] = {}


def _ensure_topic_lookup() -> None:
    global _TOPIC_LOOKUP, _TOPIC_NAME_BY_ID
    if _TOPIC_LOOKUP:
        return
    with get_sync_session() as s:
        rows = s.execute(select(Topic.id, Topic.slug, Topic.name_en)).all()
    for tid, slug, name_en in rows:
        _TOPIC_LOOKUP[slug.lower()] = tid
        _TOPIC_LOOKUP[name_en.lower()] = tid  # tolerate display names too
        _TOPIC_NAME_BY_ID[tid] = slug


def _topic_id(raw: Optional[str]) -> int:
    """Resolve a topic input (slug or display name) to topic_id."""
    _ensure_topic_lookup()
    if not raw:
        return _TOPIC_LOOKUP[_FALLBACK_TOPIC_SLUG]
    key = raw.strip().lower()
    if key in _TOPIC_LOOKUP:
        return _TOPIC_LOOKUP[key]
    for k, v in _TOPIC_LOOKUP.items():
        if key.startswith(k) or k.startswith(key):
            return v
    return _TOPIC_LOOKUP[_FALLBACK_TOPIC_SLUG]


def _topic_slug(topic_id: int) -> str:
    _ensure_topic_lookup()
    return _TOPIC_NAME_BY_ID.get(topic_id, _FALLBACK_TOPIC_SLUG)


def _row_to_dto(row: UserVocabulary) -> VocabularyItem:
    """Hydrate a VocabularyItem DTO from a UserVocabulary row.

    DTO field ``topic`` is the slug (e.g. ``"technology"``), not the
    display name. Callers that need the localised display name fetch it
    from the i18n bundle keyed by slug.
    """
    return VocabularyItem(
        id=row.id,
        word=row.word,
        definition=row.definition_en,  # legacy alias
        definition_en=row.definition_en,
        definition_vi=row.definition_vi,
        ipa=row.ipa,
        part_of_speech=row.part_of_speech,
        topic=_topic_slug(row.topic_id),
        example_en=row.example_en,
        example_vi=row.example_vi,
        source=row.source,
        srs_interval=row.srs_interval,
        srs_ease=row.srs_ease,
        srs_reps=row.srs_reps,
        srs_next_review=row.srs_next_review,
        is_favourite=row.is_favourite,
        added_at=row.created_at,
    )


class PostgresVocabRepo:
    """Postgres-backed ``VocabRepo``. Sync API; matches the Protocol."""

    def add_word(self, user_id: UserId, word_data: dict) -> str:
        word = str(word_data.get("word", "")).strip()
        norm = _normalize(word)
        if not norm:
            raise ValueError("add_word: empty word")
        now = datetime.now(timezone.utc)
        word_id = uuid.uuid4().hex
        row = UserVocabulary(
            id=word_id,
            user_id=str(user_id),
            word=word,
            normalized_word=norm,
            topic_id=_topic_id(word_data.get("topic")),
            definition_en=str(word_data.get("definition_en") or word_data.get("definition") or ""),
            definition_vi=str(word_data.get("definition_vi") or ""),
            ipa=str(word_data.get("ipa") or ""),
            part_of_speech=str(word_data.get("part_of_speech") or ""),
            example_en=str(word_data.get("example_en") or word_data.get("example") or ""),
            example_vi=str(word_data.get("example_vi") or ""),
            user_note="",
            source=int(word_data.get("source") or 1),
            srs_interval=config.SRS_INITIAL_INTERVAL,
            srs_ease=config.SRS_INITIAL_EASE,
            srs_reps=0,
            srs_next_review=now,
            created_at=now,
            updated_at=now,
        )
        with get_sync_session() as s, s.begin():
            s.add(row)
        # Bump parent user's total_words counter (atomic, server-side).
        from services.repositories import get_user_repo
        get_user_repo().increment_counters(user_id, total_words=1)
        return word_id

    def add_word_if_not_exists(
        self, user_id: UserId, word_data: dict,
    ) -> tuple[str, bool]:
        """Atomic dedupe by ``normalized_word``. Returns ``(word_id, created)``.

        Race-free: relies on ``UNIQUE (user_id, normalized_word)`` from
        the 0006 migration. ``ON CONFLICT DO NOTHING`` handles concurrent
        inserts.
        """
        word = str(word_data.get("word", "")).strip()
        norm = _normalize(word)
        if not norm:
            raise ValueError("add_word_if_not_exists: empty word")
        now = datetime.now(timezone.utc)
        new_id = uuid.uuid4().hex
        with get_sync_session() as s, s.begin():
            stmt = pg_insert(UserVocabulary).values(
                id=new_id,
                user_id=str(user_id),
                word=word,
                normalized_word=norm,
                topic_id=_topic_id(word_data.get("topic")),
                definition_en=str(word_data.get("definition_en") or word_data.get("definition") or ""),
                definition_vi=str(word_data.get("definition_vi") or ""),
                ipa=str(word_data.get("ipa") or ""),
                part_of_speech=str(word_data.get("part_of_speech") or ""),
                example_en=str(word_data.get("example_en") or word_data.get("example") or ""),
                example_vi=str(word_data.get("example_vi") or ""),
                user_note="",
                source=int(word_data.get("source") or 1),
                srs_interval=config.SRS_INITIAL_INTERVAL,
                srs_ease=config.SRS_INITIAL_EASE,
                srs_reps=0,
                srs_next_review=now,
                created_at=now,
                updated_at=now,
            ).on_conflict_do_nothing(
                index_elements=["user_id", "normalized_word"],
            ).returning(UserVocabulary.id)
            inserted_id = s.execute(stmt).scalar_one_or_none()
            if inserted_id is not None:
                created = True
                word_id = inserted_id
            else:
                created = False
                word_id = s.execute(
                    select(UserVocabulary.id).where(
                        UserVocabulary.user_id == str(user_id),
                        UserVocabulary.normalized_word == norm,
                    )
                ).scalar_one()
        if created:
            from services.repositories import get_user_repo
            get_user_repo().increment_counters(user_id, total_words=1)
        return word_id, created

    def list_by_user(self, user_id: UserId, limit: int = 50) -> list[VocabularyItem]:
        with get_sync_session() as s:
            rows = s.execute(
                select(UserVocabulary)
                .where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.archived_at.is_(None),
                )
                .order_by(UserVocabulary.created_at.desc())
                .limit(limit)
            ).scalars().all()
        return [_row_to_dto(r) for r in rows]

    def list_word_strings(self, user_id: UserId) -> list[str]:
        with get_sync_session() as s:
            rows = s.execute(
                select(UserVocabulary.word)
                .where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.archived_at.is_(None),
                )
            ).scalars().all()
        return list(rows)

    def list_page(
        self,
        user_id: UserId,
        limit: int = 20,
        after_added_at: Optional[datetime] = None,
        topic: Optional[str] = None,
        favourite: Optional[bool] = None,
        source: Optional[int] = None,
    ) -> list[VocabularyItem]:
        conds = [
            UserVocabulary.user_id == str(user_id),
            UserVocabulary.archived_at.is_(None),
        ]
        if topic:
            conds.append(UserVocabulary.topic_id == _topic_id(topic))
        if favourite is True:
            conds.append(UserVocabulary.is_favourite == True)  # noqa: E712
        if source is not None:
            conds.append(UserVocabulary.source == source)
        if after_added_at is not None:
            conds.append(UserVocabulary.created_at < after_added_at)
        with get_sync_session() as s:
            rows = s.execute(
                select(UserVocabulary)
                .where(and_(*conds))
                .order_by(UserVocabulary.created_at.desc())
                .limit(limit)
            ).scalars().all()
        return [_row_to_dto(r) for r in rows]

    def count_by_topic(self, user_id: UserId) -> dict[str, int]:
        with get_sync_session() as s:
            rows = s.execute(
                select(UserVocabulary.topic_id, func.count(UserVocabulary.id))
                .where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.archived_at.is_(None),
                )
                .group_by(UserVocabulary.topic_id)
            ).all()
        return {_topic_slug(tid): cnt for tid, cnt in rows}

    def count_by_topic_with_mastery(
        self, user_id: UserId,
    ) -> dict[str, dict[str, int]]:
        """Per-topic ``{total, mastered}`` for /learn/vocab home cards.

        Mastered := srs_interval > 30 (matches services.srs_service rule).
        Single SQL query, no in-memory cache needed (PG can do this in <2ms).
        """
        with get_sync_session() as s:
            rows = s.execute(
                select(
                    UserVocabulary.topic_id,
                    func.count(UserVocabulary.id),
                    func.sum(
                        func.cast(UserVocabulary.srs_interval > 30, type_=__import__("sqlalchemy").Integer)
                    ),
                )
                .where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.archived_at.is_(None),
                )
                .group_by(UserVocabulary.topic_id)
            ).all()
        out: dict[str, dict[str, int]] = {}
        for tid, total, mastered in rows:
            out[_topic_slug(tid)] = {
                "total": int(total or 0),
                "mastered": int(mastered or 0),
            }
        return out

    def get_mastered(self, user_id: UserId) -> list[VocabularyItem]:
        with get_sync_session() as s:
            rows = s.execute(
                select(UserVocabulary)
                .where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.srs_interval > 30,
                    UserVocabulary.archived_at.is_(None),
                )
            ).scalars().all()
        return [_row_to_dto(r) for r in rows]

    def get_due(self, user_id: UserId, limit: int = 10) -> list[VocabularyItem]:
        now = datetime.now(timezone.utc)
        with get_sync_session() as s:
            rows = s.execute(
                select(UserVocabulary)
                .where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.srs_next_review <= now,
                    UserVocabulary.archived_at.is_(None),
                )
                .order_by(UserVocabulary.srs_next_review)
                .limit(limit)
            ).scalars().all()
        return [_row_to_dto(r) for r in rows]

    def update_srs(self, user_id: UserId, word_id: str, data: dict) -> None:
        # Map FS-shaped ``data`` to PG columns. Drop any unknown keys.
        allowed = {
            "srs_interval", "srs_ease", "srs_reps", "srs_next_review",
            "archived_at",
        }
        values = {k: v for k, v in data.items() if k in allowed}
        if "topic" in data:
            values["topic_id"] = _topic_id(data["topic"])
        if not values:
            return
        with get_sync_session() as s, s.begin():
            s.execute(
                update(UserVocabulary)
                .where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.id == word_id,
                )
                .values(**values),
            )

    def toggle_favourite(self, user_id: UserId, word_id: str, is_favourite: bool) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(
                update(UserVocabulary)
                .where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.id == word_id,
                )
                .values(is_favourite=is_favourite),
            )

    def get_favourite_words(self, user_id: UserId, limit: int = 10) -> list[str]:
        with get_sync_session() as s:
            rows = s.execute(
                select(UserVocabulary.word)
                .where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.is_favourite == True,  # noqa: E712
                    UserVocabulary.archived_at.is_(None),
                )
                .order_by(UserVocabulary.srs_reps.desc())
                .limit(limit)
            ).scalars().all()
        return list(rows)

    def get_by_id(self, user_id: UserId, word_id: str) -> Optional[VocabularyItem]:
        with get_sync_session() as s:
            row = s.execute(
                select(UserVocabulary).where(
                    UserVocabulary.user_id == str(user_id),
                    UserVocabulary.id == word_id,
                )
            ).scalar_one_or_none()
        return _row_to_dto(row) if row else None


__all__ = ["PostgresVocabRepo"]
