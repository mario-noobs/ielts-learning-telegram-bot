"""Tests for ``services.admin.metrics_service`` (US-M11.5)."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping metrics_service tests",
)


@pytest.fixture(autouse=True)
def _clean():
    """Wipe ai_usage + platform_metrics + audit_log between tests."""
    from services.db import get_sync_session
    from services.db.models import AiUsage, AuditLog, PlatformMetric

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AiUsage))
            s.execute(delete(AuditLog))
            s.execute(delete(PlatformMetric))

    _wipe()
    yield
    _wipe()


def _seed_ai_usage(user_uid: str, d: date, feature: str, count: int) -> None:
    """Direct INSERT — bypasses increment() so we control history dates."""
    from services.db import get_sync_session
    from services.db.models import AiUsage

    with get_sync_session() as s, s.begin():
        s.add(AiUsage(
            user_uid=user_uid, date=d, feature=feature,
            count=count,
            last_call_at=datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc),
        ))


def _seed_audit(event_type: str, actor_uid: str, target_kind: str, target_id: str,
                when: datetime) -> None:
    from services.db import get_sync_session
    from services.db.models import AuditLog

    with get_sync_session() as s, s.begin():
        s.add(AuditLog(
            event_type=event_type, actor_uid=actor_uid,
            target_kind=target_kind, target_id=target_id,
            before=None, after=None, request_id=None,
            created_at=when,
        ))


# ─── aggregate_daily ───────────────────────────────────────────────


def test_aggregate_daily_writes_one_row_and_is_idempotent() -> None:
    from services.admin import metrics_service
    from services.repositories import get_metrics_repo

    target = date(2026, 5, 1)
    fake_users = [
        {"id": "u1", "plan": "free", "last_active_date": target.isoformat(),
         "created_at": "2026-04-15"},
        {"id": "u2", "plan": "personal_pro",
         "last_active_date": (target - timedelta(days=1)).isoformat(),
         "created_at": target.isoformat()},
        {"id": "u3", "plan": "free",
         "last_active_date": target.isoformat(),
         "created_at": "2026-03-01"},
    ]
    _seed_ai_usage("u1", target, "vocab", 7)
    _seed_ai_usage("u2", target, "writing", 3)

    with patch("services.admin.metrics_service.firebase_service.get_all_users",
               return_value=fake_users):
        snap = metrics_service.aggregate_daily(target)
        # Re-run is idempotent (same numbers, same row).
        snap2 = metrics_service.aggregate_daily(target)

    assert snap["dau"] == 2
    assert snap["signups"] == 1
    assert snap["ai_calls"] == 10
    assert snap["plan_distribution"] == {"free": 2, "personal_pro": 1}
    assert snap == snap2

    rows = get_metrics_repo().get_range(target, target)
    assert len(rows) == 1
    assert rows[0].dau == 2
    assert rows[0].ai_calls == 10


# ─── dau_series ────────────────────────────────────────────────────


def test_dau_series_pads_missing_days_and_computes_mau_window() -> None:
    from services.admin import metrics_service
    from services.repositories import get_metrics_repo

    today = datetime.now(timezone.utc).date()
    repo = get_metrics_repo()
    repo.upsert_daily(today - timedelta(days=2), 10, 4, 1, 0, {"free": 10})
    repo.upsert_daily(today, 10, 6, 0, 0, {"free": 10})

    series = metrics_service.dau_series(3)
    assert len(series) == 3
    assert [p["dau"] for p in series] == [4, 0, 6]
    # MAU is the rolling sum of DAUs over the last 30 days; for a 3-day
    # window with no other data, it equals the cumulative sum.
    assert [p["mau"] for p in series] == [4, 4, 10]


# ─── ai_usage_series ───────────────────────────────────────────────


def test_ai_usage_series_groups_by_date_and_feature() -> None:
    from services.admin import metrics_service

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    _seed_ai_usage("u1", yesterday, "vocab", 3)
    _seed_ai_usage("u2", yesterday, "vocab", 2)
    _seed_ai_usage("u1", today, "writing", 5)

    series = metrics_service.ai_usage_series(7)
    by_key = {(p["date"], p["feature"]): p["count"] for p in series}
    assert by_key[(yesterday.isoformat(), "vocab")] == 5
    assert by_key[(today.isoformat(), "writing")] == 5


# ─── plan_distribution ─────────────────────────────────────────────


def test_plan_distribution_counts_users_by_plan() -> None:
    from services.admin import metrics_service

    fake_users = [
        {"id": "u1", "plan": "free"},
        {"id": "u2", "plan": "personal_pro"},
        {"id": "u3", "plan": "free"},
        {"id": "u4"},  # missing → defaults to 'free'
    ]
    with patch("services.admin.metrics_service.firebase_service.get_all_users",
               return_value=fake_users):
        out = metrics_service.plan_distribution()
    assert out == {"free": 3, "personal_pro": 1}


# ─── signup_cohorts ────────────────────────────────────────────────


def test_signup_cohorts_computes_d7_and_d30_retention() -> None:
    from services.admin import metrics_service

    today = datetime.now(timezone.utc).date()
    monday_today = today - timedelta(days=today.weekday())
    cohort_week = monday_today - timedelta(weeks=2)

    fake_users = [
        {"id": "alpha", "created_at": cohort_week.isoformat()},
        {"id": "beta", "created_at": cohort_week.isoformat()},
    ]
    # alpha is active in d7 window only; beta is active in d30 window only.
    _seed_ai_usage("alpha", cohort_week + timedelta(days=2), "vocab", 1)
    _seed_ai_usage("beta", cohort_week + timedelta(days=20), "vocab", 1)

    with patch("services.admin.metrics_service.firebase_service.get_all_users",
               return_value=fake_users):
        cohorts = metrics_service.signup_cohorts(weeks=4)

    target = next(c for c in cohorts if c["cohort_week"] == cohort_week.isoformat())
    assert target["signups"] == 2
    assert target["retained_d7"] == 1
    assert target["retained_d30"] == 2


# ─── audit_page ────────────────────────────────────────────────────


def test_audit_page_paginates_and_orders_desc() -> None:
    from services.admin import metrics_service

    base = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    for i in range(5):
        _seed_audit(
            event_type="user.role_granted",
            actor_uid="admin-1",
            target_kind="user",
            target_id=f"u{i}",
            when=base + timedelta(minutes=i),
        )

    p1 = metrics_service.audit_page(page=1, page_size=2)
    p2 = metrics_service.audit_page(page=2, page_size=2)
    assert p1["total"] == 5
    assert [r["target_id"] for r in p1["items"]] == ["u4", "u3"]
    assert [r["target_id"] for r in p2["items"]] == ["u2", "u1"]


def test_audit_page_filters_by_actor_and_event_type() -> None:
    from services.admin import metrics_service

    base = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    _seed_audit("user.role_granted", "a-1", "user", "u1", base)
    _seed_audit("user.role_revoked", "a-1", "user", "u2", base + timedelta(seconds=1))
    _seed_audit("user.role_granted", "a-2", "user", "u3", base + timedelta(seconds=2))

    by_actor = metrics_service.audit_page(actor_uid="a-1")
    by_event = metrics_service.audit_page(event_type="user.role_granted")
    assert {r["target_id"] for r in by_actor["items"]} == {"u1", "u2"}
    assert {r["target_id"] for r in by_event["items"]} == {"u1", "u3"}


def test_audit_event_types_returns_distinct_sorted() -> None:
    from services.admin import metrics_service

    now = datetime.now(timezone.utc)
    _seed_audit("z.last", "a", "x", "1", now)
    _seed_audit("a.first", "a", "x", "2", now)
    _seed_audit("a.first", "a", "x", "3", now)  # duplicate

    types = metrics_service.audit_event_types()
    assert types == ["a.first", "z.last"]
