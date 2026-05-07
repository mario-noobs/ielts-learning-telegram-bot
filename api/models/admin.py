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


# ─── Teams (US-M11.4) ────────────────────────────────────────────────


class AdminTeamSummary(BaseModel):
    id: str
    name: str
    owner_uid: str
    plan_id: str
    plan_expires_at: Optional[date] = None
    seat_limit: int
    created_by: str
    created_at: Optional[datetime] = None
    member_count: int = 0


class AdminTeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    owner_uid: str = Field(..., min_length=1)
    plan_id: str = Field(..., min_length=1)
    seat_limit: int = Field(..., ge=1, le=10000)


class AdminTeamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    plan_id: Optional[str] = None
    plan_expires_at: Optional[date] = None
    seat_limit: Optional[int] = Field(default=None, ge=1, le=10000)


class AdminTeamMemberRow(BaseModel):
    user_uid: str
    role: str  # 'member' | 'admin'
    joined_at: Optional[datetime] = None


class AdminTeamMemberAdd(BaseModel):
    user_uid: str = Field(..., min_length=1)
    role: Literal["member", "admin"] = "member"


# ─── Orgs (US-M11.4) ─────────────────────────────────────────────────


class AdminOrgSummary(BaseModel):
    id: str
    name: str
    owner_uid: str
    plan_id: str
    plan_expires_at: Optional[date] = None
    created_at: Optional[datetime] = None
    admin_count: int = 0
    team_count: int = 0


class AdminOrgCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    owner_uid: str = Field(..., min_length=1)
    plan_id: str = Field(..., min_length=1)


class AdminOrgUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    plan_id: Optional[str] = None
    plan_expires_at: Optional[date] = None


class AdminOrgAdminAdd(BaseModel):
    user_uid: str = Field(..., min_length=1)


class AdminOrgTeamLink(BaseModel):
    team_id: str = Field(..., min_length=1)


# ─── Metrics + Audit (US-M11.5) ──────────────────────────────────────


class AdminDauPoint(BaseModel):
    date: str
    dau: int
    mau: int
    signups: int


class AdminAiUsagePoint(BaseModel):
    date: str
    feature: str
    count: int


class AdminCohortRow(BaseModel):
    cohort_week: str
    signups: int
    retained_d7: int
    retained_d30: int


class AdminPlanDistribution(BaseModel):
    plan_id: str
    count: int


class AdminAuditRow(BaseModel):
    id: int
    event_type: str
    actor_uid: str
    target_kind: str
    target_id: str
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    request_id: Optional[str] = None
    created_at: Optional[str] = None


class AdminAuditPage(BaseModel):
    items: list[AdminAuditRow]
    total: int
    page: int
    page_size: int


# ─── Generic ─────────────────────────────────────────────────────────


class AdminActionResponse(BaseModel):
    """Returned by mutating endpoints when a row body isn't useful."""

    ok: bool = True
    audit_log_id: Optional[int] = None
    extra: dict[str, Any] = Field(default_factory=dict)
