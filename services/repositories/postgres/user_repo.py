"""Postgres implementation of ``UserRepo``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update

import config
from services.db import get_sync_session
from services.db.models import User

from ..dtos import QuizStats, UserDoc
from ..protocols import UserId

DEFAULT_TOPICS = ["education", "environment", "technology"]


def _row_to_doc(u: User) -> UserDoc:
    """Hydrate a UserDoc from a SQLAlchemy User row."""
    return UserDoc(
        id=u.id,
        name=u.name,
        username=u.username,
        email=u.email,
        auth_uid=u.auth_uid,
        group_id=u.group_id,
        target_band=u.target_band,
        topics=list(u.topics or []),
        daily_time=u.daily_time,
        timezone=u.timezone,
        streak=u.streak,
        last_active=u.last_active,
        total_words=u.total_words,
        total_quizzes=u.total_quizzes,
        total_correct=u.total_correct,
        challenge_wins=u.challenge_wins,
        exam_date=u.exam_date,
        weekly_goal_minutes=u.weekly_goal_minutes,
        created_at=u.created_at,
        role=u.role,
        plan=u.plan,
        plan_expires_at=u.plan_expires_at,
        team_id=u.team_id,
        org_id=u.org_id,
        quota_override=u.quota_override,
        last_active_date=u.last_active_date,
        signup_cohort=u.signup_cohort,
    )


class PostgresUserRepo:
    """Postgres-backed ``UserRepo``. Sync API; matches the Protocol."""

    def get(self, user_id: UserId) -> Optional[UserDoc]:
        with get_sync_session() as s:
            row = s.get(User, str(user_id))
            return _row_to_doc(row) if row else None

    def create(
        self,
        telegram_id: int,
        name: str,
        username: str = "",
        group_id: Optional[int] = None,
        target_band: float = 7.0,
        topics: Optional[list[str]] = None,
    ) -> UserDoc:
        now = datetime.now(timezone.utc)
        u = User(
            id=str(telegram_id),
            name=name,
            username=username or "",
            group_id=group_id,
            target_band=target_band,
            topics=topics or DEFAULT_TOPICS,
            daily_time=config.DEFAULT_DAILY_TIME,
            timezone=config.DEFAULT_TIMEZONE,
            streak=0,
            last_active=now,
            total_words=0,
            total_quizzes=0,
            total_correct=0,
            challenge_wins=0,
            created_at=now,
        )
        with get_sync_session() as s, s.begin():
            s.add(u)
        return _row_to_doc(u)

    def update(self, user_id: UserId, data: dict) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(
                update(User).where(User.id == str(user_id)).values(**data),
            )

    def list_by_group(self, group_id: int) -> list[UserDoc]:
        with get_sync_session() as s:
            rows = s.execute(select(User).where(User.group_id == group_id)).scalars().all()
            return [_row_to_doc(r) for r in rows]

    def list_all(self) -> list[UserDoc]:
        with get_sync_session() as s:
            rows = s.execute(select(User)).scalars().all()
            return [_row_to_doc(r) for r in rows]

    def update_streak(self, user_id: UserId) -> None:
        # Read + update in the same transaction so concurrent calls don't
        # race on the streak counter.
        with get_sync_session() as s, s.begin():
            row = s.get(User, str(user_id))
            if row is None:
                return
            now = datetime.now(timezone.utc)
            last = row.last_active
            if last is None:
                new_streak = 1
            else:
                delta_days = (now.date() - last.date()).days
                if delta_days == 1:
                    new_streak = (row.streak or 0) + 1
                elif delta_days == 0:
                    new_streak = row.streak or 0
                else:
                    new_streak = 1
            row.streak = new_streak
            row.last_active = now

    def get_quiz_stats(self, user_id: UserId) -> QuizStats:
        user = self.get(user_id)
        if not user:
            return QuizStats(total=0, correct=0, accuracy=0.0)
        total = user.total_quizzes or 0
        correct = user.total_correct or 0
        accuracy = round((correct / total * 100), 1) if total > 0 else 0.0
        return QuizStats(total=total, correct=correct, accuracy=accuracy)

    # ── Web auth ──────────────────────────────────────────────────────

    def get_by_auth_uid(self, auth_uid: str) -> Optional[UserDoc]:
        with get_sync_session() as s:
            row = s.execute(
                select(User).where(User.auth_uid == auth_uid),
            ).scalar_one_or_none()
            return _row_to_doc(row) if row else None

    def create_web_user(
        self,
        auth_uid: str,
        email: str,
        name: str,
        target_band: float = 7.0,
        topics: Optional[list[str]] = None,
    ) -> UserDoc:
        now = datetime.now(timezone.utc)
        u = User(
            id=f"web_{uuid.uuid4().hex[:12]}",
            name=name,
            username="",
            email=email,
            auth_uid=auth_uid,
            group_id=None,
            target_band=target_band,
            topics=topics or DEFAULT_TOPICS,
            daily_time=config.DEFAULT_DAILY_TIME,
            timezone=config.DEFAULT_TIMEZONE,
            streak=0,
            last_active=now,
            total_words=0,
            total_quizzes=0,
            total_correct=0,
            challenge_wins=0,
            created_at=now,
        )
        with get_sync_session() as s, s.begin():
            s.add(u)
        return _row_to_doc(u)

    def link_telegram_to_auth(self, telegram_id: int, auth_uid: str) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(
                update(User)
                .where(User.id == str(telegram_id))
                .values(auth_uid=auth_uid),
            )


__all__ = ["PostgresUserRepo"]
