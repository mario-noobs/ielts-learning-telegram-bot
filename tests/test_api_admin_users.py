"""Integration tests for ``/api/v1/admin/users`` (US-M11.3)."""

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
    reason="DATABASE_URL not set; skipping admin/users integration tests",
)


@pytest.fixture(autouse=True)
def _clean_users():
    from services.db import get_sync_session
    from services.db.models import AuditLog, User

    test_ids = {
        "u-admin", "u-target", "u-pro", "u-free-1", "u-free-2",
        "u-team", "u-org",
    }

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AuditLog))
            s.execute(delete(User).where(User.id.in_(test_ids)))

    _wipe()
    yield
    _wipe()


def _seed(uid: str, **fields) -> None:
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.add(User(id=uid, name=fields.pop("name", uid), **fields))


def _client(actor_role: str = "platform_admin") -> TestClient:
    app = create_app()

    async def _fake_user() -> dict:
        return {"id": "u-admin", "role": actor_role, "plan": "free"}

    app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


# ─── auth gate ──────────────────────────────────────────────────────


def test_non_admin_gets_403() -> None:
    with _client(actor_role="user") as c:
        r = c.get("/api/v1/admin/users")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == ERR.admin_forbidden_role.code


# ─── list ───────────────────────────────────────────────────────────


def test_list_returns_paginated_results() -> None:
    _seed("u-pro", role="user", plan="personal_pro")
    _seed("u-free-1", role="user", plan="free")
    _seed("u-free-2", role="user", plan="free")

    with _client() as c:
        r = c.get("/api/v1/admin/users")
    assert r.status_code == 200
    body = r.json()
    ids = {item["id"] for item in body["items"]}
    assert {"u-pro", "u-free-1", "u-free-2"}.issubset(ids)
    assert body["page"] == 1
    assert body["page_size"] == 50


def test_list_filters_by_plan() -> None:
    _seed("u-pro", plan="personal_pro")
    _seed("u-free-1", plan="free")

    with _client() as c:
        r = c.get("/api/v1/admin/users?plan=personal_pro")
    assert r.status_code == 200
    ids = {item["id"] for item in r.json()["items"]}
    assert "u-pro" in ids
    assert "u-free-1" not in ids


def test_list_filters_by_q() -> None:
    _seed("u-pro", name="Alice")
    _seed("u-free-1", name="Bob")

    with _client() as c:
        r = c.get("/api/v1/admin/users?q=ali")
    assert r.status_code == 200
    ids = {item["id"] for item in r.json()["items"]}
    assert "u-pro" in ids
    assert "u-free-1" not in ids


# ─── detail ─────────────────────────────────────────────────────────


def test_detail_returns_user() -> None:
    _seed("u-target", role="team_admin", plan="team_member")
    with _client() as c:
        r = c.get("/api/v1/admin/users/u-target")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "u-target"
    assert body["role"] == "team_admin"
    assert body["plan"] == "team_member"


def test_detail_404s_on_missing_user() -> None:
    with _client() as c:
        r = c.get("/api/v1/admin/users/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == ERR.admin_target_not_found.code


# ─── PATCH ──────────────────────────────────────────────────────────


def test_patch_updates_role_and_writes_audit_log() -> None:
    from services.repositories import get_audit_log_repo

    _seed("u-target", role="user", plan="free")
    with _client() as c:
        r = c.patch(
            "/api/v1/admin/users/u-target",
            json={"role": "team_admin"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["audit_log_id"], int)

    # DB reflects the change
    with _client() as c:
        r2 = c.get("/api/v1/admin/users/u-target")
    assert r2.json()["role"] == "team_admin"

    # Audit row written
    rows = get_audit_log_repo().list_by_target("user", "u-target")
    assert any(r.event_type == "admin.user_updated" for r in rows)
    audit = next(r for r in rows if r.event_type == "admin.user_updated")
    assert audit.before == {"role": "user"}
    assert audit.after == {"role": "team_admin"}


def test_patch_can_set_plan_and_expiry() -> None:
    _seed("u-target", role="user", plan="free")
    with _client() as c:
        r = c.patch(
            "/api/v1/admin/users/u-target",
            json={"plan": "personal_pro", "plan_expires_at": "2027-01-01"},
        )
    assert r.status_code == 200

    with _client() as c:
        r2 = c.get("/api/v1/admin/users/u-target")
    body = r2.json()
    assert body["plan"] == "personal_pro"
    assert body["plan_expires_at"] == "2027-01-01"


def test_patch_with_empty_body_is_noop() -> None:
    _seed("u-target", role="user", plan="free")
    with _client() as c:
        r = c.patch("/api/v1/admin/users/u-target", json={})
    assert r.status_code == 200
    assert r.json()["audit_log_id"] is None


def test_patch_404s_on_missing_user() -> None:
    with _client() as c:
        r = c.patch("/api/v1/admin/users/nope", json={"role": "team_admin"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == ERR.admin_target_not_found.code
