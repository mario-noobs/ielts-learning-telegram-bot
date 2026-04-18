"""Firestore implementation of ``QuizHistoryRepo``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from firebase_admin import firestore

from ..dtos import QuizHistoryEntry
from ..protocols import UserId
from .user_repo import _get_db


def _history_col(user_id: UserId):
    return (_get_db().collection("users").document(str(user_id))
            .collection("quiz_history"))


def _user_ref(user_id: UserId):
    return _get_db().collection("users").document(str(user_id))


class FirestoreQuizHistoryRepo:
    """Firestore-backed ``QuizHistoryRepo``.

    ``save_result`` writes the answer doc AND bumps the parent user
    doc's ``total_quizzes`` / ``total_correct`` counters in a single
    ``update`` call with ``Increment``. The two writes are not
    atomic today (same as the current behavior) — the Postgres impl
    (M8) will wrap them in a single SQL transaction.
    """

    def save_result(self, user_id: UserId, quiz_data: dict) -> None:
        now = datetime.now(timezone.utc)
        doc = {**quiz_data, "created_at": now}
        _history_col(user_id).document().set(doc)

        update_data: dict = {"total_quizzes": firestore.Increment(1)}
        if quiz_data.get("is_correct"):
            update_data["total_correct"] = firestore.Increment(1)
        _user_ref(user_id).update(update_data)

    def get_latest(self, user_id: UserId) -> Optional[QuizHistoryEntry]:
        docs = (_history_col(user_id)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(1)
                .stream())
        results = [QuizHistoryEntry.from_snapshot(d) for d in docs]
        return results[0] if results else None


__all__ = ["FirestoreQuizHistoryRepo"]
