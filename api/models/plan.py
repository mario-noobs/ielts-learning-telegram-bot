from datetime import datetime

from pydantic import BaseModel


class PlanActivity(BaseModel):
    id: str
    type: str
    title: str
    description: str = ""
    estimated_minutes: int = 0
    route: str = "/"
    meta: dict = {}
    completed: bool = False


class DailyPlan(BaseModel):
    date: str
    activities: list[PlanActivity]
    total_minutes: int = 0
    cap_minutes: int = 30
    exam_urgent: bool = False
    days_until_exam: int | None = None
    completed_count: int = 0
    generated_at: datetime | None = None
