"""PlatformMetric model — daily snapshot."""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Any

from sqlalchemy import Date, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class PlatformMetric(Base):
    __tablename__ = "platform_metrics"

    date: Mapped[_date] = mapped_column(Date, primary_key=True)
    total_users: Mapped[int] = mapped_column(Integer, nullable=False)
    dau: Mapped[int] = mapped_column(Integer, nullable=False)
    signups: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_distribution: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    errors_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
