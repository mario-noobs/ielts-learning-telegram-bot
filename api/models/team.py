from __future__ import annotations

from datetime import datetime
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
