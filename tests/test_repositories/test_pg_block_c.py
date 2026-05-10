"""Block-C Postgres repo smoke tests (M8 #234) — sessions + TTL cleanup."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from services import firebase_service
from services.db import get_sync_session
from services.repositories import (
    get_quiz_sessions_repo,
    get_reading_sessions_repo,
    get_user_repo,
)


@pytest.fixture
def fresh_user():
    uid = f"web_test_{uuid.uuid4().hex[:12]}"
    user = get_user_repo().create_web_user(
        auth_uid=f"auth_{uid}",
        email=f"{uid}@test.local",
        name="Test User",
    )
    actual = next(
        u for u in get_user_repo().list_all() if u.auth_uid == f"auth_{uid}"
    )
    yield actual.id
    with get_sync_session() as s, s.begin():
        s.execute(
            text("DELETE FROM users WHERE id = :uid"),
            {"uid": actual.id},
        )


def test_save_quiz_session_replaces_existing(fresh_user):
    sid = uuid.uuid4().hex
    firebase_service.save_quiz_session(
        fresh_user, sid, [{"q": "first", "id": "q1"}],
    )
    firebase_service.mark_session_question_answered(fresh_user, sid, "q1")

    # Re-saving the same session_id should reset to fresh state.
    firebase_service.save_quiz_session(
        fresh_user, sid, [{"q": "second", "id": "qX"}],
    )
    qs = firebase_service.get_quiz_session(fresh_user, sid)
    assert qs["questions"][0]["q"] == "second"
    assert qs["answered_ids"] == []  # reset on re-save


def test_mark_question_answered_is_idempotent(fresh_user):
    sid = uuid.uuid4().hex
    firebase_service.save_quiz_session(fresh_user, sid, [{"id": "q1"}])
    firebase_service.mark_session_question_answered(fresh_user, sid, "q1")
    firebase_service.mark_session_question_answered(fresh_user, sid, "q1")
    qs = firebase_service.get_quiz_session(fresh_user, sid)
    assert qs["answered_ids"] == ["q1"]


def test_reading_session_update_preserves_unrelated_fields(fresh_user):
    sid = "rs_" + uuid.uuid4().hex[:12]
    firebase_service.save_reading_session(fresh_user, sid, {
        "passage_id": "p001",
        "questions": [{"id": "q1"}],
        "answer_key": [{"id": "q1", "answer": "A"}],
        "status": "in_progress",
    })
    firebase_service.update_reading_session(
        fresh_user, sid, {"status": "submitted", "grade": {"band": 7.0}},
    )
    rs = firebase_service.get_reading_session(fresh_user, sid)
    assert rs["status"] == "submitted"
    assert rs["grade"] == {"band": 7.0}
    # Untouched fields preserved.
    assert rs["passage_id"] == "p001"
    assert rs["questions"] == [{"id": "q1"}]


def test_list_reading_sessions_orders_by_updated_at_desc(fresh_user):
    sid_old = "rs_" + uuid.uuid4().hex[:12]
    sid_new = "rs_" + uuid.uuid4().hex[:12]
    firebase_service.save_reading_session(fresh_user, sid_old, {"passage_id": "p001"})
    firebase_service.save_reading_session(fresh_user, sid_new, {"passage_id": "p002"})
    # Touch sid_old AFTER sid_new so it sorts newest-first.
    firebase_service.update_reading_session(
        fresh_user, sid_old, {"status": "submitted"},
    )

    sessions = firebase_service.list_reading_sessions(fresh_user, limit=10)
    assert sessions[0]["id"] == sid_old
    assert sessions[1]["id"] == sid_new


def test_cleanup_deletes_old_sessions_only(fresh_user):
    """Sessions older than the cutoff get deleted; recent ones stay."""
    fresh_sid = uuid.uuid4().hex
    stale_sid = uuid.uuid4().hex
    firebase_service.save_quiz_session(fresh_user, fresh_sid, [])
    firebase_service.save_quiz_session(fresh_user, stale_sid, [])

    # Backdate one row past the 7-day cutoff.
    with get_sync_session() as s, s.begin():
        s.execute(
            text(
                "UPDATE quiz_sessions SET created_at = :ts WHERE id = :sid"
            ),
            {
                "ts": datetime.now(timezone.utc) - timedelta(days=10),
                "sid": stale_sid,
            },
        )

    deleted = get_quiz_sessions_repo().cleanup_older_than(days=7)
    assert deleted >= 1
    assert firebase_service.get_quiz_session(fresh_user, stale_sid) is None
    assert firebase_service.get_quiz_session(fresh_user, fresh_sid) is not None
