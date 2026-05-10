"""Re-export models so Alembic autogenerate sees their metadata."""

from services.db.models.ai_routing import AiProviderUsage, AiRoutingConfig
from services.db.models.ai_usage import AiUsage
from services.db.models.audit_log import AuditLog
from services.db.models.content import (
    AuthLinkCode,
    EnrichedWord,
    FeatureFlag,
    ReadingQuestion,
)
from services.db.models.groups import (
    Group,
    GroupChallenge,
    GroupChallengeAnswer,
    GroupDailyWords,
    GroupMember,
)
from services.db.models.history import (
    ListeningHistory,
    QuizHistory,
    UserDailyWords,
    WritingHistory,
)
from services.db.models.link_token import LinkToken
from services.db.models.org import Org, OrgAdmin, OrgTeam
from services.db.models.plan import Plan
from services.db.models.platform_metric import PlatformMetric
from services.db.models.progress import (
    DailyPlan,
    DailyReviewSnapshot,
    ProgressRecommendation,
    ProgressSnapshot,
)
from services.db.models.sessions import QuizSession, ReadingSession
from services.db.models.team import Team, TeamMember
from services.db.models.user import User
from services.db.models.vocabulary import ReviewEvent, Topic, UserVocabulary

__all__ = [
    "AiProviderUsage",
    "AiRoutingConfig",
    "AiUsage",
    "AuditLog",
    "AuthLinkCode",
    "DailyPlan",
    "DailyReviewSnapshot",
    "EnrichedWord",
    "FeatureFlag",
    "Group",
    "GroupChallenge",
    "GroupChallengeAnswer",
    "GroupDailyWords",
    "GroupMember",
    "LinkToken",
    "ListeningHistory",
    "Org",
    "OrgAdmin",
    "OrgTeam",
    "Plan",
    "PlatformMetric",
    "ProgressRecommendation",
    "ProgressSnapshot",
    "QuizHistory",
    "QuizSession",
    "ReadingQuestion",
    "ReadingSession",
    "ReviewEvent",
    "Team",
    "TeamMember",
    "Topic",
    "User",
    "UserDailyWords",
    "UserVocabulary",
    "WritingHistory",
]
