from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TeamSummary(BaseModel):
    id: str
    name: str
    owner_uid: str
    plan_id: str
    seat_limit: int
    member_count: int = 0
    my_role: Literal["owner", "admin", "member"] | None = None
    created_at: datetime | None = None


class TeamMeResponse(BaseModel):
    team: TeamSummary | None = None


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class TeamCreateResponse(BaseModel):
    team: TeamSummary


class TeamInviteCreateRequest(BaseModel):
    role: Literal["member", "admin"] = "member"


class TeamInviteCreateResponse(BaseModel):
    token: str
    invite_url: str
    expires_at: datetime


class TeamInvitePreviewResponse(BaseModel):
    team_id: str
    team_name: str
    expires_at: datetime
    member_count: int
    seat_limit: int
    already_member: bool = False


class TeamInviteAcceptResponse(BaseModel):
    team: TeamSummary


class TeamMemberSummary(BaseModel):
    user_id: str
    name: str = ""
    email: str | None = None
    role: Literal["owner", "admin", "member"]
    joined_at: datetime | None = None
    is_current_user: bool = False


class TeamMembersResponse(BaseModel):
    team: TeamSummary
    members: list[TeamMemberSummary]


class TeamMemberUpdateRequest(BaseModel):
    role: Literal["admin", "member"]


class TeamMemberUpdateResponse(BaseModel):
    member: TeamMemberSummary


class TeamOverviewResponse(BaseModel):
    week_start: datetime
    weekly_active_members: int = 0
    study_minutes: int = 0
    words_reviewed: int = 0
    words_mastered: int = 0
    quiz_count: int = 0
    member_count: int = 0
    seat_limit: int = 0


class TeamMemberProgressRow(BaseModel):
    user_id: str
    name: str = ""
    email: str | None = None
    role: Literal["owner", "admin", "member"]
    last_active_date: date | None = None
    weekly_minutes: int = 0
    words_reviewed: int = 0
    due_words: int = 0
    current_streak: int = 0


class TeamMemberProgressResponse(BaseModel):
    week_start: datetime
    members: list[TeamMemberProgressRow]
