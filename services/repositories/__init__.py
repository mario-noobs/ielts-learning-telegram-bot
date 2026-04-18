"""Repository package — Protocol + DTO layer over user-scoped storage.

This package is the seam between application code and the persistence
backend. Today the only implementation is Firestore (see the ``firestore``
subpackage). M8 (#130) will add a Postgres implementation behind the
same Protocols.

Typical usage::

    from services.repositories import get_user_repo

    user = get_user_repo().get(telegram_id)

The factories below return module-level singletons — they match the
lazy-init style already used by ``services.firebase_service._get_db``
and avoid introducing a DI framework for this refactor.

Scope reminder: group data (``groups/*`` and all subcollections) is NOT
covered here and stays on Firestore via ``services.firebase_service``.
"""

from __future__ import annotations

from .dtos import (
    DailyWordsDoc,
    QuizHistoryEntry,
    QuizStats,
    UserDoc,
    VocabularyItem,
    WritingHistoryEntry,
)
from .firestore import (
    FirestoreDailyWordsRepo,
    FirestoreQuizHistoryRepo,
    FirestoreUserRepo,
    FirestoreVocabRepo,
    FirestoreWritingHistoryRepo,
)
from .protocols import (
    DailyWordsRepo,
    QuizHistoryRepo,
    UserId,
    UserRepo,
    VocabRepo,
    WritingHistoryRepo,
)

# ─── Lazy singletons ─────────────────────────────────────────────────

_user_repo: UserRepo | None = None
_vocab_repo: VocabRepo | None = None
_quiz_history_repo: QuizHistoryRepo | None = None
_writing_history_repo: WritingHistoryRepo | None = None
_daily_words_repo: DailyWordsRepo | None = None


def get_user_repo() -> UserRepo:
    """Return the process-wide ``UserRepo`` singleton."""
    global _user_repo
    if _user_repo is None:
        _user_repo = FirestoreUserRepo()
    return _user_repo


def get_vocab_repo() -> VocabRepo:
    """Return the process-wide ``VocabRepo`` singleton."""
    global _vocab_repo
    if _vocab_repo is None:
        _vocab_repo = FirestoreVocabRepo()
    return _vocab_repo


def get_quiz_history_repo() -> QuizHistoryRepo:
    """Return the process-wide ``QuizHistoryRepo`` singleton."""
    global _quiz_history_repo
    if _quiz_history_repo is None:
        _quiz_history_repo = FirestoreQuizHistoryRepo()
    return _quiz_history_repo


def get_writing_history_repo() -> WritingHistoryRepo:
    """Return the process-wide ``WritingHistoryRepo`` singleton."""
    global _writing_history_repo
    if _writing_history_repo is None:
        _writing_history_repo = FirestoreWritingHistoryRepo()
    return _writing_history_repo


def get_daily_words_repo() -> DailyWordsRepo:
    """Return the process-wide ``DailyWordsRepo`` singleton."""
    global _daily_words_repo
    if _daily_words_repo is None:
        _daily_words_repo = FirestoreDailyWordsRepo()
    return _daily_words_repo


def _reset_singletons_for_tests() -> None:
    """Test-only hook to clear cached repos. Don't call from app code."""
    global _user_repo, _vocab_repo, _quiz_history_repo
    global _writing_history_repo, _daily_words_repo
    _user_repo = None
    _vocab_repo = None
    _quiz_history_repo = None
    _writing_history_repo = None
    _daily_words_repo = None


__all__ = [
    # Protocols
    "UserId",
    "UserRepo",
    "VocabRepo",
    "QuizHistoryRepo",
    "WritingHistoryRepo",
    "DailyWordsRepo",
    # DTOs
    "UserDoc",
    "QuizStats",
    "VocabularyItem",
    "QuizHistoryEntry",
    "WritingHistoryEntry",
    "DailyWordsDoc",
    # Firestore impls
    "FirestoreUserRepo",
    "FirestoreVocabRepo",
    "FirestoreQuizHistoryRepo",
    "FirestoreWritingHistoryRepo",
    "FirestoreDailyWordsRepo",
    # Factories
    "get_user_repo",
    "get_vocab_repo",
    "get_quiz_history_repo",
    "get_writing_history_repo",
    "get_daily_words_repo",
]
