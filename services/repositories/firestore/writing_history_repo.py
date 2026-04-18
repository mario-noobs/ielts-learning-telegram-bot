"""Firestore implementation of ``WritingHistoryRepo``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from firebase_admin import firestore

from ..dtos import WritingHistoryEntry
from ..protocols import UserId
from .user_repo import _get_db


def _history_col(user_id: UserId):
    return (_get_db().collection("users").document(str(user_id))
            .collection("writing_history"))


class FirestoreWritingHistoryRepo:
    """Firestore-backed ``WritingHistoryRepo``."""

    def save(self, user_id: UserId, writing_data: dict) -> None:
        now = datetime.now(timezone.utc)
        doc = {**writing_data, "created_at": now}
        _history_col(user_id).document().set(doc)

    def save_submission(self, user_id: UserId, writing_data: dict) -> str:
        now = datetime.now(timezone.utc)
        doc = {**writing_data, "created_at": now}
        ref = _history_col(user_id).document()
        ref.set(doc)
        return ref.id

    def get_submission(
        self, user_id: UserId, submission_id: str,
    ) -> Optional[WritingHistoryEntry]:
        doc = _history_col(user_id).document(submission_id).get()
        if not doc.exists:
            return None
        return WritingHistoryEntry.from_snapshot(doc)

    def list_submissions(
        self, user_id: UserId, limit: int = 50,
    ) -> list[WritingHistoryEntry]:
        docs = (_history_col(user_id)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream())
        return [WritingHistoryEntry.from_snapshot(d) for d in docs]


__all__ = ["FirestoreWritingHistoryRepo"]
