"""Unit tests for the M8.2 migration scripts (US-M8.2 / GH#131).

These don't talk to Firestore; they exercise the Postgres-side logic
(idempotent upsert, drift detection) by feeding synthetic input. The
actual Firestore round-trip is verified manually before the cutover
PR ships.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping migration script tests",
)


@pytest.fixture(autouse=True)
def _truncate_users():
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.execute(delete(User))
    yield
    with get_sync_session() as s, s.begin():
        s.execute(delete(User))


def _make_row(user_id: str, **overrides) -> dict:
    base = {
        "id": user_id,
        "name": f"user-{user_id}",
        "username": "",
        "email": None,
        "auth_uid": None,
        "group_id": None,
        "target_band": 7.0,
        "topics": ["education"],
        "daily_time": "08:00",
        "timezone": "Asia/Ho_Chi_Minh",
        "streak": 0,
        "last_active": datetime.now(timezone.utc),
        "total_words": 0,
        "total_quizzes": 0,
        "total_correct": 0,
        "challenge_wins": 0,
        "exam_date": None,
        "weekly_goal_minutes": None,
        "created_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


def test_backfill_upsert_idempotent_on_rerun() -> None:
    from scripts.backfill_users_to_postgres import _upsert_batch
    from services.db import get_sync_session
    from services.db.models import User

    rows = [_make_row("1", name="Alice"), _make_row("2", name="Bob")]

    _upsert_batch(rows)
    _upsert_batch(rows)  # rerun must not duplicate

    with get_sync_session() as s:
        users = s.execute(User.__table__.select()).all()
        assert len(users) == 2
        names = {u.id: u.name for u in [s.get(User, "1"), s.get(User, "2")]}
        assert names == {"1": "Alice", "2": "Bob"}


def test_backfill_upsert_overwrites_changed_fields() -> None:
    from scripts.backfill_users_to_postgres import _upsert_batch
    from services.db import get_sync_session
    from services.db.models import User

    _upsert_batch([_make_row("1", name="Old", target_band=6.0)])
    _upsert_batch([_make_row("1", name="New", target_band=8.5)])

    with get_sync_session() as s:
        u = s.get(User, "1")
        assert u.name == "New"
        assert u.target_band == 8.5


def test_verify_passes_when_stores_match() -> None:
    from scripts.backfill_users_to_postgres import _upsert_batch
    from scripts.verify_user_migration import run as verify_run

    rows = [_make_row("1", name="Alice"), _make_row("2", name="Bob")]
    _upsert_batch(rows)

    fake_fs = {r["id"]: r for r in rows}

    with patch("scripts.verify_user_migration._load_firestore_winners",
               lambda: fake_fs), \
         patch("scripts.verify_user_migration._get_db", lambda: None):
        rc = verify_run(sample_size=50)
    assert rc == 0


def test_verify_fails_on_count_mismatch() -> None:
    from scripts.backfill_users_to_postgres import _upsert_batch
    from scripts.verify_user_migration import run as verify_run

    _upsert_batch([_make_row("1")])

    fake_fs = {str(i): _make_row(str(i)) for i in range(99)}
    with patch("scripts.verify_user_migration._load_firestore_winners",
               lambda: fake_fs), \
         patch("scripts.verify_user_migration._get_db", lambda: None):
        rc = verify_run(sample_size=50)
    assert rc == 1


def test_verify_fails_on_field_drift() -> None:
    from scripts.backfill_users_to_postgres import _upsert_batch
    from scripts.verify_user_migration import run as verify_run

    _upsert_batch([_make_row("1", name="postgres-name")])

    fake_fs = {"1": _make_row("1", name="firestore-name")}
    with patch("scripts.verify_user_migration._load_firestore_winners",
               lambda: fake_fs), \
         patch("scripts.verify_user_migration._get_db", lambda: None):
        rc = verify_run(sample_size=50)
    assert rc == 1


def test_dedupe_by_auth_uid_pure() -> None:
    from scripts.backfill_users_to_postgres import _dedupe_by_auth_uid

    # Two rows share the same auth_uid; the higher-activity one wins.
    a = _make_row("real", auth_uid="X", total_words=100, total_quizzes=50)
    b = _make_row("stub", auth_uid="X", total_words=0, total_quizzes=0)
    c = _make_row("solo", auth_uid="Y", total_words=10)
    d = _make_row("noauth", auth_uid=None, total_words=5)

    winners, losers = _dedupe_by_auth_uid([b, a, c, d])
    winner_ids = {w["id"] for w in winners}
    loser_ids = {row["id"] for row in losers}
    assert winner_ids == {"real", "solo", "noauth"}
    assert loser_ids == {"stub"}


def test_dedupe_tiebreak_by_created_at() -> None:
    from scripts.backfill_users_to_postgres import _dedupe_by_auth_uid

    older = _make_row("old", auth_uid="Z",
                      created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = _make_row("new", auth_uid="Z",
                      created_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    winners, losers = _dedupe_by_auth_uid([newer, older])
    assert {w["id"] for w in winners} == {"old"}
    assert {row["id"] for row in losers} == {"new"}
