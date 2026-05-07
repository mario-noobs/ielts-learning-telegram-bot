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


class FirestoreQuizHistoryRepo:
    """Firestore-backed ``QuizHistoryRepo``.

    ``save_result`` writes the answer doc to the Firestore subcollection
    and then bumps ``total_quizzes`` / ``total_correct`` on the parent
    user via ``UserRepo.increment_counters`` so the counters land in
    whichever store is authoritative for the user doc (Postgres
    post-US-M8.6). The two writes are not atomic across stores; same
    eventual-consistency window as before.
    """

    def save_result(self, user_id: UserId, quiz_data: dict) -> None:
        now = datetime.now(timezone.utc)
        doc = {**quiz_data, "created_at": now}
        _history_col(user_id).document().set(doc)

        from services.repositories import get_user_repo
        deltas: dict[str, int] = {"total_quizzes": 1}
        if quiz_data.get("is_correct"):
            deltas["total_correct"] = 1
        get_user_repo().increment_counters(user_id, **deltas)

    def get_latest(self, user_id: UserId) -> Optional[QuizHistoryEntry]:
        docs = (_history_col(user_id)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(1)
                .stream())
        results = [QuizHistoryEntry.from_snapshot(d) for d in docs]
        return results[0] if results else None


__all__ = ["FirestoreQuizHistoryRepo"]
