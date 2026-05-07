"""Integration tests for ``/api/v1/admin/orgs`` (US-M11.4)."""

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
    reason="DATABASE_URL not set; skipping admin/orgs integration tests",
)


@pytest.fixture(autouse=True)
def _clean():
    """Wipe AuditLog + admin tables touched by these tests."""
    from services.db import get_sync_session
    from services.db.models import AuditLog, Org, OrgAdmin, OrgTeam, Team, TeamMember

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AuditLog))
            s.execute(delete(OrgTeam))
            s.execute(delete(OrgAdmin))
            s.execute(delete(Org))
            s.execute(delete(TeamMember))
            s.execute(delete(Team))

    _wipe()
    yield
    _wipe()


def _client(role: str = "platform_admin", actor_id: str = "u-admin") -> TestClient:
    app = create_app()

    async def _fake_user() -> dict:
        return {"id": actor_id, "role": role, "plan": "free"}

    app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


def _create_org(c: TestClient, **overrides) -> str:
    body = {
        "name": "Org A", "owner_uid": "u-owner", "plan_id": "org_member",
        **overrides,
    }
    r = c.post("/api/v1/admin/orgs", json=body)
    assert r.status_code == 201
    return r.json()["extra"]["id"]


def _create_team(c: TestClient, **overrides) -> str:
    body = {
        "name": "T", "owner_uid": "u-owner",
        "plan_id": "team_member", "seat_limit": 3,
        **overrides,
    }
    r = c.post("/api/v1/admin/teams", json=body)
    assert r.status_code == 201
    return r.json()["extra"]["id"]


# A syntactically valid UUID that no test ever creates; used for 404 cases
# (the column is uuid-typed, so plain "ghost" / "does-not-exist" would
# blow up at the cast layer instead of returning a clean 404).
_NO_SUCH_ID = "00000000-0000-0000-0000-000000000000"


# ─── auth gate ──────────────────────────────────────────────────────


def test_non_admin_cant_list_orgs() -> None:
    with _client(role="user") as c:
        r = c.get("/api/v1/admin/orgs")
    assert r.status_code == 403


def test_team_admin_cant_list_orgs() -> None:
    """Org routes are platform_admin only."""
    with _client(role="team_admin") as c:
        r = c.get("/api/v1/admin/orgs")
    assert r.status_code == 403


# ─── CRUD ───────────────────────────────────────────────────────────


def test_create_then_list_org() -> None:
    with _client() as c:
        org_id = _create_org(c)
        r = c.get("/api/v1/admin/orgs")
    assert r.status_code == 200
    assert any(row["id"] == org_id and row["name"] == "Org A" for row in r.json())


def test_get_org_returns_counts() -> None:
    with _client() as c:
        org_id = _create_org(c)
        team_id = _create_team(c)
        c.post(f"/api/v1/admin/orgs/{org_id}/admins",
               json={"user_uid": "u-1"})
        c.post(f"/api/v1/admin/orgs/{org_id}/admins",
               json={"user_uid": "u-2"})
        c.post(f"/api/v1/admin/orgs/{org_id}/teams",
               json={"team_id": team_id})
        r = c.get(f"/api/v1/admin/orgs/{org_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["admin_count"] == 2
    assert body["team_count"] == 1


def test_get_org_404_unknown() -> None:
    with _client() as c:
        r = c.get(f"/api/v1/admin/orgs/{_NO_SUCH_ID}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == ERR.admin_target_not_found.code


def test_patch_org_name() -> None:
    with _client() as c:
        org_id = _create_org(c)
        r = c.patch(f"/api/v1/admin/orgs/{org_id}",
                    json={"name": "Renamed"})
        assert r.status_code == 200
        r2 = c.get(f"/api/v1/admin/orgs/{org_id}")
    assert r2.json()["name"] == "Renamed"


def test_patch_org_404_unknown() -> None:
    with _client() as c:
        r = c.patch(f"/api/v1/admin/orgs/{_NO_SUCH_ID}", json={"name": "x"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == ERR.admin_target_not_found.code


def test_delete_org_then_get_returns_404() -> None:
    with _client() as c:
        org_id = _create_org(c)
        r = c.delete(f"/api/v1/admin/orgs/{org_id}")
        assert r.status_code == 200
        r2 = c.get(f"/api/v1/admin/orgs/{org_id}")
    assert r2.status_code == 404


# ─── Admins ─────────────────────────────────────────────────────────


def test_add_admin_writes_audit_log() -> None:
    from services.repositories import get_audit_log_repo

    with _client() as c:
        org_id = _create_org(c)
        r = c.post(f"/api/v1/admin/orgs/{org_id}/admins",
                   json={"user_uid": "u-alpha"})
    assert r.status_code == 201
    rows = get_audit_log_repo().list_by_target("org", org_id)
    assert any(row.event_type == "admin.org_admin_added" for row in rows)


def test_list_admins_returns_added_uids() -> None:
    with _client() as c:
        org_id = _create_org(c)
        c.post(f"/api/v1/admin/orgs/{org_id}/admins",
               json={"user_uid": "u-a"})
        c.post(f"/api/v1/admin/orgs/{org_id}/admins",
               json={"user_uid": "u-b"})
        r = c.get(f"/api/v1/admin/orgs/{org_id}/admins")
    assert r.status_code == 200
    assert set(r.json()) == {"u-a", "u-b"}


def test_remove_admin_drops_uid() -> None:
    with _client() as c:
        org_id = _create_org(c)
        c.post(f"/api/v1/admin/orgs/{org_id}/admins",
               json={"user_uid": "u-a"})
        c.post(f"/api/v1/admin/orgs/{org_id}/admins",
               json={"user_uid": "u-b"})
        r = c.delete(f"/api/v1/admin/orgs/{org_id}/admins/u-a")
        assert r.status_code == 200
        r2 = c.get(f"/api/v1/admin/orgs/{org_id}/admins")
    assert r2.json() == ["u-b"]


# ─── Team links ─────────────────────────────────────────────────────


def test_link_team_writes_audit_log() -> None:
    from services.repositories import get_audit_log_repo

    with _client() as c:
        org_id = _create_org(c)
        team_id = _create_team(c)
        r = c.post(f"/api/v1/admin/orgs/{org_id}/teams",
                   json={"team_id": team_id})
    assert r.status_code == 201
    rows = get_audit_log_repo().list_by_target("org", org_id)
    assert any(row.event_type == "admin.org_team_linked" for row in rows)


def test_list_org_teams_returns_linked_ids() -> None:
    with _client() as c:
        org_id = _create_org(c)
        t1 = _create_team(c, name="T1")
        t2 = _create_team(c, name="T2")
        c.post(f"/api/v1/admin/orgs/{org_id}/teams", json={"team_id": t1})
        c.post(f"/api/v1/admin/orgs/{org_id}/teams", json={"team_id": t2})
        r = c.get(f"/api/v1/admin/orgs/{org_id}/teams")
    assert r.status_code == 200
    assert set(r.json()) == {t1, t2}


def test_unlink_team_drops_id() -> None:
    with _client() as c:
        org_id = _create_org(c)
        t1 = _create_team(c, name="T1")
        t2 = _create_team(c, name="T2")
        c.post(f"/api/v1/admin/orgs/{org_id}/teams", json={"team_id": t1})
        c.post(f"/api/v1/admin/orgs/{org_id}/teams", json={"team_id": t2})
        r = c.delete(f"/api/v1/admin/orgs/{org_id}/teams/{t1}")
        assert r.status_code == 200
        r2 = c.get(f"/api/v1/admin/orgs/{org_id}/teams")
    assert r2.json() == [t2]
