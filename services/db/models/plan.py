"""Plan model — admin-defined subscription tiers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    daily_ai_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_ai_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    max_team_seats: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    features: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
