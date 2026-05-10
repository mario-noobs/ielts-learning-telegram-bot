"""Postgres implementation of ``DailyWordsRepo`` (per-user DM scope).

Group daily words live in a separate ``group_daily_words`` table
(out of scope for this Protocol — accessed via the bot group repo in
M8 Block B).
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.db import get_sync_session
from services.db.models import UserDailyWords

from ..dtos import DailyWordsDoc
from ..protocols import UserId


def _row_to_dto(row: UserDailyWords) -> DailyWordsDoc:
    return DailyWordsDoc(
        id=row.date.isoformat(),
        words=list(row.words or []),
        topic=row.topic or "",
        generated_at=row.generated_at,
    )


def _parse_date(s: str) -> _date:
    return datetime.fromisoformat(s).date() if "T" in s else _date.fromisoformat(s)


class PostgresDailyWordsRepo:
    """Postgres-backed personal daily-words repo."""

    def save(
        self, user_id: UserId, date_str: str, words: list, topic: str,
    ) -> None:
        d = _parse_date(date_str)
        now = datetime.now(timezone.utc)
        # Upsert: re-saving the same (user, date) overwrites words/topic
        # — matches Firestore set() semantics.
        stmt = pg_insert(UserDailyWords).values(
            user_id=str(user_id),
            date=d,
            words=words,
            topic=topic,
            generated_at=now,
        ).on_conflict_do_update(
            index_elements=["user_id", "date"],
            set_={"words": words, "topic": topic, "generated_at": now},
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)

    def get(self, user_id: UserId, date_str: str) -> Optional[DailyWordsDoc]:
        d = _parse_date(date_str)
        with get_sync_session() as s:
            row = s.execute(
                select(UserDailyWords).where(
                    UserDailyWords.user_id == str(user_id),
                    UserDailyWords.date == d,
                )
            ).scalar_one_or_none()
        return _row_to_dto(row) if row else None


__all__ = ["PostgresDailyWordsRepo"]
