"""Pydantic models for `/api/v1/readiness` (US-#223)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


Status = Literal["done", "active", "upcoming", "locked"]


class ReadinessSubTask(BaseModel):
    id: str
    label_key: str
    href: str
    done: bool


class ReadinessStep(BaseModel):
    id: Literal["goal", "daily_plan", "skills", "mock_test"]
    status: Status
    title_key: str
    rationale_key: str
    rationale_params: dict
    sub_tasks: list[ReadinessSubTask]


class ReadinessResponse(BaseModel):
    pct_complete: int
    days_until_exam: Optional[int] = None
    urgent: bool
    target_band: float
    steps: list[ReadinessStep]
