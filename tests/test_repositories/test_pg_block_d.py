"""Block-D Postgres repo smoke tests (M8 #234) — analytics + rollup."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from services import firebase_service
from services.db import get_sync_session
from services.repositories import (
    get_daily_plans_repo,
    get_progress_recommendations_repo,
    get_progress_snapshots_repo,
    get_user_repo,
)


@pytest.fixture
def fresh_user():
    uid = f"web_test_{uuid.uuid4().hex[:12]}"
    get_user_repo().create_web_user(
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


def test_save_daily_plan_round_trips(fresh_user):
    firebase_service.save_daily_plan(fresh_user, "2099-04-01", {
        "activities": [{"id": "srs", "completed": False}],
        "cap_minutes": 30,
        "completed_count": 0,
        "total_minutes": 25,
        "exam_urgent": False,
    })
    plan = firebase_service.get_daily_plan(fresh_user, "2099-04-01")
    assert plan["cap_minutes"] == 30
    assert plan["activities"][0]["id"] == "srs"
    assert plan["exam_urgent"] is False


def test_complete_plan_activity_atomic_and_idempotent(fresh_user):
    firebase_service.save_daily_plan(fresh_user, "2099-04-02", {
        "activities": [
            {"id": "srs", "completed": False},
            {"id": "writing", "completed": False},
        ],
        "completed_count": 0,
    })

    out = firebase_service.complete_plan_activity(fresh_user, "2099-04-02", "srs")
    assert out["completed_count"] == 1
    assert any(a["id"] == "srs" and a["completed"] for a in out["activities"])

    # Re-completing is a no-op (idempotent)
    out2 = firebase_service.complete_plan_activity(fresh_user, "2099-04-02", "srs")
    assert out2["completed_count"] == 1

    # Unknown activity id surfaces as "NOT_FOUND"
    out3 = firebase_service.complete_plan_activity(fresh_user, "2099-04-02", "ghost")
    assert out3 == "NOT_FOUND"


def test_progress_snapshot_save_and_list_for_dates(fresh_user):
    firebase_service.save_progress_snapshot(fresh_user, "2099-05-01", {
        "overall_band": 6.5, "target_band": 7.0,
        "skills": {"writing": {"band": 6.5, "sample_size": 5}},
    })
    firebase_service.save_progress_snapshot(fresh_user, "2099-05-02", {
        "overall_band": 6.0, "target_band": 7.0, "skills": {},
    })

    snaps = firebase_service.list_progress_snapshots(
        fresh_user, ["2099-05-01", "2099-05-02", "2099-12-31"],
    )
    # Skips missing dates — we only seeded 2 rows.
    assert len(snaps) == 2
    bands = sorted(s["overall_band"] for s in snaps)
    assert bands == [6.0, 6.5]


def test_progress_recommendations_round_trip(fresh_user):
    firebase_service.save_progress_recommendations(
        fresh_user, "2099-W01",
        {"tips": [{"skill": "listening", "tip_vi": "luyện nghe"}]},
    )
    rec = firebase_service.get_progress_recommendations(fresh_user, "2099-W01")
    assert rec["week_key"] == "2099-W01"
    assert rec["tips"][0]["skill"] == "listening"


def test_rollup_daily_review_snapshots_aggregates_correctly(fresh_user):
    """Backdate review_events into yesterday's window, then run rollup."""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    backdated = datetime.combine(
        yesterday, datetime.min.time(), tzinfo=timezone.utc,
    ) + timedelta(hours=10)

    with get_sync_session() as s, s.begin():
        # 3 review events: 2 correct (result>=3), 1 fail
        for grade in (5, 4, 1):
            s.execute(
                text(
                    "INSERT INTO review_events "
                    "(user_id, user_vocab_id, result, source, created_at) "
                    "VALUES (:uid, 'fake_vocab', :result, 1, :ts)"
                ),
                {"uid": fresh_user, "result": grade, "ts": backdated},
            )

    from scripts.rollup_daily_review_snapshots import rollup
    rollup(yesterday)

    with get_sync_session() as s:
        row = s.execute(
            text(
                "SELECT reviews_done, reviews_correct "
                "FROM daily_review_snapshots "
                "WHERE user_id = :uid AND snapshot_date = :d"
            ),
            {"uid": fresh_user, "d": yesterday},
        ).fetchone()

    assert row.reviews_done == 3
    assert row.reviews_correct == 2

    # Cleanup the synthetic events (review_events is immutable — ALTER TABLE
    # to drop the rule temporarily).
    with get_sync_session() as s, s.begin():
        s.execute(text("ALTER TABLE review_events DISABLE RULE no_delete_review_events"))
        s.execute(
            text("DELETE FROM review_events WHERE user_id = :uid"),
            {"uid": fresh_user},
        )
        s.execute(text("ALTER TABLE review_events ENABLE RULE no_delete_review_events"))
