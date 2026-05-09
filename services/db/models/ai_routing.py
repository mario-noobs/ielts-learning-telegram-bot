"""AI routing config + per-provider usage models (US-#221).

`ai_routing_config` holds the ordered provider/model chain per plan so
admin can re-route AI traffic without a redeploy. The router caches it
for ``AI_ROUTING_CACHE_TTL_SECONDS`` (default 60s), mirroring the
feature-flag service pattern.

`ai_provider_usage` lets us track our own per-provider RPD across the
whole app — Groq's 429 alone is fine for correctness, but having a
local sliding-window counter lets us:
  - predict exhaustion + flip the chain order before users hit the cliff
  - power the admin dashboard's "Groq used X/14400 today" tile
  - emit the AC12 telemetry without an extra structlog parse step
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class AiRoutingConfig(Base):
    """Provider/model chain per plan.

    `chain` JSONB is an ordered list of `{provider, model}` dicts. The
    router walks it in order, falling forward on rate-limit / transient
    errors. Schema kept loose on purpose — adding fields like
    `timeout_s` or `temperature` per hop won't require a migration.
    """

    __tablename__ = "ai_routing_config"

    plan: Mapped[str] = mapped_column(Text, primary_key=True)
    chain: Mapped[list] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )


class AiProviderUsage(Base):
    """Per-day-per-provider call counter for telemetry + headroom alerts."""

    __tablename__ = "ai_provider_usage"

    date: Mapped[_date] = mapped_column(Date, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    model: Mapped[str] = mapped_column(Text, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    last_call_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        Index("ix_ai_provider_usage_date", "date"),
    )
