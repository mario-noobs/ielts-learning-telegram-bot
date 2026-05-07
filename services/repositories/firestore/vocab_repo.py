"""Firestore implementation of ``VocabRepo``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from firebase_admin import firestore

import config

from ..dtos import VocabularyItem
from ..protocols import UserId
from .user_repo import _get_db


def _vocab_col(user_id: UserId):
    return (_get_db().collection("users").document(str(user_id))
            .collection("vocabulary"))


class FirestoreVocabRepo:
    """Firestore-backed ``VocabRepo``.

    SRS mutations (``update_srs``) touch only the vocab subcollection.
    Word adds also bump ``total_words`` on the parent user, via
    ``UserRepo.increment_counters`` so the counter lands in whichever
    store is authoritative for the user doc (Postgres post-US-M8.6).
    The dedupe + write portion stays inside the Firestore transaction;
    the counter increment runs after the txn commits.
    """

    def add_word(self, user_id: UserId, word_data: dict) -> str:
        now = datetime.now(timezone.utc)
        word_doc = {
            **word_data,
            "srs_interval": config.SRS_INITIAL_INTERVAL,
            "srs_ease": config.SRS_INITIAL_EASE,
            "srs_next_review": now,
            "srs_reps": 0,
            "times_correct": 0,
            "times_incorrect": 0,
            "added_at": now,
        }
        doc_ref = _vocab_col(user_id).document()
        doc_ref.set(word_doc)
        from services.repositories import get_user_repo
        get_user_repo().increment_counters(user_id, total_words=1)
        return doc_ref.id

    def add_word_if_not_exists(
        self, user_id: UserId, word_data: dict,
    ) -> tuple[str, bool]:
        """Atomic dedupe by lowercased ``word``.

        Returns ``(word_id, created)``. When ``created`` is False, no
        counter is incremented and the existing doc id is returned.
        """
        db = _get_db()
        word = str(word_data.get("word", "")).strip().lower()
        vocab_ref = _vocab_col(user_id)

        @firestore.transactional
        def _txn(txn) -> tuple[str, bool]:
            existing = list(
                vocab_ref.where("word", "==", word).limit(1).get(transaction=txn)
            )
            if existing:
                return existing[0].id, False

            doc_ref = vocab_ref.document()
            now = datetime.now(timezone.utc)
            txn.set(doc_ref, {
                **word_data,
                "word": word,
                "srs_interval": config.SRS_INITIAL_INTERVAL,
                "srs_ease": config.SRS_INITIAL_EASE,
                "srs_next_review": now,
                "srs_reps": 0,
                "times_correct": 0,
                "times_incorrect": 0,
                "added_at": now,
            })
            return doc_ref.id, True

        word_id, created = _txn(db.transaction())
        if created:
            from services.repositories import get_user_repo
            get_user_repo().increment_counters(user_id, total_words=1)
        return word_id, created

    def list_by_user(self, user_id: UserId, limit: int = 50) -> list[VocabularyItem]:
        docs = (_vocab_col(user_id)
                .order_by("added_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream())
        return [VocabularyItem.from_snapshot(d) for d in docs]

    def list_word_strings(self, user_id: UserId) -> list[str]:
        docs = _vocab_col(user_id).stream()
        return [(d.to_dict() or {}).get("word", "") for d in docs]

    def list_page(
        self,
        user_id: UserId,
        limit: int = 20,
        after_added_at: Optional[datetime] = None,
    ) -> list[VocabularyItem]:
        query = (_vocab_col(user_id)
                 .order_by("added_at", direction=firestore.Query.DESCENDING))
        if after_added_at is not None:
            query = query.start_after({"added_at": after_added_at})
        docs = query.limit(limit).stream()
        return [VocabularyItem.from_snapshot(d) for d in docs]

    def count_by_topic(self, user_id: UserId) -> dict[str, int]:
        docs = _vocab_col(user_id).stream()
        counts: dict[str, int] = {}
        for d in docs:
            topic = (d.to_dict() or {}).get("topic") or ""
            if not topic:
                continue
            counts[topic] = counts.get(topic, 0) + 1
        return counts

    def get_mastered(self, user_id: UserId) -> list[VocabularyItem]:
        docs = (_vocab_col(user_id)
                .where("srs_interval", ">", 30)
                .stream())
        return [VocabularyItem.from_snapshot(d) for d in docs]

    def get_due(self, user_id: UserId, limit: int = 10) -> list[VocabularyItem]:
        now = datetime.now(timezone.utc)
        docs = (_vocab_col(user_id)
                .where("srs_next_review", "<=", now)
                .limit(limit)
                .stream())
        return [VocabularyItem.from_snapshot(d) for d in docs]

    def update_srs(self, user_id: UserId, word_id: str, data: dict) -> None:
        _vocab_col(user_id).document(word_id).update(data)

    def get_by_id(self, user_id: UserId, word_id: str) -> Optional[VocabularyItem]:
        doc = _vocab_col(user_id).document(word_id).get()
        if not doc.exists:
            return None
        return VocabularyItem.from_snapshot(doc)


__all__ = ["FirestoreVocabRepo"]
