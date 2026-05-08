"""Unit-level tests for US-M12.1 merge + unlink helpers.

- ``FirestoreUserRepo.copy_subcollections`` — covered against the
  in-memory fake Firestore via ``fake_db``.
- ``PostgresUserRepo.merge_into`` and ``unlink_auth`` —
  Postgres-gated (skipped without ``DATABASE_URL``).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select


# ── FirestoreUserRepo.copy_subcollections (uses fake_db) ─────────────

def test_copy_subcollections_vocab_dedupe_by_word(fake_db):
    """Dedupe by lowercased word; entry with greater srs_reps wins."""
    from services.repositories.firestore import FirestoreUserRepo

    repo = FirestoreUserRepo()
    src_root = fake_db.collection("users").document("web_a")
    tg_root = fake_db.collection("users").document("12345")

    src_root.collection("vocabulary").document("v1").set(
        {"word": "Resilient", "srs_reps": 5, "topic": "psychology"},
    )
    tg_root.collection("vocabulary").document("v2").set(
        {"word": "resilient", "srs_reps": 1, "topic": "psychology"},
    )

    counts = repo.copy_subcollections("web_a", "12345")

    assert counts["vocab_merged"] == 1
    assert counts["vocab_dropped"] == 0
    # Target should now hold the higher-srs_reps version (overwrote v2).
    target_vocab = list(tg_root.collection("vocabulary").stream())
    assert len(target_vocab) == 1
    assert target_vocab[0].to_dict()["srs_reps"] == 5


def test_copy_subcollections_vocab_drops_lower_reps(fake_db):
    from services.repositories.firestore import FirestoreUserRepo

    repo = FirestoreUserRepo()
    fake_db.collection("users").document("web_a").collection("vocabulary").document(
        "v1",
    ).set({"word": "fluent", "srs_reps": 1})
    fake_db.collection("users").document("12345").collection("vocabulary").document(
        "v2",
    ).set({"word": "fluent", "srs_reps": 4})

    counts = repo.copy_subcollections("web_a", "12345")

    assert counts["vocab_dropped"] == 1
    assert counts["vocab_merged"] == 0


def test_copy_subcollections_quiz_history_appends(fake_db):
    from services.repositories.firestore import FirestoreUserRepo

    repo = FirestoreUserRepo()
    src_root = fake_db.collection("users").document("web_a")
    tg_root = fake_db.collection("users").document("12345")

    for i in range(4):
        src_root.collection("quiz_history").document(f"q_src_{i}").set(
            {"is_correct": True},
        )
    for i in range(6):
        tg_root.collection("quiz_history").document(f"q_tg_{i}").set(
            {"is_correct": False},
        )

    counts = repo.copy_subcollections("web_a", "12345")

    assert counts["quiz_merged"] == 4
    assert len(list(tg_root.collection("quiz_history").stream())) == 10


def test_copy_subcollections_daily_words_target_wins(fake_db):
    from services.repositories.firestore import FirestoreUserRepo

    repo = FirestoreUserRepo()
    src = fake_db.collection("users").document("web_a")
    tg = fake_db.collection("users").document("12345")

    src.collection("daily_words").document("2026-05-08").set(
        {"words": [{"word": "from_web"}], "topic": "edu"},
    )
    tg.collection("daily_words").document("2026-05-08").set(
        {"words": [{"word": "from_tg"}], "topic": "tech"},
    )

    counts = repo.copy_subcollections("web_a", "12345")

    assert counts["daily_skipped"] == 1
    assert counts["daily_merged"] == 0
    # Target unchanged
    target_doc = tg.collection("daily_words").document("2026-05-08").get().to_dict()
    assert target_doc["words"][0]["word"] == "from_tg"


# ── Postgres merge_into / unlink_auth (gated) ────────────────────────

pytestmark = []


def _pg_skip():
    return pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"),
        reason="DATABASE_URL not set; skipping Postgres merge tests",
    )


@_pg_skip()
def test_merge_into_atomic_apply_and_delete():
    from services.db import get_sync_session
    from services.db.models import User
    from services.repositories.postgres import PostgresUserRepo

    repo = PostgresUserRepo()
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.execute(delete(User))
        s.add(User(
            id="web_xxxxxxxxxxxx",
            name="W", username="", email="w@e.test",
            auth_uid="auth-foo",
            target_band=7.5, topics=["education"],
            streak=2, total_words=12, total_quizzes=3, total_correct=2,
            challenge_wins=0, role="platform_admin", plan="personal_pro",
            created_at=now,
        ))
        s.add(User(
            id="555", name="T", username="t", email="",
            auth_uid=None,
            target_band=7.0, topics=["tech"],
            streak=5, total_words=8, total_quizzes=10, total_correct=7,
            challenge_wins=1, role="user", plan="free", created_at=now,
        ))

    repo.merge_into(
        "web_xxxxxxxxxxxx",
        "555",
        merged={
            "auth_uid": "auth-foo",
            "email": "w@e.test",
            "role": "platform_admin",
            "plan": "personal_pro",
            "total_words": 18,
            "total_quizzes": 13,
            "total_correct": 9,
        },
    )

    with get_sync_session() as s:
        rows = s.execute(select(User)).scalars().all()
    assert len(rows) == 1
    survivor = rows[0]
    assert survivor.id == "555"
    assert survivor.auth_uid == "auth-foo"
    assert survivor.role == "platform_admin"
    assert survivor.plan == "personal_pro"
    assert survivor.total_words == 18
    # Cleanup
    with get_sync_session() as s, s.begin():
        s.execute(delete(User))


@_pg_skip()
def test_merge_into_raises_when_row_missing():
    from services.db import get_sync_session
    from services.db.models import User
    from services.repositories.postgres import PostgresUserRepo

    with get_sync_session() as s, s.begin():
        s.execute(delete(User))

    with pytest.raises(ValueError, match="missing row"):
        PostgresUserRepo().merge_into("nope_a", "nope_b", merged={"role": "user"})


@_pg_skip()
def test_unlink_auth_returns_previous_uid():
    from services.db import get_sync_session
    from services.db.models import User
    from services.repositories.postgres import PostgresUserRepo

    repo = PostgresUserRepo()
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.execute(delete(User))
        s.add(User(
            id="42", name="A", username="", email="",
            auth_uid="auth-42",
            target_band=7.0, topics=["edu"],
            streak=0, total_words=0, total_quizzes=0, total_correct=0,
            challenge_wins=0, role="user", plan="free", created_at=now,
        ))

    previous = repo.unlink_auth(42)
    assert previous == "auth-42"

    fetched = repo.get(42)
    assert fetched is not None
    assert fetched.auth_uid is None
    with get_sync_session() as s, s.begin():
        s.execute(delete(User))


@_pg_skip()
def test_unlink_auth_idempotent_returns_none():
    from services.db import get_sync_session
    from services.db.models import User
    from services.repositories.postgres import PostgresUserRepo

    repo = PostgresUserRepo()
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.execute(delete(User))
        s.add(User(
            id="43", name="B", username="", email="",
            auth_uid=None,
            target_band=7.0, topics=["edu"],
            streak=0, total_words=0, total_quizzes=0, total_correct=0,
            challenge_wins=0, role="user", plan="free", created_at=now,
        ))

    assert repo.unlink_auth(43) is None
    with get_sync_session() as s, s.begin():
        s.execute(delete(User))


@_pg_skip()
def test_unlink_auth_returns_none_when_row_missing():
    from services.db import get_sync_session
    from services.db.models import User
    from services.repositories.postgres import PostgresUserRepo

    with get_sync_session() as s, s.begin():
        s.execute(delete(User))

    assert PostgresUserRepo().unlink_auth(9999) is None
