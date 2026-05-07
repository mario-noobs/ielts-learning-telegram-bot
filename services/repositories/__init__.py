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
    AiUsageDoc,
    AuditLogDoc,
    DailyWordsDoc,
    OrgDoc,
    PlanDoc,
    PlatformMetricDoc,
    QuizHistoryEntry,
    QuizStats,
    TeamDoc,
    TeamMemberDoc,
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
    AiUsageRepo,
    AuditLogRepo,
    DailyWordsRepo,
    MetricsRepo,
    OrgRepo,
    PlanRepo,
    QuizHistoryRepo,
    TeamRepo,
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
_plan_repo: PlanRepo | None = None
_team_repo: TeamRepo | None = None
_org_repo: OrgRepo | None = None
_audit_log_repo: AuditLogRepo | None = None
_ai_usage_repo: AiUsageRepo | None = None
_metrics_repo: MetricsRepo | None = None


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


def get_plan_repo() -> PlanRepo:
    """Return the process-wide ``PlanRepo`` singleton (Postgres-backed)."""
    global _plan_repo
    if _plan_repo is None:
        from services.repositories.postgres.plan_repo import PostgresPlanRepo
        _plan_repo = PostgresPlanRepo()
    return _plan_repo


def get_team_repo() -> TeamRepo:
    """Return the process-wide ``TeamRepo`` singleton (Postgres-backed)."""
    global _team_repo
    if _team_repo is None:
        from services.repositories.postgres.team_repo import PostgresTeamRepo
        _team_repo = PostgresTeamRepo()
    return _team_repo


def get_org_repo() -> OrgRepo:
    """Return the process-wide ``OrgRepo`` singleton (Postgres-backed)."""
    global _org_repo
    if _org_repo is None:
        from services.repositories.postgres.org_repo import PostgresOrgRepo
        _org_repo = PostgresOrgRepo()
    return _org_repo


def get_audit_log_repo() -> AuditLogRepo:
    """Return the process-wide ``AuditLogRepo`` singleton (Postgres-backed)."""
    global _audit_log_repo
    if _audit_log_repo is None:
        from services.repositories.postgres.audit_repo import PostgresAuditLogRepo
        _audit_log_repo = PostgresAuditLogRepo()
    return _audit_log_repo


def get_ai_usage_repo() -> AiUsageRepo:
    """Return the process-wide ``AiUsageRepo`` singleton (Postgres-backed)."""
    global _ai_usage_repo
    if _ai_usage_repo is None:
        from services.repositories.postgres.ai_usage_repo import PostgresAiUsageRepo
        _ai_usage_repo = PostgresAiUsageRepo()
    return _ai_usage_repo


def get_metrics_repo() -> MetricsRepo:
    """Return the process-wide ``MetricsRepo`` singleton (Postgres-backed)."""
    global _metrics_repo
    if _metrics_repo is None:
        from services.repositories.postgres.metrics_repo import PostgresMetricsRepo
        _metrics_repo = PostgresMetricsRepo()
    return _metrics_repo


def _reset_singletons_for_tests() -> None:
    """Test-only hook to clear cached repos. Don't call from app code."""
    global _user_repo, _vocab_repo, _quiz_history_repo
    global _writing_history_repo, _daily_words_repo
    global _plan_repo, _team_repo, _org_repo, _audit_log_repo
    global _ai_usage_repo, _metrics_repo
    _user_repo = None
    _vocab_repo = None
    _quiz_history_repo = None
    _writing_history_repo = None
    _daily_words_repo = None
    _plan_repo = None
    _team_repo = None
    _org_repo = None
    _audit_log_repo = None
    _ai_usage_repo = None
    _metrics_repo = None


__all__ = [
    # Protocols
    "UserId",
    "UserRepo",
    "VocabRepo",
    "QuizHistoryRepo",
    "WritingHistoryRepo",
    "DailyWordsRepo",
    "PlanRepo",
    "TeamRepo",
    "OrgRepo",
    "AuditLogRepo",
    "AiUsageRepo",
    "MetricsRepo",
    # DTOs
    "UserDoc",
    "QuizStats",
    "VocabularyItem",
    "QuizHistoryEntry",
    "WritingHistoryEntry",
    "DailyWordsDoc",
    "PlanDoc",
    "TeamDoc",
    "TeamMemberDoc",
    "OrgDoc",
    "AuditLogDoc",
    "AiUsageDoc",
    "PlatformMetricDoc",
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
    "get_plan_repo",
    "get_team_repo",
    "get_org_repo",
    "get_audit_log_repo",
    "get_ai_usage_repo",
    "get_metrics_repo",
]
