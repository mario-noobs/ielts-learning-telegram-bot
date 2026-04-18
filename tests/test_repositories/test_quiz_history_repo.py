"""Tests for ``services.repositories.firestore.quiz_history_repo``."""

from __future__ import annotations

from services.repositories import (
    QuizHistoryEntry,
    get_quiz_history_repo,
    get_user_repo,
)
from services.repositories.firestore import FirestoreQuizHistoryRepo

# ── save_result ─────────────────────────────────────────────────────

def test_save_result_bumps_total_and_correct(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_quiz_history_repo()

    repo.save_result(1, {
        "question": "Define 'resilient'",
        "is_correct": True,
        "word_id": "w1",
    })

    user = get_user_repo().get(1)
    assert user.total_quizzes == 1
    assert user.total_correct == 1


def test_save_result_wrong_answer_only_bumps_total(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_quiz_history_repo()

    repo.save_result(1, {"is_correct": False})

    user = get_user_repo().get(1)
    assert user.total_quizzes == 1
    assert user.total_correct == 0


def test_save_result_multiple_accumulates(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_quiz_history_repo()
    repo.save_result(1, {"is_correct": True})
    repo.save_result(1, {"is_correct": True})
    repo.save_result(1, {"is_correct": False})

    user = get_user_repo().get(1)
    assert user.total_quizzes == 3
    assert user.total_correct == 2


def test_save_result_writes_created_at(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_quiz_history_repo()
    repo.save_result(1, {"is_correct": True, "word_id": "w1"})

    latest = repo.get_latest(1)
    assert latest is not None
    assert latest.created_at == frozen_now


# ── get_latest ──────────────────────────────────────────────────────

def test_get_latest_empty_returns_none(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    assert get_quiz_history_repo().get_latest(1) is None


def test_get_latest_returns_most_recent(fake_db):
    get_user_repo().create(1, "A")
    repo = get_quiz_history_repo()

    # Seed with increasing created_at so ordering matters
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 4, 10, tzinfo=timezone.utc)
    for i in range(3):
        # Write directly via the fake client to control created_at
        fake_db.collection("users").document("1").collection("quiz_history").document(
            f"q{i}"
        ).set({
            "is_correct": i % 2 == 0,
            "created_at": base + timedelta(days=i),
            "label": f"q{i}",
        })

    latest = repo.get_latest(1)
    assert latest is not None
    # Using our VocabularyItem-esque DTO with extra allowed — ``label``
    # survives the round-trip
    dumped = latest.model_dump()
    assert dumped.get("label") == "q2"


def test_get_latest_returns_dto_type(fake_db):
    get_user_repo().create(1, "A")
    from datetime import datetime, timezone
    fake_db.collection("users").document("1").collection("quiz_history").document(
        "only"
    ).set({
        "is_correct": True,
        "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
    })
    result = get_quiz_history_repo().get_latest(1)
    assert isinstance(result, QuizHistoryEntry)


# ── Protocol conformance ────────────────────────────────────────────

def test_firestore_impl_satisfies_protocol():
    from services.repositories.protocols import QuizHistoryRepo

    assert isinstance(FirestoreQuizHistoryRepo(), QuizHistoryRepo)
