"""Integration tests for ``/api/v1/admin/audit`` + metrics routes (US-M11.5)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from api.auth import get_current_user
from api.main import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping admin/audit integration tests",
)


@pytest.fixture(autouse=True)
def _clean():
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


def _client(role: str = "platform_admin") -> TestClient:
    app = create_app()

    async def _fake_user() -> dict:
        return {"id": "u-admin", "role": role, "plan": "free"}

    app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


def _seed_audit(event_type: str, actor_uid: str = "admin-1",
                target_kind: str = "user", target_id: str = "u1",
                when: datetime | None = None) -> None:
    from services.db import get_sync_session
    from services.db.models import AuditLog

    with get_sync_session() as s, s.begin():
        s.add(AuditLog(
            event_type=event_type, actor_uid=actor_uid,
            target_kind=target_kind, target_id=target_id,
            before=None, after=None, request_id=None,
            created_at=when or datetime.now(timezone.utc),
        ))


# ─── auth gate ──────────────────────────────────────────────────────


def test_non_admin_cant_access_audit() -> None:
    with _client(role="user") as c:
        r = c.get("/api/v1/admin/audit")
    assert r.status_code == 403


def test_team_admin_cant_access_metrics() -> None:
    with _client(role="team_admin") as c:
        r = c.get("/api/v1/admin/metrics/dau")
    assert r.status_code == 403


# ─── audit list ────────────────────────────────────────────────────


def test_audit_list_paginates() -> None:
    base = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    for i in range(7):
        _seed_audit("user.role_granted", target_id=f"u{i}",
                    when=base + timedelta(seconds=i))

    with _client() as c:
        r = c.get("/api/v1/admin/audit?page=1&page_size=3")
        body = r.json()
    assert r.status_code == 200
    assert body["total"] == 7
    assert body["page"] == 1
    assert body["page_size"] == 3
    assert [row["target_id"] for row in body["items"]] == ["u6", "u5", "u4"]


def test_audit_list_filters_by_actor() -> None:
    now = datetime.now(timezone.utc)
    _seed_audit("user.role_granted", actor_uid="a-1", target_id="u1", when=now)
    _seed_audit("user.role_granted", actor_uid="a-2", target_id="u2", when=now)

    with _client() as c:
        r = c.get("/api/v1/admin/audit?actor_uid=a-1")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["target_id"] == "u1"


def test_audit_event_types_distinct() -> None:
    now = datetime.now(timezone.utc)
    _seed_audit("a.x", when=now)
    _seed_audit("a.x", when=now)
    _seed_audit("b.y", when=now)

    with _client() as c:
        r = c.get("/api/v1/admin/audit/event-types")
    assert r.status_code == 200
    assert r.json() == ["a.x", "b.y"]


# ─── metrics routes ────────────────────────────────────────────────


def test_metrics_dau_returns_padded_series() -> None:
    from services.repositories import get_metrics_repo

    today = datetime.now(timezone.utc).date()
    get_metrics_repo().upsert_daily(today, 5, 3, 1, 0, {"free": 5})

    with _client() as c:
        r = c.get("/api/v1/admin/metrics/dau?days=3")
        rows = r.json()
    assert r.status_code == 200
    assert len(rows) == 3
    assert rows[-1]["dau"] == 3


def test_metrics_plans_serializes_distribution() -> None:
    fake_users = [
        {"id": "u1", "plan": "free"},
        {"id": "u2", "plan": "personal_pro"},
        {"id": "u3", "plan": "free"},
    ]
    with patch("services.admin.metrics_service.firebase_service.get_all_users",
               return_value=fake_users), _client() as c:
        r = c.get("/api/v1/admin/metrics/plans")
    assert r.status_code == 200
    rows = {row["plan_id"]: row["count"] for row in r.json()}
    assert rows == {"free": 2, "personal_pro": 1}


def test_metrics_ai_usage_groups_by_date_feature() -> None:
    from services.db import get_sync_session
    from services.db.models import AiUsage

    today = datetime.now(timezone.utc).date()
    with get_sync_session() as s, s.begin():
        s.add(AiUsage(user_uid="u1", date=today, feature="vocab", count=2,
                      last_call_at=datetime.now(timezone.utc)))
        s.add(AiUsage(user_uid="u2", date=today, feature="vocab", count=1,
                      last_call_at=datetime.now(timezone.utc)))

    with _client() as c:
        r = c.get("/api/v1/admin/metrics/ai-usage?days=7")
    assert r.status_code == 200
    items = [(row["date"], row["feature"], row["count"]) for row in r.json()]
    assert (today.isoformat(), "vocab", 3) in items
