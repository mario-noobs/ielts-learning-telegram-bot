"""Pydantic models for /api/v1/me/groups + /api/v1/groups/* (US-#227).

Group docs live in Firestore (`groups/{id}`). These DTOs are the API
contract — the underlying Firestore shape is loose, so the route
handlers normalise on read and validate on write.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GroupSummary(BaseModel):
    """One row in `GET /api/v1/me/groups`."""

    id: str
    name: Optional[str] = None
    member_count: int = 0
    role: str = "member"  # "owner" | "member"
    default_band: float = 7.0
    topics: list[str] = Field(default_factory=list)
    daily_time: Optional[str] = None


class GroupDetail(BaseModel):
    """`GET /api/v1/groups/{id}` — full editable settings."""

    id: str
    name: Optional[str] = None
    role: str = "member"  # "owner" | "member" — frontend uses to gate UI
    member_count: int = 0
    owner_telegram_id: Optional[int] = None

    default_band: float = 7.0
    topics: list[str] = Field(default_factory=list)
    daily_time: Optional[str] = None
    challenge_time: Optional[str] = None
    word_count: int = 10
    challenge_question_count: int = 5
    challenge_deadline_minutes: int = 60


class GroupUpdate(BaseModel):
    """`PATCH /api/v1/groups/{id}` body. All fields optional — partial."""

    default_band: Optional[float] = Field(default=None, ge=4.0, le=9.0)
    topics: Optional[list[str]] = None
    daily_time: Optional[str] = Field(
        default=None,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )
    challenge_time: Optional[str] = Field(
        default=None,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )
    word_count: Optional[int] = Field(default=None, ge=5, le=20)
    challenge_question_count: Optional[int] = Field(default=None, ge=3, le=10)
    challenge_deadline_minutes: Optional[int] = Field(default=None, ge=15, le=180)
