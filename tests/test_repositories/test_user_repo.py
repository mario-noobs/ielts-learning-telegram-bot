"""Tests for ``services.repositories.firestore.user_repo``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from services.repositories import UserDoc, get_user_repo
from services.repositories.firestore import FirestoreUserRepo

# ── get / create / update ───────────────────────────────────────────

def test_get_missing_returns_none(fake_db):
    assert get_user_repo().get(42) is None


def test_create_user_persists_and_returns_dto(fake_db, frozen_now):
    repo = get_user_repo()
    result = repo.create(42, "Alice", username="alice", target_band=6.5)

    assert isinstance(result, UserDoc)
    assert result.id == "42"
    assert result.name == "Alice"
    assert result.username == "alice"
    assert result.target_band == 6.5
    assert result.created_at == frozen_now
    assert result.last_active == frozen_now
    assert result.streak == 0

    # Round-trip via Firestore
    fetched = repo.get(42)
    assert fetched is not None
    assert fetched.name == "Alice"
    assert fetched.target_band == 6.5


def test_create_user_defaults(fake_db, frozen_now):
    user = get_user_repo().create(1, "Bob")
    assert user.topics == ["education", "environment", "technology"]
    assert user.target_band == 7.0
    assert user.total_quizzes == 0


def test_update_user(fake_db, frozen_now):
    repo = get_user_repo()
    repo.create(42, "Alice")
    repo.update(42, {"streak": 10, "target_band": 8.0})
    user = repo.get(42)
    assert user.streak == 10
    assert user.target_band == 8.0


def test_list_by_group_filters_correctly(fake_db, frozen_now):
    repo = get_user_repo()
    repo.create(1, "A", group_id=100)
    repo.create(2, "B", group_id=200)
    repo.create(3, "C", group_id=100)

    group_100 = repo.list_by_group(100)
    ids = sorted(u.id for u in group_100)
    assert ids == ["1", "3"]


def test_list_all(fake_db, frozen_now):
    repo = get_user_repo()
    repo.create(1, "A")
    repo.create(2, "B")
    assert len(repo.list_all()) == 2


# ── Streaks ─────────────────────────────────────────────────────────

def test_update_streak_missing_user_is_noop(fake_db):
    get_user_repo().update_streak(999)  # must not raise


def test_update_streak_first_time_sets_one(fake_db, frozen_now):
    repo = get_user_repo()
    repo.create(1, "A")
    # Clear last_active so we hit the None branch
    repo.update(1, {"last_active": None})
    repo.update_streak(1)
    assert repo.get(1).streak == 1


def test_update_streak_consecutive_day_increments(fake_db):
    repo = get_user_repo()
    repo.create(1, "A")
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    repo.update(1, {"last_active": yesterday, "streak": 5})
    repo.update_streak(1)
    assert repo.get(1).streak == 6


def test_update_streak_same_day_no_change(fake_db):
    repo = get_user_repo()
    repo.create(1, "A")
    today = datetime.now(timezone.utc)
    repo.update(1, {"last_active": today, "streak": 5})
    repo.update_streak(1)
    assert repo.get(1).streak == 5


def test_update_streak_gap_resets_to_one(fake_db):
    repo = get_user_repo()
    repo.create(1, "A")
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    repo.update(1, {"last_active": three_days_ago, "streak": 10})
    repo.update_streak(1)
    assert repo.get(1).streak == 1


# ── Quiz stats ──────────────────────────────────────────────────────

def test_get_quiz_stats_missing_user(fake_db):
    stats = get_user_repo().get_quiz_stats(99)
    assert stats.total == 0
    assert stats.correct == 0
    assert stats.accuracy == 0.0


def test_get_quiz_stats_computes_accuracy(fake_db, frozen_now):
    repo = get_user_repo()
    repo.create(1, "A")
    repo.update(1, {"total_quizzes": 8, "total_correct": 6})
    stats = repo.get_quiz_stats(1)
    assert stats.total == 8
    assert stats.correct == 6
    assert stats.accuracy == 75.0


def test_get_quiz_stats_zero_total(fake_db, frozen_now):
    repo = get_user_repo()
    repo.create(1, "A")
    stats = repo.get_quiz_stats(1)
    assert stats.accuracy == 0.0


# ── Web auth ────────────────────────────────────────────────────────

def test_get_by_auth_uid_missing_mapping(fake_db):
    assert get_user_repo().get_by_auth_uid("auth-xyz") is None


def test_create_web_user_and_fetch_by_auth(fake_db, frozen_now):
    repo = get_user_repo()
    with patch(
        "services.repositories.firestore.user_repo.uuid.uuid4",
    ) as mock_uuid:
        mock_uuid.return_value.hex = "a" * 32
        user = repo.create_web_user("auth-xyz", "a@b.com", "Alice")

    assert user.id == f"web_{'a' * 12}"
    assert user.email == "a@b.com"
    assert user.auth_uid == "auth-xyz"

    fetched = repo.get_by_auth_uid("auth-xyz")
    assert fetched is not None
    assert fetched.id == user.id
    assert fetched.email == "a@b.com"


def test_get_by_auth_uid_routes_numeric_ids_through_get(fake_db, frozen_now):
    repo = get_user_repo()
    repo.create(42, "Alice")
    repo.link_telegram_to_auth(42, "auth-42")

    fetched = repo.get_by_auth_uid("auth-42")
    assert fetched is not None
    assert fetched.id == "42"


def test_link_telegram_to_auth_updates_user(fake_db, frozen_now):
    repo = get_user_repo()
    repo.create(42, "Alice")
    repo.link_telegram_to_auth(42, "auth-42")

    assert repo.get(42).auth_uid == "auth-42"


# ── Protocol conformance ────────────────────────────────────────────

def test_firestore_impl_satisfies_protocol():
    """``isinstance`` check works because ``UserRepo`` is runtime_checkable."""
    from services.repositories.protocols import UserRepo

    assert isinstance(FirestoreUserRepo(), UserRepo)
