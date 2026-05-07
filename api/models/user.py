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
