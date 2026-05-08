"""Postgres implementation of ``LinkTokenRepo`` (US-M12.2)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, update

from services.db import get_sync_session
from services.db.models import LinkToken

from ..dtos import LinkTokenDoc


def _row_to_doc(t: LinkToken) -> LinkTokenDoc:
    return LinkTokenDoc(
        token=t.token,
        direction=t.direction,
        telegram_id=t.telegram_id,
        auth_uid=t.auth_uid,
        created_at=t.created_at,
        expires_at=t.expires_at,
        redeemed_at=t.redeemed_at,
        redeemed_by=t.redeemed_by,
    )


class PostgresLinkTokenRepo:
    """Postgres-backed ``LinkTokenRepo``.

    Token values come from ``secrets.token_urlsafe(24)`` — ~32 URL-safe
    characters, ~192 bits of entropy. Single-use is enforced by the
    atomic ``UPDATE … WHERE token=$1 AND redeemed_at IS NULL`` in
    ``redeem``: a second concurrent caller sees the row with
    ``redeemed_at`` set and the UPDATE matches 0 rows.
    """

    def create(
        self,
        *,
        direction: str,
        telegram_id: Optional[int] = None,
        auth_uid: Optional[str] = None,
        ttl_seconds: int = 15 * 60,
    ) -> LinkTokenDoc:
        if direction not in ("tg_to_web", "web_to_tg"):
            raise ValueError(f"unknown direction: {direction!r}")
        if direction == "tg_to_web" and telegram_id is None:
            raise ValueError("tg_to_web token requires telegram_id")
        if direction == "web_to_tg" and not auth_uid:
            raise ValueError("web_to_tg token requires auth_uid")

        now = datetime.now(timezone.utc)
        row = LinkToken(
            token=secrets.token_urlsafe(24),
            direction=direction,
            telegram_id=telegram_id,
            auth_uid=auth_uid,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        with get_sync_session() as s, s.begin():
            s.add(row)
        return _row_to_doc(row)

    def get(self, token: str) -> Optional[LinkTokenDoc]:
        with get_sync_session() as s:
            row = s.execute(
                select(LinkToken).where(LinkToken.token == token),
            ).scalar_one_or_none()
            return _row_to_doc(row) if row else None

    def redeem(self, token: str, redeemed_by: str) -> Optional[LinkTokenDoc]:
        """Atomically mark ``token`` redeemed.

        Returns the redeemed token doc on success, ``None`` if the token
        is missing, already redeemed, or expired. The caller (the
        orchestrator in ``firebase_service``) inspects the returned
        ``direction`` + origin id to route the sub-case.
        """
        now = datetime.now(timezone.utc)
        with get_sync_session() as s, s.begin():
            result = s.execute(
                update(LinkToken)
                .where(LinkToken.token == token)
                .where(LinkToken.redeemed_at.is_(None))
                .where(LinkToken.expires_at > now)
                .values(redeemed_at=now, redeemed_by=redeemed_by)
                .returning(LinkToken),
            ).scalar_one_or_none()
            return _row_to_doc(result) if result else None

    def cleanup_expired(self, *, older_than_seconds: int = 24 * 3600) -> int:
        """Delete tokens whose ``expires_at`` is older than the cutoff.

        Keeps a 24h debug window after expiry by default. Returns the
        number of rows deleted. Hourly cron in
        ``services.scheduler_service`` calls this.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
        with get_sync_session() as s, s.begin():
            result = s.execute(
                delete(LinkToken).where(LinkToken.expires_at < cutoff),
            )
            return int(result.rowcount or 0)


__all__ = ["PostgresLinkTokenRepo"]
