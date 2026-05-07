"""Integration tests for ``/api/v1/admin/plans`` (US-M11.3)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from api.auth import get_current_user
from api.errors import ERR
from api.main import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping admin/plans integration tests",
)


@pytest.fixture(autouse=True)
def _clean():
    """Wipe non-seed plans + the test users this module touches."""
    from services.db import get_sync_session
    from services.db.models import AuditLog, Plan, User

    test_plan_ids = {"custom_x", "custom_y", "custom_z"}
    test_user_ids = {"u-admin", "u-on-plan"}

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AuditLog))
            s.execute(delete(User).where(User.id.in_(test_user_ids)))
            s.execute(delete(Plan).where(Plan.id.in_(test_plan_ids)))

    _wipe()
    yield
    _wipe()


def _client() -> TestClient:
    app = create_app()

    async def _fake_user() -> dict:
        return {"id": "u-admin", "role": "platform_admin", "plan": "free"}

    app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


# ─── GET /plans ─────────────────────────────────────────────────────


def test_list_returns_seeded_plans() -> None:
    with _client() as c:
        r = c.get("/api/v1/admin/plans")
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()}
    assert {"free", "personal_pro", "team_member", "org_member"}.issubset(ids)


# ─── POST /plans ────────────────────────────────────────────────────


def test_create_plan_succeeds_then_lists() -> None:
    with _client() as c:
        r = c.post(
            "/api/v1/admin/plans",
            json={
                "id": "custom_x",
                "name": "Custom X",
                "daily_ai_quota": 50,
                "monthly_ai_quota": 1000,
                "max_team_seats": 5,
                "features": ["foo"],
            },
        )
    assert r.status_code == 201
    assert r.json()["audit_log_id"] is not None

    with _client() as c:
        r2 = c.get("/api/v1/admin/plans")
    found = next((p for p in r2.json() if p["id"] == "custom_x"), None)
    assert found is not None
    assert found["daily_ai_quota"] == 50
    assert found["features"] == ["foo"]


def test_create_plan_rejects_duplicate_id() -> None:
    with _client() as c:
        r = c.post(
            "/api/v1/admin/plans",
            json={
                "id": "free",  # already seeded
                "name": "x", "daily_ai_quota": 0, "monthly_ai_quota": 0,
            },
        )
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == ERR.admin_target_not_found.code
    assert body["error"]["params"]["reason"] == "duplicate_id"


# ─── PATCH /plans/{id} ──────────────────────────────────────────────


def test_patch_updates_quota_and_writes_audit() -> None:
    from services.repositories import get_audit_log_repo

    with _client() as c:
        c.post(
            "/api/v1/admin/plans",
            json={
                "id": "custom_x", "name": "X",
                "daily_ai_quota": 10, "monthly_ai_quota": 100,
            },
        )
        r = c.patch(
            "/api/v1/admin/plans/custom_x",
            json={"daily_ai_quota": 99},
        )
    assert r.status_code == 200

    with _client() as c:
        r2 = c.get("/api/v1/admin/plans")
    found = next(p for p in r2.json() if p["id"] == "custom_x")
    assert found["daily_ai_quota"] == 99

    rows = get_audit_log_repo().list_by_target("plan", "custom_x")
    types = {r.event_type for r in rows}
    assert "admin.plan_updated" in types
    assert "admin.plan_created" in types


def test_patch_404s_on_unknown_plan() -> None:
    with _client() as c:
        r = c.patch("/api/v1/admin/plans/nope", json={"daily_ai_quota": 1})
    assert r.status_code == 404


# ─── DELETE /plans/{id} ─────────────────────────────────────────────


def test_delete_plan_with_no_users_succeeds() -> None:
    with _client() as c:
        c.post(
            "/api/v1/admin/plans",
            json={
                "id": "custom_z", "name": "Z",
                "daily_ai_quota": 0, "monthly_ai_quota": 0,
            },
        )
        r = c.delete("/api/v1/admin/plans/custom_z")
    assert r.status_code == 200
    assert r.json()["audit_log_id"] is not None

    with _client() as c:
        r2 = c.get("/api/v1/admin/plans")
    assert "custom_z" not in {p["id"] for p in r2.json()}


def test_delete_plan_blocked_when_users_assigned() -> None:
    """custom_y has a user on it; the plan can't be dropped."""
    from services.db import get_sync_session
    from services.db.models import User

    with _client() as c:
        c.post(
            "/api/v1/admin/plans",
            json={
                "id": "custom_y", "name": "Y",
                "daily_ai_quota": 0, "monthly_ai_quota": 0,
            },
        )

    with get_sync_session() as s, s.begin():
        s.add(User(id="u-on-plan", name="N", plan="custom_y"))

    with _client() as c:
        r = c.delete("/api/v1/admin/plans/custom_y")
    assert r.status_code == 404
    assert r.json()["error"]["params"]["reason"] == "users_still_assigned"


def test_delete_404s_on_unknown_plan() -> None:
    with _client() as c:
        r = c.delete("/api/v1/admin/plans/nope")
    assert r.status_code == 404
