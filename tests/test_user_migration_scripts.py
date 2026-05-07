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

    fake_fs = {r["id"]: {k: v for k, v in r.items() if k != "id"} for r in rows}

    def fake_count():
        return len(fake_fs)

    def fake_ids():
        return list(fake_fs.keys())

    def fake_row(doc_id):
        return fake_fs.get(doc_id)

    with patch("scripts.verify_user_migration._firestore_count", fake_count), \
         patch("scripts.verify_user_migration._firestore_ids", fake_ids), \
         patch("scripts.verify_user_migration._firestore_row", fake_row), \
         patch("scripts.verify_user_migration._get_db", lambda: None):
        rc = verify_run(sample_size=50)
    assert rc == 0


def test_verify_fails_on_count_mismatch() -> None:
    from scripts.backfill_users_to_postgres import _upsert_batch
    from scripts.verify_user_migration import run as verify_run

    _upsert_batch([_make_row("1")])

    with patch("scripts.verify_user_migration._firestore_count", lambda: 99), \
         patch("scripts.verify_user_migration._get_db", lambda: None):
        rc = verify_run(sample_size=50)
    assert rc == 1


def test_verify_fails_on_field_drift() -> None:
    from scripts.backfill_users_to_postgres import _upsert_batch
    from scripts.verify_user_migration import run as verify_run

    _upsert_batch([_make_row("1", name="postgres-name")])

    fake_fs = {"1": {f: None for f in [
        "name", "username", "email", "auth_uid", "group_id", "target_band",
        "topics", "daily_time", "timezone", "streak", "last_active",
        "total_words", "total_quizzes", "total_correct", "challenge_wins",
        "exam_date", "weekly_goal_minutes", "created_at",
    ]}}
    fake_fs["1"]["name"] = "firestore-name"  # deliberate drift

    with patch("scripts.verify_user_migration._firestore_count", lambda: 1), \
         patch("scripts.verify_user_migration._firestore_ids", lambda: ["1"]), \
         patch("scripts.verify_user_migration._firestore_row", lambda i: fake_fs[i]), \
         patch("scripts.verify_user_migration._get_db", lambda: None):
        rc = verify_run(sample_size=50)
    assert rc == 1
