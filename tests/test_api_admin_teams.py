"""Integration tests for ``/api/v1/admin/teams`` (US-M11.4)."""

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
    reason="DATABASE_URL not set; skipping admin/teams integration tests",
)


@pytest.fixture(autouse=True)
def _clean():
    """Wipe AuditLog + admin tables touched by these tests."""
    from services.db import get_sync_session
    from services.db.models import AuditLog, Team, TeamMember

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AuditLog))
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


def _create_team(c: TestClient, **overrides) -> str:
    body = {
        "name": "Team A", "owner_uid": "u-owner",
        "plan_id": "team_member", "seat_limit": 3,
        **overrides,
    }
    r = c.post("/api/v1/admin/teams", json=body)
    assert r.status_code == 201
    return r.json()["extra"]["id"]


# ─── auth gate ──────────────────────────────────────────────────────


def test_non_admin_cant_list_teams() -> None:
    with _client(role="user") as c:
        r = c.get("/api/v1/admin/teams")
    assert r.status_code == 403


# ─── CRUD ───────────────────────────────────────────────────────────


def test_create_then_list_team() -> None:
    with _client() as c:
        team_id = _create_team(c)
        r = c.get("/api/v1/admin/teams")
    assert r.status_code == 200
    body = r.json()
    assert any(row["id"] == team_id and row["name"] == "Team A" for row in body)


def test_get_team_returns_member_count() -> None:
    with _client() as c:
        team_id = _create_team(c, seat_limit=5)
        c.post(f"/api/v1/admin/teams/{team_id}/members",
               json={"user_uid": "u1", "role": "member"})
        c.post(f"/api/v1/admin/teams/{team_id}/members",
               json={"user_uid": "u2", "role": "member"})
        r = c.get(f"/api/v1/admin/teams/{team_id}")
    assert r.status_code == 200
    assert r.json()["member_count"] == 2


def test_patch_team_name() -> None:
    with _client() as c:
        team_id = _create_team(c)
        r = c.patch(f"/api/v1/admin/teams/{team_id}",
                    json={"name": "Renamed"})
        assert r.status_code == 200
        r2 = c.get(f"/api/v1/admin/teams/{team_id}")
    assert r2.json()["name"] == "Renamed"


def test_delete_team_cascades_members() -> None:
    with _client() as c:
        team_id = _create_team(c)
        c.post(f"/api/v1/admin/teams/{team_id}/members",
               json={"user_uid": "u1"})
        r = c.delete(f"/api/v1/admin/teams/{team_id}")
        assert r.status_code == 200
        r2 = c.get(f"/api/v1/admin/teams/{team_id}")
    assert r2.status_code == 404


# ─── Members ────────────────────────────────────────────────────────


def test_add_member_writes_audit_log() -> None:
    from services.repositories import get_audit_log_repo

    with _client() as c:
        team_id = _create_team(c)
        r = c.post(f"/api/v1/admin/teams/{team_id}/members",
                   json={"user_uid": "u1", "role": "member"})
    assert r.status_code == 201
    rows = get_audit_log_repo().list_by_target("team", team_id)
    assert any(r.event_type == "admin.team_member_added" for r in rows)


def test_seat_limit_blocks_extra_member() -> None:
    with _client() as c:
        team_id = _create_team(c, seat_limit=2)
        assert c.post(f"/api/v1/admin/teams/{team_id}/members",
                      json={"user_uid": "u1"}).status_code == 201
        assert c.post(f"/api/v1/admin/teams/{team_id}/members",
                      json={"user_uid": "u2"}).status_code == 201
        r = c.post(f"/api/v1/admin/teams/{team_id}/members",
                   json={"user_uid": "u3"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == ERR.team_seat_limit_reached.code
    assert r.json()["error"]["params"]["seat_limit"] == 2


def test_duplicate_member_returns_409() -> None:
    with _client() as c:
        team_id = _create_team(c)
        c.post(f"/api/v1/admin/teams/{team_id}/members",
               json={"user_uid": "u1"})
        r = c.post(f"/api/v1/admin/teams/{team_id}/members",
                   json={"user_uid": "u1"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == ERR.team_member_already_exists.code


def test_remove_member_404s_if_not_present() -> None:
    with _client() as c:
        team_id = _create_team(c)
        r = c.delete(f"/api/v1/admin/teams/{team_id}/members/ghost")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == ERR.team_not_member.code


def test_list_members_returns_added_users() -> None:
    with _client() as c:
        team_id = _create_team(c)
        c.post(f"/api/v1/admin/teams/{team_id}/members",
               json={"user_uid": "u-alpha"})
        c.post(f"/api/v1/admin/teams/{team_id}/members",
               json={"user_uid": "u-beta", "role": "admin"})
        r = c.get(f"/api/v1/admin/teams/{team_id}/members")
    assert r.status_code == 200
    members = r.json()
    assert {m["user_uid"] for m in members} == {"u-alpha", "u-beta"}
    assert next(m for m in members if m["user_uid"] == "u-beta")["role"] == "admin"


# ─── team_admin scope ───────────────────────────────────────────────


def test_team_admin_can_manage_own_team() -> None:
    """A user who's already team_admin of T can patch T."""
    with _client() as c:
        team_id = _create_team(c)
        # Add the actor as a team admin of this team.
        c.post(f"/api/v1/admin/teams/{team_id}/members",
               json={"user_uid": "u-self", "role": "admin"})

    # Re-create the client as a 'team_admin' role acting on themselves.
    with _client(role="team_admin", actor_id="u-self") as c:
        r = c.patch(f"/api/v1/admin/teams/{team_id}",
                    json={"name": "Renamed by team_admin"})
    assert r.status_code == 200


def test_team_admin_cant_manage_other_teams() -> None:
    """team_admin without membership in the target team gets 403."""
    with _client() as c:
        team_id = _create_team(c)

    with _client(role="team_admin", actor_id="u-self") as c:
        r = c.patch(f"/api/v1/admin/teams/{team_id}",
                    json={"name": "Should not work"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == ERR.admin_forbidden_role.code
