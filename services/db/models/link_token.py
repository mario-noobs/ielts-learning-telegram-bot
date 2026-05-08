"""LinkToken model — single-use token backing the `/link` deep-link flow.

Direction `'tg_to_web'`: bot `/link` mints the token, web redeems via
`POST /api/v1/link/redeem`. `telegram_id` is set, `auth_uid` is NULL
until redemption.

Direction `'web_to_tg'`: web "Link Telegram" mints the token, bot
`/start link_<token>` redeems it. `auth_uid` is set, `telegram_id` is
NULL until redemption.

TTL is enforced via `expires_at`. Single-use is enforced via
`redeemed_at IS NULL` — the redeemer flips both `redeemed_at` and
`redeemed_by` in one UPDATE.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from services.db.base import Base


class LinkToken(Base):
    __tablename__ = "link_tokens"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    auth_uid: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    redeemed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "direction IN ('tg_to_web', 'web_to_tg')",
            name="ck_link_tokens_direction",
        ),
        Index(
            "ix_link_tokens_expires_at_unredeemed",
            "expires_at",
            postgresql_where="redeemed_at IS NULL",
        ),
    )
