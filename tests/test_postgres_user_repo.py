"""CRUD round-trip tests for ``PostgresUserRepo``."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping Postgres user_repo tests",
)


@pytest.fixture(autouse=True)
def _truncate_users():
    """Wipe the users table around every test so cases don't bleed."""
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.execute(delete(User))
    yield
    with get_sync_session() as s, s.begin():
        s.execute(delete(User))


def _repo():
    from services.repositories.postgres import PostgresUserRepo

    return PostgresUserRepo()


def test_create_then_get_telegram_user() -> None:
    repo = _repo()
    created = repo.create(
        telegram_id=42,
        name="Alice",
        username="alice",
        group_id=-100,
        target_band=8.0,
        topics=["education", "health"],
    )
    assert created.id == "42"
    assert created.target_band == 8.0
    assert created.topics == ["education", "health"]

    fetched = repo.get(42)
    assert fetched is not None
    assert fetched.id == "42"
    assert fetched.name == "Alice"
    assert fetched.streak == 0
    assert fetched.total_words == 0
    assert fetched.created_at is not None
    assert fetched.last_active is not None


def test_get_missing_returns_none() -> None:
    assert _repo().get(9999) is None


def test_update_writes_arbitrary_fields() -> None:
    repo = _repo()
    repo.create(telegram_id=1, name="Bob")
    repo.update(1, {"name": "Bob v2", "total_words": 7, "streak": 3})

    u = repo.get(1)
    assert u is not None
    assert u.name == "Bob v2"
    assert u.total_words == 7
    assert u.streak == 3


def test_list_by_group_filters() -> None:
    repo = _repo()
    repo.create(telegram_id=10, name="A", group_id=-1)
    repo.create(telegram_id=11, name="B", group_id=-1)
    repo.create(telegram_id=12, name="C", group_id=-2)

    g1 = repo.list_by_group(-1)
    assert {u.id for u in g1} == {"10", "11"}
    g2 = repo.list_by_group(-2)
    assert [u.id for u in g2] == ["12"]


def test_list_all_returns_every_row() -> None:
    repo = _repo()
    repo.create(telegram_id=1, name="A")
    repo.create(telegram_id=2, name="B")
    repo.create_web_user(auth_uid="auth-1", email="a@b.test", name="C")
    assert len(repo.list_all()) == 3


def test_update_streak_first_call_starts_at_one() -> None:
    repo = _repo()
    repo.create(telegram_id=1, name="A")
    # last_active was set on create; same UTC day → streak stays at 0 logic.
    # Force last_active to None to exercise the "fresh" branch.
    repo.update(1, {"last_active": None})

    repo.update_streak(1)
    assert repo.get(1).streak == 1


def test_update_streak_consecutive_day_increments() -> None:
    repo = _repo()
    repo.create(telegram_id=1, name="A")
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    repo.update(1, {"last_active": yesterday, "streak": 4})

    repo.update_streak(1)
    assert repo.get(1).streak == 5


def test_update_streak_same_day_holds() -> None:
    repo = _repo()
    repo.create(telegram_id=1, name="A")
    repo.update(1, {"streak": 7})  # last_active was set on create (today)

    repo.update_streak(1)
    assert repo.get(1).streak == 7


def test_update_streak_gap_resets_to_one() -> None:
    repo = _repo()
    repo.create(telegram_id=1, name="A")
    long_ago = datetime.now(timezone.utc) - timedelta(days=10)
    repo.update(1, {"last_active": long_ago, "streak": 9})

    repo.update_streak(1)
    assert repo.get(1).streak == 1


def test_get_quiz_stats() -> None:
    repo = _repo()
    repo.create(telegram_id=1, name="A")
    repo.update(1, {"total_quizzes": 10, "total_correct": 7})

    stats = repo.get_quiz_stats(1)
    assert stats.total == 10
    assert stats.correct == 7
    assert stats.accuracy == 70.0


def test_get_quiz_stats_handles_missing_user() -> None:
    stats = _repo().get_quiz_stats(9999)
    assert stats.total == 0
    assert stats.correct == 0
    assert stats.accuracy == 0.0


def test_create_web_user_sets_auth_uid_and_returns_doc() -> None:
    repo = _repo()
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    u = repo.create_web_user(auth_uid=auth_uid, email="x@example.com", name="W")
    assert u.id.startswith("web_")
    assert u.email == "x@example.com"
    assert u.auth_uid == auth_uid

    fetched = repo.get_by_auth_uid(auth_uid)
    assert fetched is not None
    assert fetched.id == u.id
    assert fetched.email == "x@example.com"


def test_get_by_auth_uid_unknown() -> None:
    assert _repo().get_by_auth_uid("nope") is None


def test_link_telegram_to_auth() -> None:
    repo = _repo()
    repo.create(telegram_id=1, name="A")
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    repo.link_telegram_to_auth(1, auth_uid)

    u = repo.get(1)
    assert u is not None
    assert u.auth_uid == auth_uid

    fetched = repo.get_by_auth_uid(auth_uid)
    assert fetched is not None
    assert fetched.id == "1"


def test_m11_admin_fields_default_and_round_trip() -> None:
    """role/plan/team_id/etc. (admin schema in M11) round-trip via update."""
    from services.db import get_sync_session
    from services.db.models import User

    repo = _repo()
    repo.create(telegram_id=1, name="A")

    # The DTO doesn't expose admin fields yet (M11 owns the DTO extension),
    # but the table has them. Verify defaults + writes via direct SQLAlchemy.
    with get_sync_session() as s:
        row = s.get(User, "1")
        assert row.role == "user"
        assert row.plan == "free"
        assert row.team_id is None
        assert row.quota_override is None

    with get_sync_session() as s, s.begin():
        row = s.get(User, "1")
        row.role = "platform_admin"
        row.plan = "personal_pro"
        row.team_id = "t-1"
        row.quota_override = 500

    with get_sync_session() as s:
        row = s.get(User, "1")
        assert row.role == "platform_admin"
        assert row.plan == "personal_pro"
        assert row.team_id == "t-1"
        assert row.quota_override == 500
