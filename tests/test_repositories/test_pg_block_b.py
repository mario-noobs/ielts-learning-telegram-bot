"""Block-B Postgres repo smoke tests (M8 #234).

Group state: groups, group_daily_words, group_challenges,
group_challenge_answers. close_atomic() is the highest-risk function —
it serializes a multi-table transaction with row-level locks and bumps
the winner's challenge_wins counter, so 3 of the 6 tests focus on it.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from services import firebase_service
from services.db import get_sync_session
from services.repositories import (
    get_group_challenges_repo,
    get_groups_repo,
    get_user_repo,
)


@pytest.fixture
def fresh_group():
    """Yield a synthetic group_id with cleanup after the test."""
    # Negative chat_ids only (Telegram convention) so we don't collide
    # with any real BIGINT ids.
    gid = -abs(int(uuid.uuid4().int >> 96))
    yield gid
    with get_sync_session() as s, s.begin():
        s.execute(text("DELETE FROM groups WHERE id = :gid"), {"gid": gid})


@pytest.fixture
def fresh_user_id():
    """Create a user with a unique numeric id so it's eligible to be a
    group_members.telegram_id (which only accepts numeric ids)."""
    tg_id = int(uuid.uuid4().int >> 96)
    user = get_user_repo().create(
        telegram_id=tg_id, name="TestUser",
    )
    yield int(user.id)
    with get_sync_session() as s, s.begin():
        s.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})


def test_create_group_persists_owner_and_topics(fresh_group):
    firebase_service.create_group(
        fresh_group, settings={"topics": ["health", "science"]},
        owner_telegram_id=99999,
    )
    g = firebase_service.get_group_settings(fresh_group)
    assert g is not None
    assert g["owner_telegram_id"] == 99999
    assert g["topics"] == ["health", "science"]
    # Defaults from config picked up
    assert g["daily_time"]  # not None


def test_update_group_settings_drops_unknown_fields(fresh_group):
    firebase_service.create_group(fresh_group, owner_telegram_id=1)
    # `challenge_deadline_minutes` is app-config, not group state — repo
    # silently drops it instead of crashing on Unconsumed column.
    firebase_service.update_group_settings(
        fresh_group, {"daily_time": "06:00", "challenge_deadline_minutes": 60},
    )
    g = firebase_service.get_group_settings(fresh_group)
    assert g["daily_time"] == "06:00"


def test_list_groups_for_user_via_users_group_id(fresh_group, fresh_user_id):
    firebase_service.create_group(fresh_group, owner_telegram_id=fresh_user_id)
    # Mark user's group_id so the legacy /start-in-group flow is exercised.
    get_user_repo().update(fresh_user_id, {"group_id": fresh_group})
    groups = get_groups_repo().list_for_user(fresh_user_id)
    assert len(groups) == 1
    assert int(groups[0]["id"]) == fresh_group


def test_save_challenge_answer_merges_responses(fresh_group):
    firebase_service.create_group(fresh_group)
    firebase_service.save_challenge(fresh_group, "2099-01-15", [{"q": "?"}, {"q": "?"}])
    firebase_service.save_challenge_answer(
        fresh_group, "2099-01-15", 777, 0, True, display_name="Carol",
    )
    firebase_service.save_challenge_answer(
        fresh_group, "2099-01-15", 777, 1, False, display_name="Carol",
    )
    ans = firebase_service.get_user_challenge_answers(
        fresh_group, "2099-01-15", 777,
    )
    assert ans["responses"] == {"0": True, "1": False}
    assert ans["display_name"] == "Carol"  # captured on first save


def test_close_atomic_picks_highest_score_winner_and_bumps_counter(
    fresh_group, fresh_user_id,
):
    firebase_service.create_group(fresh_group, owner_telegram_id=fresh_user_id)
    firebase_service.save_challenge(
        fresh_group, "2099-02-01", [{"q": "1"}, {"q": "2"}, {"q": "3"}],
    )
    # Winner: 3/3 correct
    for q in range(3):
        firebase_service.save_challenge_answer(
            fresh_group, "2099-02-01", fresh_user_id, q, True, display_name="Winner",
        )
    firebase_service.mark_challenge_answer_complete(
        fresh_group, "2099-02-01", fresh_user_id,
    )
    # Loser: 1/3 correct
    firebase_service.save_challenge_answer(
        fresh_group, "2099-02-01", 88888, 0, True, display_name="Loser",
    )
    firebase_service.save_challenge_answer(
        fresh_group, "2099-02-01", 88888, 1, False, display_name="Loser",
    )
    firebase_service.mark_challenge_answer_complete(
        fresh_group, "2099-02-01", 88888,
    )

    before_wins = get_user_repo().get(fresh_user_id).challenge_wins or 0

    result = firebase_service.close_challenge_atomic(fresh_group, "2099-02-01")
    assert result["status"] == "closed"
    assert result["participants"][str(fresh_user_id)] == 3
    assert result["participants"]["88888"] == 1
    assert result["display_names"][str(fresh_user_id)] == "Winner"

    # Winner's counter bumped in the same txn
    after = get_user_repo().get(fresh_user_id)
    assert (after.challenge_wins or 0) == before_wins + 1


def test_close_atomic_is_idempotent(fresh_group):
    firebase_service.create_group(fresh_group)
    firebase_service.save_challenge(fresh_group, "2099-03-01", [{"q": "?"}])
    first = firebase_service.close_challenge_atomic(fresh_group, "2099-03-01")
    assert first["status"] == "closed"
    second = firebase_service.close_challenge_atomic(fresh_group, "2099-03-01")
    assert second["status"] == "closed"
