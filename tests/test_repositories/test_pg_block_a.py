"""Block-A Postgres repo smoke tests (M8 #234).

Exercises the critical paths that real callers depend on:

  * UserVocabulary: insert + dedupe + topic-mastery aggregate
  * QuizHistory: save_result bumps user counters atomically
  * WritingHistory: round-trip with structured + JSONB tail
  * ListeningHistory: shape compatibility with legacy dict callers

Tests run against the local Postgres dev DB (``DATABASE_URL`` in .env).
Each test creates its own user with a uuid4 id and cleans up via a
fixture so tests are independent and can run in any order.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from services.db import get_sync_session
from services.repositories import (
    get_listening_history_repo,
    get_quiz_history_repo,
    get_user_repo,
    get_vocab_repo,
    get_writing_history_repo,
)


@pytest.fixture
def fresh_user():
    uid = f"web_test_{uuid.uuid4().hex[:12]}"
    get_user_repo().create_web_user(
        auth_uid=f"auth_{uid}",
        email=f"{uid}@test.local",
        name="Test User",
    )
    # Re-read to get the actual id (create_web_user assigns a fresh one)
    user = next(
        u for u in get_user_repo().list_all() if u.auth_uid == f"auth_{uid}"
    )
    yield user.id
    # Cleanup the user + cascade everything we wrote.
    with get_sync_session() as s, s.begin():
        s.execute(
            text(
                "DELETE FROM listening_history WHERE user_id = :uid;"
                "DELETE FROM writing_history WHERE user_id = :uid;"
                "DELETE FROM quiz_history WHERE user_id = :uid;"
                "DELETE FROM user_daily_words WHERE user_id = :uid;"
                "DELETE FROM user_vocabulary WHERE user_id = :uid;"
                "DELETE FROM users WHERE id = :uid;"
            ),
            {"uid": user.id},
        )


def test_add_word_inserts_row_and_bumps_user_total(fresh_user):
    repo = get_vocab_repo()
    word_id = repo.add_word(fresh_user, {
        "word": "resilient",
        "topic": "society",  # slug — repo resolves to topic_id
        "definition_en": "able to recover quickly",
    })
    assert isinstance(word_id, str) and word_id

    item = repo.get_by_id(fresh_user, word_id)
    assert item is not None
    assert item.word == "resilient"
    assert item.topic == "society"
    assert item.definition_en == "able to recover quickly"

    # User counter bumped via increment_counters.
    user = get_user_repo().get(fresh_user)
    assert user.total_words == 1


def test_add_word_if_not_exists_is_idempotent(fresh_user):
    repo = get_vocab_repo()
    payload = {"word": "Abandon", "topic": "education"}  # mixed case
    id1, created1 = repo.add_word_if_not_exists(fresh_user, payload)
    assert created1 is True

    # Same word, different case + punctuation — normalized_word UNIQUE
    # constraint catches the dupe.
    id2, created2 = repo.add_word_if_not_exists(
        fresh_user, {"word": "abandon!", "topic": "education"},
    )
    assert created2 is False
    assert id2 == id1

    user = get_user_repo().get(fresh_user)
    assert user.total_words == 1, "counter must not bump on dedupe hit"


def test_count_by_topic_with_mastery_aggregates(fresh_user):
    repo = get_vocab_repo()
    repo.add_word(fresh_user, {"word": "alpha", "topic": "technology"})
    repo.add_word(fresh_user, {"word": "beta", "topic": "technology"})
    repo.add_word(fresh_user, {"word": "gamma", "topic": "education"})
    # Promote alpha to mastered (srs_interval > 30).
    items = repo.list_by_user(fresh_user, limit=50)
    alpha = next(i for i in items if i.word == "alpha")
    repo.update_srs(fresh_user, alpha.id, {"srs_interval": 60, "srs_reps": 5})

    stats = repo.count_by_topic_with_mastery(fresh_user)
    assert stats["technology"] == {"total": 2, "mastered": 1}
    assert stats["education"] == {"total": 1, "mastered": 0}


def test_save_quiz_result_bumps_total_and_correct(fresh_user):
    qrepo = get_quiz_history_repo()
    qrepo.save_result(fresh_user, {"type": "mcq", "is_correct": True})
    qrepo.save_result(fresh_user, {"type": "mcq", "is_correct": False})

    user = get_user_repo().get(fresh_user)
    assert user.total_quizzes == 2
    assert user.total_correct == 1

    latest = qrepo.get_latest(fresh_user)
    assert latest is not None
    assert latest.is_correct is False  # most-recent wins


def test_writing_submission_round_trips_with_jsonb_tail(fresh_user):
    repo = get_writing_history_repo()
    sid = repo.save_submission(fresh_user, {
        "task_type": "task2",
        "prompt": "Discuss…",
        "text": "My essay body.",
        "overall_band": 6.5,
        "word_count": 4,
        "scores": {"task_response": 6.5, "coherence_cohesion": 6.5},
        "criterion_feedback": {"task_response": "Strong stance."},
        # Loose tail — should land in feedback JSONB and round-trip back.
        "extra_field": "preserved",
    })
    out = repo.get_submission(fresh_user, sid)
    assert out.text == "My essay body."
    assert out.overall_band == 6.5
    # extra="allow" on the DTO surfaces JSONB fields by attribute access.
    assert out.scores["task_response"] == 6.5
    assert out.criterion_feedback["task_response"] == "Strong stance."
    assert out.extra_field == "preserved"


def test_listening_history_update_merges_jsonb_tail(fresh_user):
    repo = get_listening_history_repo()
    eid = repo.save(fresh_user, {
        "exercise_type": "gap_fill",
        "score": 7,
        "total": 10,
        "transcript": "original transcript",  # tail
    })
    # Update with a structured field + new tail field.
    repo.update(fresh_user, eid, {"submitted": True, "user_answers": ["a", "b"]})

    out = repo.get(fresh_user, eid)
    assert out["score"] == 7  # unchanged
    assert out["submitted"] is True  # structured update applied
    assert out["transcript"] == "original transcript"  # tail preserved
    assert out["user_answers"] == ["a", "b"]  # new tail merged
