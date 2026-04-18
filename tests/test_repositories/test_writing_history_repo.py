"""Tests for ``services.repositories.firestore.writing_history_repo``."""

from __future__ import annotations

from services.repositories import (
    WritingHistoryEntry,
    get_user_repo,
    get_writing_history_repo,
)
from services.repositories.firestore import FirestoreWritingHistoryRepo

# ── save / save_submission ──────────────────────────────────────────

def test_save_persists_without_returning_id(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_writing_history_repo()

    result = repo.save(1, {"text": "An essay.", "task_type": "task2"})
    assert result is None

    listed = repo.list_submissions(1)
    assert len(listed) == 1
    assert listed[0].text == "An essay."
    assert listed[0].created_at == frozen_now


def test_save_submission_returns_id(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_writing_history_repo()

    submission_id = repo.save_submission(1, {
        "text": "Another essay.",
        "task_type": "task1",
        "overall_band": 7.5,
    })
    assert isinstance(submission_id, str) and submission_id

    fetched = repo.get_submission(1, submission_id)
    assert fetched is not None
    assert fetched.text == "Another essay."
    assert fetched.task_type == "task1"
    assert fetched.overall_band == 7.5


# ── get_submission ──────────────────────────────────────────────────

def test_get_submission_missing_returns_none(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    assert get_writing_history_repo().get_submission(1, "nope") is None


def test_get_submission_returns_dto(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_writing_history_repo()
    sid = repo.save_submission(1, {"text": "x"})
    assert isinstance(repo.get_submission(1, sid), WritingHistoryEntry)


# ── list_submissions ────────────────────────────────────────────────

def test_list_submissions_orders_desc(fake_db):
    from datetime import datetime, timedelta, timezone

    get_user_repo().create(1, "A")
    base = datetime(2026, 4, 1, tzinfo=timezone.utc)

    for i in range(3):
        fake_db.collection("users").document("1").collection(
            "writing_history"
        ).document(f"s{i}").set({
            "text": f"essay {i}",
            "task_type": "task2",
            "created_at": base + timedelta(days=i),
        })

    listed = get_writing_history_repo().list_submissions(1)
    assert [s.text for s in listed] == ["essay 2", "essay 1", "essay 0"]


def test_list_submissions_respects_limit(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_writing_history_repo()
    for i in range(5):
        repo.save_submission(1, {"text": f"essay {i}"})

    assert len(repo.list_submissions(1, limit=2)) == 2


def test_list_submissions_empty(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    assert get_writing_history_repo().list_submissions(1) == []


# ── Protocol conformance ────────────────────────────────────────────

def test_firestore_impl_satisfies_protocol():
    from services.repositories.protocols import WritingHistoryRepo

    assert isinstance(FirestoreWritingHistoryRepo(), WritingHistoryRepo)
