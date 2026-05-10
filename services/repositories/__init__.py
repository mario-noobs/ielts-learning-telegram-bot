"""Repository package — Protocol + DTO layer over user-scoped storage.

Post-M8-cutover (#234): the canonical implementations are Postgres for
all user-scoped data. The Firestore impls are kept import-able for the
30-day read-only archive but no factory returns them by default.

Typical usage::

    from services.repositories import get_user_repo

    user = get_user_repo().get(telegram_id)

The factories below return module-level singletons — they match the
lazy-init style already used by ``services.firebase_service._get_db``
and avoid introducing a DI framework for this refactor.
"""

from __future__ import annotations

from .dtos import (
    AiUsageDoc,
    AuditLogDoc,
    DailyWordsDoc,
    LinkTokenDoc,
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
    LinkTokenRepo,
    ListeningHistoryRepo,
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
_listening_history_repo: ListeningHistoryRepo | None = None
_groups_repo = None
_group_daily_words_repo = None
_group_challenges_repo = None
_group_challenge_answers_repo = None
_quiz_sessions_repo = None
_reading_sessions_repo = None
_plan_repo: PlanRepo | None = None
_team_repo: TeamRepo | None = None
_org_repo: OrgRepo | None = None
_audit_log_repo: AuditLogRepo | None = None
_ai_usage_repo: AiUsageRepo | None = None
_metrics_repo: MetricsRepo | None = None
_link_token_repo: LinkTokenRepo | None = None


def get_user_repo() -> UserRepo:
    """Postgres-backed user core doc repo."""
    global _user_repo
    if _user_repo is None:
        from .postgres.user_repo import PostgresUserRepo
        _user_repo = PostgresUserRepo()
    return _user_repo


def get_vocab_repo() -> VocabRepo:
    """Postgres-backed vocab repo (M8 cutover)."""
    global _vocab_repo
    if _vocab_repo is None:
        from .postgres.vocab_repo import PostgresVocabRepo
        _vocab_repo = PostgresVocabRepo()
    return _vocab_repo


def get_quiz_history_repo() -> QuizHistoryRepo:
    """Postgres-backed quiz history repo (M8 cutover)."""
    global _quiz_history_repo
    if _quiz_history_repo is None:
        from .postgres.quiz_history_repo import PostgresQuizHistoryRepo
        _quiz_history_repo = PostgresQuizHistoryRepo()
    return _quiz_history_repo


def get_writing_history_repo() -> WritingHistoryRepo:
    """Postgres-backed writing history repo (M8 cutover)."""
    global _writing_history_repo
    if _writing_history_repo is None:
        from .postgres.writing_history_repo import PostgresWritingHistoryRepo
        _writing_history_repo = PostgresWritingHistoryRepo()
    return _writing_history_repo


def get_daily_words_repo() -> DailyWordsRepo:
    """Postgres-backed personal daily words repo (M8 cutover)."""
    global _daily_words_repo
    if _daily_words_repo is None:
        from .postgres.daily_words_repo import PostgresDailyWordsRepo
        _daily_words_repo = PostgresDailyWordsRepo()
    return _daily_words_repo


def get_listening_history_repo() -> ListeningHistoryRepo:
    """Postgres-backed listening history repo (M8 cutover, new in #234)."""
    global _listening_history_repo
    if _listening_history_repo is None:
        from .postgres.listening_history_repo import PostgresListeningHistoryRepo
        _listening_history_repo = PostgresListeningHistoryRepo()
    return _listening_history_repo


def get_groups_repo():
    """Postgres-backed group settings + membership repo (M8 Block B)."""
    global _groups_repo
    if _groups_repo is None:
        from .postgres.groups_repo import PostgresGroupsRepo
        _groups_repo = PostgresGroupsRepo()
    return _groups_repo


def get_group_daily_words_repo():
    """Postgres-backed group daily-words repo (M8 Block B)."""
    global _group_daily_words_repo
    if _group_daily_words_repo is None:
        from .postgres.groups_repo import PostgresGroupDailyWordsRepo
        _group_daily_words_repo = PostgresGroupDailyWordsRepo()
    return _group_daily_words_repo


def get_group_challenges_repo():
    """Postgres-backed group challenges repo (M8 Block B)."""
    global _group_challenges_repo
    if _group_challenges_repo is None:
        from .postgres.groups_repo import PostgresGroupChallengesRepo
        _group_challenges_repo = PostgresGroupChallengesRepo()
    return _group_challenges_repo


def get_group_challenge_answers_repo():
    """Postgres-backed group challenge answers repo (M8 Block B)."""
    global _group_challenge_answers_repo
    if _group_challenge_answers_repo is None:
        from .postgres.groups_repo import PostgresGroupChallengeAnswersRepo
        _group_challenge_answers_repo = PostgresGroupChallengeAnswersRepo()
    return _group_challenge_answers_repo


def get_quiz_sessions_repo():
    """Postgres-backed bot quiz session repo (M8 Block C)."""
    global _quiz_sessions_repo
    if _quiz_sessions_repo is None:
        from .postgres.sessions_repo import PostgresQuizSessionsRepo
        _quiz_sessions_repo = PostgresQuizSessionsRepo()
    return _quiz_sessions_repo


def get_reading_sessions_repo():
    """Postgres-backed reading-lab session repo (M8 Block C)."""
    global _reading_sessions_repo
    if _reading_sessions_repo is None:
        from .postgres.sessions_repo import PostgresReadingSessionsRepo
        _reading_sessions_repo = PostgresReadingSessionsRepo()
    return _reading_sessions_repo


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


def get_link_token_repo() -> LinkTokenRepo:
    """Return the process-wide ``LinkTokenRepo`` singleton (Postgres-backed)."""
    global _link_token_repo
    if _link_token_repo is None:
        from services.repositories.postgres.link_token_repo import (
            PostgresLinkTokenRepo,
        )
        _link_token_repo = PostgresLinkTokenRepo()
    return _link_token_repo


def _reset_singletons_for_tests() -> None:
    """Test-only hook to clear cached repos. Don't call from app code."""
    global _user_repo, _vocab_repo, _quiz_history_repo
    global _writing_history_repo, _daily_words_repo, _listening_history_repo
    global _groups_repo, _group_daily_words_repo
    global _group_challenges_repo, _group_challenge_answers_repo
    global _quiz_sessions_repo, _reading_sessions_repo
    global _plan_repo, _team_repo, _org_repo, _audit_log_repo
    global _ai_usage_repo, _metrics_repo, _link_token_repo
    _user_repo = None
    _vocab_repo = None
    _quiz_history_repo = None
    _writing_history_repo = None
    _daily_words_repo = None
    _listening_history_repo = None
    _groups_repo = None
    _group_daily_words_repo = None
    _group_challenges_repo = None
    _group_challenge_answers_repo = None
    _quiz_sessions_repo = None
    _reading_sessions_repo = None
    _plan_repo = None
    _team_repo = None
    _org_repo = None
    _audit_log_repo = None
    _ai_usage_repo = None
    _metrics_repo = None
    _link_token_repo = None


__all__ = [
    # Protocols
    "UserId",
    "UserRepo",
    "VocabRepo",
    "QuizHistoryRepo",
    "WritingHistoryRepo",
    "DailyWordsRepo",
    "ListeningHistoryRepo",
    "PlanRepo",
    "TeamRepo",
    "OrgRepo",
    "AuditLogRepo",
    "AiUsageRepo",
    "MetricsRepo",
    "LinkTokenRepo",
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
    "LinkTokenDoc",
    # Firestore impls (kept for the 30-day archive — never returned by factories)
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
    "get_listening_history_repo",
    "get_groups_repo",
    "get_group_daily_words_repo",
    "get_group_challenges_repo",
    "get_group_challenge_answers_repo",
    "get_quiz_sessions_repo",
    "get_reading_sessions_repo",
    "get_plan_repo",
    "get_team_repo",
    "get_org_repo",
    "get_audit_log_repo",
    "get_ai_usage_repo",
    "get_metrics_repo",
    "get_link_token_repo",
]
