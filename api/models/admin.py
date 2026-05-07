"""Pydantic schemas for ``/api/v1/admin/*`` (US-M11.3)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ─── Users ───────────────────────────────────────────────────────────


Role = Literal["user", "team_admin", "org_admin", "platform_admin"]


class AdminUserSummary(BaseModel):
    """One row in the ``GET /admin/users`` list."""

    id: str
    name: str
    email: Optional[str] = None
    auth_uid: Optional[str] = None
    role: str
    plan: str
    plan_expires_at: Optional[date] = None
    quota_override: Optional[int] = None
    last_active_date: Optional[date] = None
    created_at: Optional[datetime] = None


class AdminUsersListResponse(BaseModel):
    items: list[AdminUserSummary]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    """PATCH body for ``/admin/users/:id``. All fields optional."""

    role: Optional[Role] = None
    plan: Optional[str] = None
    plan_expires_at: Optional[date] = None
    quota_override: Optional[int] = Field(default=None, ge=0)


# ─── Plans ───────────────────────────────────────────────────────────


class AdminPlanRow(BaseModel):
    id: str
    name: str
    daily_ai_quota: int
    monthly_ai_quota: int
    max_team_seats: Optional[int] = None
    features: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class AdminPlanCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    daily_ai_quota: int = Field(..., ge=0)
    monthly_ai_quota: int = Field(..., ge=0)
    max_team_seats: Optional[int] = Field(default=None, ge=1)
    features: list[str] = Field(default_factory=list)


class AdminPlanUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    daily_ai_quota: Optional[int] = Field(default=None, ge=0)
    monthly_ai_quota: Optional[int] = Field(default=None, ge=0)
    max_team_seats: Optional[int] = Field(default=None, ge=1)
    features: Optional[list[str]] = None


# ─── Flags ───────────────────────────────────────────────────────────


class AdminFlagRow(BaseModel):
    name: str
    enabled: bool = False
    rollout_pct: int = 0
    uid_allowlist: list[str] = Field(default_factory=list)
    description: str = ""
    updated_at: Optional[datetime] = None


class AdminFlagUpsert(BaseModel):
    enabled: bool = False
    rollout_pct: int = Field(default=0, ge=0, le=100)
    uid_allowlist: list[str] = Field(default_factory=list)
    description: str = ""


# ─── Usage time series ───────────────────────────────────────────────


class AiUsagePoint(BaseModel):
    date: date
    feature: str
    count: int


class AdminUserUsageResponse(BaseModel):
    user_id: str
    days: int
    points: list[AiUsagePoint]


# ─── Generic ─────────────────────────────────────────────────────────


class AdminActionResponse(BaseModel):
    """Returned by mutating endpoints when a row body isn't useful."""

    ok: bool = True
    audit_log_id: Optional[int] = None
    extra: dict[str, Any] = Field(default_factory=dict)
