"""AiUsage model — per-user-per-day-per-feature counter."""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class AiUsage(Base):
    __tablename__ = "ai_usage"

    user_uid: Mapped[str] = mapped_column(Text, primary_key=True)
    date: Mapped[_date] = mapped_column(Date, primary_key=True)
    feature: Mapped[str] = mapped_column(Text, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_call_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        Index("ix_ai_usage_date", "date"),
    )
