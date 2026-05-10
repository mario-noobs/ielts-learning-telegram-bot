from typing import Literal

from pydantic import BaseModel, Field

Locale = Literal["en", "vi"]


class UserCreate(BaseModel):
    name: str
    target_band: float = 7.0
    topics: list[str] = ["education", "environment", "technology"]


class LinkCodeRequest(BaseModel):
    code: str


class UserProfile(BaseModel):
    id: str
    name: str
    email: str | None = None
    target_band: float
    topics: list[str]
    streak: int = 0
    total_words: int = 0
    total_quizzes: int = 0
    total_correct: int = 0
    challenge_wins: int = 0
    exam_date: str | None = None
    weekly_goal_minutes: int = 150
    preferred_locale: Locale | None = None

    # Admin fields. Surfaced through /api/v1/me so the web app's
    # useProfile() hook can gate /admin routes and the AppShell's
    # admin nav entry. Defaults match the M11.1 schema defaults so
    # pre-cutover Firestore docs that lack these keys still validate.
    role: str = "user"
    plan: str = "free"
    plan_expires_at: str | None = None
    team_id: str | None = None
    org_id: str | None = None
    quota_override: int | None = None

    # US-M14.1: scheduling fields surfaced for /settings Practice tab.
    # `daily_time` is local clock string `HH:MM`; `timezone` is IANA.
    daily_time: str | None = None
    timezone: str | None = None

    # #242: editable from /settings Practice tab + dismissable onboarding.
    daily_words_count: int = 5
    dismissed_onboarding: bool = False

    # #dashboard-polish: stamped to true by PATCH /me when the user
    # explicitly submits the corresponding field. Surfaces in the
    # response so the dashboard ReadinessTrack sub-tasks tick once the
    # user has actually configured these — not from the row defaults.
    target_band_set: bool = False
    weekly_goal_set: bool = False


class AiUsageFeaturePoint(BaseModel):
    """One feature's count in today's per-user usage breakdown."""

    feature: str
    count: int


class MeAiUsage(BaseModel):
    """Response model for ``GET /api/v1/me/ai-usage`` (US-M13.1)."""

    plan: str
    quota_daily: int
    used_today: int
    by_feature: list[AiUsageFeaturePoint]
    reset_at: str  # ISO timestamp at next UTC midnight


class AiUsageHistoryPoint(BaseModel):
    """One (date, feature, count) row in the per-user history (US-M13.4).

    Used by ``GET /api/v1/me/ai-usage/history?days=N`` to back the
    ``/settings/usage`` page's 30-day chart and history table.
    """

    date: str  # ISO date (YYYY-MM-DD)
    feature: str
    count: int


class StudyWeekFeaturePoint(BaseModel):
    """One row in ``GET /api/v1/me/study-week``'s feature breakdown."""

    feature: str
    count: int
    minutes: int


class MeStudyWeek(BaseModel):
    """Response for ``GET /api/v1/me/study-week`` (US-M14.3).

    Completion-event proxy — minutes are estimated from per-feature
    constants (``MINUTES_PER_FEATURE``), not measured directly.
    """

    minutes_actual: int
    minutes_goal: int
    by_feature: list[StudyWeekFeaturePoint]
    week_start: str  # ISO datetime at Monday 00:00 UTC


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    target_band: float | None = Field(default=None, ge=4.0, le=9.0)
    topics: list[str] | None = None
    exam_date: str | None = Field(
        default=None,
        description="ISO date (YYYY-MM-DD) or empty string to clear",
    )
    weekly_goal_minutes: int | None = Field(default=None, ge=30, le=2000)
    preferred_locale: Locale | None = None
    # US-M14.1: editable from /settings Practice tab.
    daily_time: str | None = Field(
        default=None,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="HH:MM 24-hour local time, or empty string to clear",
    )
    timezone: str | None = Field(
        default=None,
        max_length=64,
        description="IANA timezone, e.g. Asia/Ho_Chi_Minh",
    )
    # #242: not validated at the Pydantic layer so an out-of-range value
    # surfaces as a domain ApiError (`users.daily_words_count.out_of_range`)
    # the web UI can localize, instead of a generic 422.
    daily_words_count: int | None = None
    dismissed_onboarding: bool | None = None


# ─── US-M12.2 token deep-link models ─────────────────────────────────

class LinkTokenRedeemRequest(BaseModel):
    """Body for ``POST /api/v1/link/redeem``."""

    token: str


class LinkStartResponse(BaseModel):
    """Response for ``POST /api/v1/link/start`` — web→TG deep-link."""

    token: str
    bot_deep_link: str
    expires_at: str


class LinkRedeemMergeCounts(BaseModel):
    """Subcollection-merge stats echoed back to the web UI for sub-case B."""

    vocab_merged: int = 0
    vocab_dropped: int = 0
    quiz_merged: int = 0
    writing_merged: int = 0
    daily_merged: int = 0
    daily_skipped: int = 0


class LinkRedeemResponse(BaseModel):
    """Response for ``POST /api/v1/link/redeem``.

    ``status`` is ``"linked"`` (sub-case A), ``"merged"`` (B), or
    ``"already_linked"`` (C). ``counts`` is non-null only when
    ``status == "merged"``.
    """

    status: Literal["linked", "merged", "already_linked"]
    profile: UserProfile
    counts: LinkRedeemMergeCounts | None = None
