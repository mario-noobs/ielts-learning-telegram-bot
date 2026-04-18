"""Protocol interfaces for the user-scoped data repositories.

These Protocols define the contract any storage backend must satisfy.
Currently only a Firestore implementation exists (see
``services/repositories/firestore/``). In M8 (#130) a Postgres
implementation will be added behind these same Protocols so that the
bot and API can migrate user data without touching service code.

Scope (matches refinement 2026-04-18):
- ``users/{uid}`` profile doc
- ``users/{uid}/vocabulary`` SRS cards
- ``users/{uid}/quiz_history``
- ``users/{uid}/writing_history``
- ``users/{uid}/daily_words`` (DM personal words — NOT group words)

Group data (``groups/*`` and all its subcollections) is explicitly out
of scope. It stays on Firestore and keeps its direct access path
through ``services/firebase_service.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Union, runtime_checkable

from .dtos import (
    DailyWordsDoc,
    QuizHistoryEntry,
    QuizStats,
    UserDoc,
    VocabularyItem,
    WritingHistoryEntry,
)

# User ids are either a Telegram int or a ``web_<hex>`` string. Accept
# both at the Protocol boundary; impls coerce to ``str`` for Firestore
# and will coerce to the canonical type for Postgres in M8.
UserId = Union[int, str]


@runtime_checkable
class UserRepo(Protocol):
    """User profile operations over ``users/{uid}``."""

    def get(self, user_id: UserId) -> Optional[UserDoc]: ...

    def create(
        self,
        telegram_id: int,
        name: str,
        username: str = "",
        group_id: Optional[int] = None,
        target_band: float = 7.0,
        topics: Optional[list[str]] = None,
    ) -> UserDoc: ...

    def update(self, user_id: UserId, data: dict) -> None: ...

    def list_by_group(self, group_id: int) -> list[UserDoc]: ...

    def list_all(self) -> list[UserDoc]: ...

    def update_streak(self, user_id: UserId) -> None: ...

    def get_quiz_stats(self, user_id: UserId) -> QuizStats: ...

    # ── Web auth ──────────────────────────────────────────────────

    def get_by_auth_uid(self, auth_uid: str) -> Optional[UserDoc]: ...

    def create_web_user(
        self,
        auth_uid: str,
        email: str,
        name: str,
        target_band: float = 7.0,
        topics: Optional[list[str]] = None,
    ) -> UserDoc: ...

    def link_telegram_to_auth(self, telegram_id: int, auth_uid: str) -> None: ...


@runtime_checkable
class VocabRepo(Protocol):
    """Vocabulary card operations over ``users/{uid}/vocabulary``."""

    def add_word(self, user_id: UserId, word_data: dict) -> str: ...

    def add_word_if_not_exists(
        self, user_id: UserId, word_data: dict,
    ) -> tuple[str, bool]: ...

    def list_by_user(self, user_id: UserId, limit: int = 50) -> list[VocabularyItem]: ...

    def list_word_strings(self, user_id: UserId) -> list[str]: ...

    def list_page(
        self,
        user_id: UserId,
        limit: int = 20,
        after_added_at: Optional[datetime] = None,
    ) -> list[VocabularyItem]: ...

    def count_by_topic(self, user_id: UserId) -> dict[str, int]: ...

    def get_mastered(self, user_id: UserId) -> list[VocabularyItem]: ...

    def get_due(self, user_id: UserId, limit: int = 10) -> list[VocabularyItem]: ...

    def update_srs(self, user_id: UserId, word_id: str, data: dict) -> None: ...

    def get_by_id(self, user_id: UserId, word_id: str) -> Optional[VocabularyItem]: ...


@runtime_checkable
class QuizHistoryRepo(Protocol):
    """Quiz answer history over ``users/{uid}/quiz_history``.

    Writes here also atomically bump the parent user doc's
    ``total_quizzes`` / ``total_correct`` counters. The Postgres
    impl (M8) will wrap both writes in the same SQL transaction.
    """

    def save_result(self, user_id: UserId, quiz_data: dict) -> None: ...

    def get_latest(self, user_id: UserId) -> Optional[QuizHistoryEntry]: ...


@runtime_checkable
class WritingHistoryRepo(Protocol):
    """Writing submissions + feedback over ``users/{uid}/writing_history``."""

    def save(self, user_id: UserId, writing_data: dict) -> None: ...

    def save_submission(self, user_id: UserId, writing_data: dict) -> str: ...

    def get_submission(
        self, user_id: UserId, submission_id: str,
    ) -> Optional[WritingHistoryEntry]: ...

    def list_submissions(
        self, user_id: UserId, limit: int = 50,
    ) -> list[WritingHistoryEntry]: ...


@runtime_checkable
class DailyWordsRepo(Protocol):
    """Personal daily words over ``users/{uid}/daily_words/{date_str}``.

    Group daily words are out of scope (stay on Firestore).
    """

    def save(
        self, user_id: UserId, date_str: str, words: list, topic: str,
    ) -> None: ...

    def get(self, user_id: UserId, date_str: str) -> Optional[DailyWordsDoc]: ...


__all__ = [
    "UserId",
    "UserRepo",
    "VocabRepo",
    "QuizHistoryRepo",
    "WritingHistoryRepo",
    "DailyWordsRepo",
]
