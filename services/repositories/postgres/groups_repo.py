"""Postgres repos for bot-owned group state (M8 Block B #234).

Five tables (groups, group_members, group_daily_words, group_challenges,
group_challenge_answers) each get a focused repo. Returns dicts (legacy
caller shape) — group state has no DTOs at the Protocol layer; bot
handlers consume dicts directly.

challenge_id is a deterministic UUIDv5 of (group_id, date_str). The
``challenge_id_for(group_id, date_str)`` helper at module top is the
single source of truth — bot handlers and migration scripts both use it
so no DB lookup is needed to resolve (group_id, date) → challenge row.
"""

from __future__ import annotations

import uuid
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

import config
from services.db import get_sync_session
from services.db.models import (
    Group,
    GroupChallenge,
    GroupChallengeAnswer,
    GroupDailyWords,
    GroupMember,
    User,
)

# UUIDv5 namespace shared with scripts/migrate_firestore_to_pg.py so the
# migrator and the live app produce identical challenge ids.
_CHALLENGE_NAMESPACE = uuid.UUID("e6a9d8bb-4c1e-5f8e-9c1a-1f2c3d4e5f60")


def challenge_id_for(group_id: int, date_str: str) -> str:
    """Resolve (group_id, date_str) → stable challenge_id (no DB lookup)."""
    return str(uuid.uuid5(_CHALLENGE_NAMESPACE, f"{group_id}:{date_str}"))


def _parse_date(s) -> _date:
    if isinstance(s, _date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    return _date.fromisoformat(str(s).split("T")[0])


def _group_to_dict(g: Group) -> dict[str, Any]:
    return {
        "id": str(g.id),  # legacy callers expect string id
        "default_band": g.default_band,
        "daily_time": g.daily_time,
        "challenge_time": g.challenge_time,
        "timezone": g.timezone,
        "challenge_question_count": g.challenge_question_count,
        "word_count": g.word_count,
        "owner_telegram_id": g.owner_telegram_id,
        "owner_uid": g.owner_uid,
        "topics": list(g.topics or []),
        "recent_topics": list(g.recent_topics or []),
        "created_at": g.created_at,
        "updated_at": g.updated_at,
    }


def _challenge_to_dict(
    c: GroupChallenge, *, with_id_aliases: bool = True,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": c.date.isoformat() if with_id_aliases else c.id,
        "group_id": c.group_id,
        "date": c.date,
        "status": c.status,
        "questions": list(c.questions or []),
        "participants": dict(c.participants or {}),
        "created_at": c.created_at,
        "expires_at": c.expires_at,
    }
    return out


# ─── PostgresGroupsRepo ────────────────────────────────────────────────


class PostgresGroupsRepo:
    """Group settings + membership lookup."""

    def get(self, group_id: int) -> Optional[dict]:
        with get_sync_session() as s:
            row = s.get(Group, int(group_id))
        return _group_to_dict(row) if row else None

    def create(
        self,
        group_id: int,
        settings: Optional[dict] = None,
        owner_telegram_id: Optional[int] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        defaults: dict[str, Any] = {
            "id": int(group_id),
            "daily_time": config.DEFAULT_DAILY_TIME,
            "challenge_time": config.DEFAULT_CHALLENGE_TIME,
            "timezone": config.DEFAULT_TIMEZONE,
            "topics": ["education", "environment", "technology"],
            "default_band": config.DEFAULT_BAND_TARGET,
            "word_count": config.DEFAULT_WORD_COUNT,
            "challenge_question_count": config.DEFAULT_CHALLENGE_QUESTION_COUNT,
            "owner_telegram_id": int(owner_telegram_id) if owner_telegram_id else None,
            "recent_topics": [],
            "created_at": now,
            "updated_at": now,
        }
        if settings:
            # Drop fields the model doesn't carry (e.g. challenge_deadline_minutes
            # — that's app-config, not group state).
            allowed = {
                "default_band", "daily_time", "challenge_time", "timezone",
                "challenge_question_count", "word_count", "owner_telegram_id",
                "owner_uid", "topics", "recent_topics",
            }
            defaults.update({k: v for k, v in settings.items() if k in allowed})

        stmt = pg_insert(Group).values(**defaults).on_conflict_do_nothing(
            index_elements=["id"],
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)

    def update(self, group_id: int, data: dict) -> None:
        # Filter to known columns; drop legacy fields like
        # challenge_deadline_minutes that don't have PG storage.
        allowed = {
            "default_band", "daily_time", "challenge_time", "timezone",
            "challenge_question_count", "word_count", "owner_telegram_id",
            "owner_uid", "topics", "recent_topics",
        }
        values = {k: v for k, v in data.items() if k in allowed}
        if not values:
            return
        with get_sync_session() as s, s.begin():
            s.execute(
                update(Group).where(Group.id == int(group_id)).values(**values),
            )

    def list_all(self) -> list[dict]:
        with get_sync_session() as s:
            rows = s.execute(select(Group)).scalars().all()
        return [_group_to_dict(r) for r in rows]

    def list_for_user(self, telegram_id: int) -> list[dict]:
        """Groups this user is a member of.

        Membership inferred from ``users.group_id`` *AND* ``group_members``
        (M14 explicit ledger). Either signal is enough — UNION cleans
        duplicates.
        """
        if telegram_id is None:
            return []
        tg = int(telegram_id)
        with get_sync_session() as s:
            via_users = s.execute(
                select(Group)
                .join(User, User.group_id == Group.id)
                .where(User.id == str(tg))
            ).scalars().all()
            via_members = s.execute(
                select(Group)
                .join(GroupMember, GroupMember.group_id == Group.id)
                .where(GroupMember.telegram_id == tg)
            ).scalars().all()
        seen: dict[int, Group] = {g.id: g for g in via_users}
        for g in via_members:
            seen.setdefault(g.id, g)
        return [_group_to_dict(g) for g in seen.values()]

    def list_users_in_group(self, group_id: int) -> list[dict]:
        """Return user dicts belonging to ``group_id`` via users.group_id."""
        from services.repositories.postgres.user_repo import _row_to_doc

        with get_sync_session() as s:
            rows = s.execute(
                select(User).where(User.group_id == int(group_id)),
            ).scalars().all()
        return [_row_to_doc(r).model_dump() for r in rows]


# ─── Helpers shared across child-table repos ───────────────────────────


def _ensure_group_stub(session, group_id: int) -> None:
    """Insert a minimal ``groups`` row if one doesn't exist (FK guard).

    Pre-cutover, Firestore tolerated subcollections under groups that
    were never explicitly created (legacy data, lazy creation flow,
    bot-added groups missing the explicit ``create_group`` call). Post-
    cutover the ``group_daily_words`` / ``group_challenges`` /
    ``group_challenge_answers`` FKs reject those orphans.

    The stub row is intentionally minimal — settings come from the
    bot's first ``/start``-in-group call later. Idempotent (ON CONFLICT
    DO NOTHING) so concurrent inserts don't race.
    """
    now = datetime.now(timezone.utc)
    session.execute(
        pg_insert(Group).values(
            id=int(group_id),
            topics=[],
            recent_topics=[],
            created_at=now,
            updated_at=now,
        ).on_conflict_do_nothing(index_elements=["id"]),
    )


# ─── PostgresGroupDailyWordsRepo ───────────────────────────────────────


class PostgresGroupDailyWordsRepo:
    """Per-group daily vocab set, keyed by (group_id, date)."""

    def save(
        self, group_id: int, date_str: str, words: list, topic: str,
    ) -> None:
        d = _parse_date(date_str)
        now = datetime.now(timezone.utc)
        with get_sync_session() as s, s.begin():
            _ensure_group_stub(s, group_id)  # FK guard for legacy groups
            s.execute(
                pg_insert(GroupDailyWords).values(
                    group_id=int(group_id),
                    date=d,
                    words=words,
                    topic=topic,
                    generated_at=now,
                ).on_conflict_do_update(
                    index_elements=["group_id", "date"],
                    set_={"words": words, "topic": topic, "generated_at": now},
                ),
            )

    def get(self, group_id: int, date_str: str) -> Optional[dict]:
        d = _parse_date(date_str)
        with get_sync_session() as s:
            row = s.execute(
                select(GroupDailyWords).where(
                    GroupDailyWords.group_id == int(group_id),
                    GroupDailyWords.date == d,
                )
            ).scalar_one_or_none()
        if not row:
            return None
        return {
            "words": list(row.words or []),
            "topic": row.topic,
            "generated_at": row.generated_at,
        }


# ─── PostgresGroupChallengesRepo ───────────────────────────────────────


class PostgresGroupChallengesRepo:
    """Group quiz challenges + atomic close transaction.

    challenge_id resolution is deterministic UUIDv5(group_id, date) —
    callers that already know (group_id, date) can compute it locally
    via ``challenge_id_for`` without a DB roundtrip.
    """

    def save(
        self,
        group_id: int,
        date_str: str,
        questions: list,
        deadline_minutes: Optional[int] = None,
    ) -> None:
        d = _parse_date(date_str)
        now = datetime.now(timezone.utc)
        if deadline_minutes is None:
            deadline_minutes = config.CHALLENGE_DEADLINE_MINUTES
        cid = challenge_id_for(int(group_id), date_str)
        with get_sync_session() as s, s.begin():
            _ensure_group_stub(s, group_id)  # FK guard for legacy groups
            s.execute(
                pg_insert(GroupChallenge).values(
                    id=cid,
                    group_id=int(group_id),
                    date=d,
                    status="active",
                    questions=questions,
                    participants={},
                    created_at=now,
                    expires_at=now + timedelta(minutes=deadline_minutes),
                ).on_conflict_do_nothing(index_elements=["id"]),
            )

    def get(self, group_id: int, date_str: str) -> Optional[dict]:
        cid = challenge_id_for(int(group_id), date_str)
        with get_sync_session() as s:
            row = s.execute(
                select(GroupChallenge).where(GroupChallenge.id == cid),
            ).scalar_one_or_none()
        return _challenge_to_dict(row) if row else None

    def update_participant_score(
        self, group_id: int, date_str: str, user_id: int, score: int,
    ) -> None:
        """Set participants[user_id] = score.

        SELECT-FOR-UPDATE + Python-side merge keeps SQL portable
        (avoids JSONB function bind-param shape that SA doesn't pass
        through cleanly). Row lock serializes concurrent score updates.
        """
        cid = challenge_id_for(int(group_id), date_str)
        with get_sync_session() as s, s.begin():
            row = s.execute(
                select(GroupChallenge)
                .where(GroupChallenge.id == cid)
                .with_for_update(),
            ).scalar_one_or_none()
            if row is None:
                return
            merged = dict(row.participants or {})
            merged[str(user_id)] = int(score)
            row.participants = merged

    def list_active(self) -> list[dict]:
        """Active challenges across all groups (used at restart for recovery)."""
        now = datetime.now(timezone.utc)
        with get_sync_session() as s:
            rows = s.execute(
                select(GroupChallenge).where(
                    GroupChallenge.status == "active",
                    GroupChallenge.expires_at > now,
                )
            ).scalars().all()
        out: list[dict] = []
        for r in rows:
            out.append({
                "group_id": r.group_id,
                "date_str": r.date.isoformat(),
                "id": r.date.isoformat(),
                "questions": list(r.questions or []),
                "participants": dict(r.participants or {}),
                "status": r.status,
                "created_at": r.created_at,
                "expires_at": r.expires_at,
            })
        return out

    def close_atomic(self, group_id: int, date_str: str) -> Optional[dict]:
        """Compute scores from answers, set winner, mark closed.

        Single PG transaction with row-level locking on the challenge row
        so concurrent close calls serialize. Idempotent — re-closing an
        already-closed challenge returns the existing result.

        Counter bump on the winner's user row uses ``col = col + 1``
        atomic UPDATE inside the same txn (no race vs another concurrent
        challenge close).
        """
        cid = challenge_id_for(int(group_id), date_str)
        with get_sync_session() as s, s.begin():
            row = s.execute(
                select(GroupChallenge).where(GroupChallenge.id == cid).with_for_update(),
            ).scalar_one_or_none()
            if row is None:
                return None
            if row.status == "closed":
                return _challenge_to_dict(row)

            answers = s.execute(
                select(GroupChallengeAnswer).where(
                    GroupChallengeAnswer.challenge_id == cid,
                ),
            ).scalars().all()

            participants: dict[str, int] = {}
            display_names: dict[str, str] = {}
            for ans in answers:
                resp = ans.responses or {}
                score = sum(1 for v in resp.values() if v)
                participants[ans.user_id] = score
                if ans.display_name:
                    display_names[ans.user_id] = ans.display_name

            winner_id: Optional[int] = None
            if participants:
                # Sort: highest score first, earliest completed_at as tie-breaker.
                far_future = datetime(9999, 1, 1, tzinfo=timezone.utc)
                completed_lookup = {
                    a.user_id: (a.completed_at or far_future) for a in answers
                }

                def _sort_key(item):
                    uid, score = item
                    return (-score, completed_lookup.get(uid, far_future))

                sorted_p = sorted(participants.items(), key=_sort_key)
                if sorted_p[0][1] > 0:
                    try:
                        winner_id = int(sorted_p[0][0])
                    except ValueError:
                        winner_id = None

            row.participants = participants
            row.status = "closed"

            if winner_id is not None:
                s.execute(
                    update(User)
                    .where(User.id == str(winner_id))
                    .values(challenge_wins=User.challenge_wins + 1),
                )

            result = _challenge_to_dict(row)
            # Surface display_names in the return so the result post can
            # render names without a second query (matches Firestore
            # legacy shape).
            result["display_names"] = display_names
            return result


# ─── PostgresGroupChallengeAnswersRepo ─────────────────────────────────


class PostgresGroupChallengeAnswersRepo:
    """Per-user answer document for a challenge."""

    def upsert_response(
        self,
        group_id: int,
        date_str: str,
        user_id: int,
        q_idx: int,
        is_correct: bool,
        display_name: Optional[str] = None,
    ) -> None:
        """Merge {q_idx: is_correct} into responses; set display_name on first save.

        SELECT-FOR-UPDATE + Python-side merge keeps the SQL simple
        (avoids the jsonb_set + on-conflict bindparam shape that
        SQLAlchemy's ON CONFLICT helper doesn't accept). Race-safe
        because the row lock serializes concurrent answer-callbacks.

        Auto-creates a stub group + challenge row for legacy groups
        whose parent rows never made it into PG (FK guard).
        """
        cid = challenge_id_for(int(group_id), date_str)
        d = _parse_date(date_str)
        now = datetime.now(timezone.utc)
        with get_sync_session() as s, s.begin():
            _ensure_group_stub(s, group_id)
            # Stub the challenge row too so the answer FK is satisfied.
            # Empty questions list is a defensible fallback — the bot
            # caller normally creates the row via ``save()`` first; this
            # branch only fires for an answer arriving before the
            # challenge row was set up (or for a never-migrated group).
            s.execute(
                pg_insert(GroupChallenge).values(
                    id=cid,
                    group_id=int(group_id),
                    date=d,
                    status="active",
                    questions=[],
                    participants={},
                    created_at=now,
                ).on_conflict_do_nothing(index_elements=["id"]),
            )

            existing = s.execute(
                select(GroupChallengeAnswer)
                .where(
                    GroupChallengeAnswer.challenge_id == cid,
                    GroupChallengeAnswer.user_id == str(user_id),
                )
                .with_for_update(),
            ).scalar_one_or_none()
            if existing is None:
                s.add(GroupChallengeAnswer(
                    challenge_id=cid,
                    user_id=str(user_id),
                    responses={str(q_idx): bool(is_correct)},
                    display_name=display_name,
                    started_at=now,
                ))
            else:
                merged = dict(existing.responses or {})
                merged[str(q_idx)] = bool(is_correct)
                existing.responses = merged
                if display_name and not existing.display_name:
                    existing.display_name = display_name

    def mark_completed(
        self, group_id: int, date_str: str, user_id: int,
    ) -> None:
        cid = challenge_id_for(int(group_id), date_str)
        now = datetime.now(timezone.utc)
        with get_sync_session() as s, s.begin():
            s.execute(
                update(GroupChallengeAnswer)
                .where(
                    GroupChallengeAnswer.challenge_id == cid,
                    GroupChallengeAnswer.user_id == str(user_id),
                )
                .values(completed_at=now),
            )

    def get(
        self, group_id: int, date_str: str, user_id: int,
    ) -> Optional[dict]:
        cid = challenge_id_for(int(group_id), date_str)
        with get_sync_session() as s:
            row = s.execute(
                select(GroupChallengeAnswer).where(
                    GroupChallengeAnswer.challenge_id == cid,
                    GroupChallengeAnswer.user_id == str(user_id),
                )
            ).scalar_one_or_none()
        if not row:
            return None
        return {
            "id": row.user_id,
            "responses": dict(row.responses or {}),
            "display_name": row.display_name,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
        }

    def list_for_challenge(
        self, group_id: int, date_str: str,
    ) -> list[dict]:
        cid = challenge_id_for(int(group_id), date_str)
        with get_sync_session() as s:
            rows = s.execute(
                select(GroupChallengeAnswer).where(
                    GroupChallengeAnswer.challenge_id == cid,
                )
            ).scalars().all()
        return [{
            "id": r.user_id,
            "responses": dict(r.responses or {}),
            "display_name": r.display_name,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
        } for r in rows]


__all__ = [
    "PostgresGroupChallengeAnswersRepo",
    "PostgresGroupChallengesRepo",
    "PostgresGroupDailyWordsRepo",
    "PostgresGroupsRepo",
    "challenge_id_for",
]
