"""Firestore implementation of ``DailyWordsRepo`` (user scope only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..dtos import DailyWordsDoc
from ..protocols import UserId
from .user_repo import _get_db


def _daily_col(user_id: UserId):
    return (_get_db().collection("users").document(str(user_id))
            .collection("daily_words"))


class FirestoreDailyWordsRepo:
    """Firestore-backed ``DailyWordsRepo``.

    Handles only ``users/{uid}/daily_words/{date_str}``. Group daily
    words (``groups/{gid}/daily_words``) stay on Firestore permanently
    and are reached directly via ``services/firebase_service.py``.
    """

    def save(
        self, user_id: UserId, date_str: str, words: list, topic: str,
    ) -> None:
        doc = {
            "words": words,
            "topic": topic,
            "generated_at": datetime.now(timezone.utc),
        }
        _daily_col(user_id).document(date_str).set(doc)

    def get(self, user_id: UserId, date_str: str) -> Optional[DailyWordsDoc]:
        doc = _daily_col(user_id).document(date_str).get()
        if not doc.exists:
            return None
        # Document id IS the date string — inject it as the DTO id.
        return DailyWordsDoc.model_validate({"id": date_str, **(doc.to_dict() or {})})


__all__ = ["FirestoreDailyWordsRepo"]
