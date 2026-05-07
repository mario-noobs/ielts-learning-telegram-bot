"""AuditLog model — append-only record of admin mutations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_uid: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    before: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    after: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_audit_log_actor_uid_created_at",
            "actor_uid",
            "created_at",
        ),
        Index(
            "ix_audit_log_target_kind_target_id_created_at",
            "target_kind",
            "target_id",
            "created_at",
        ),
        Index("ix_audit_log_created_at", "created_at"),
    )
