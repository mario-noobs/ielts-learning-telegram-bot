"""Integration tests for self-serve team workspace routes (US-#332-#335)."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update

from api.auth import get_current_user
from api.errors import ERR
from api.main import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping team workspace integration tests",
)


@pytest.fixture(autouse=True)
def _clean():
    from services.db import get_sync_session
    from services.db.models import AuditLog, Team, TeamInvite, TeamMember, User

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(update(User).values(team_id=None))
            s.execute(delete(AuditLog))
            s.execute(delete(TeamInvite))
            s.execute(delete(TeamMember))
            s.execute(delete(Team))
            s.execute(delete(User).where(User.id.like("team-test-%")))

    _wipe()
    yield
    _wipe()


def _seed_user(user_id: str, **fields) -> None:
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.add(User(id=user_id, name=fields.pop("name", user_id), **fields))


def _client(user_id: str, team_id: str | None = None) -> TestClient:
    app = create_app()

    async def _fake_user() -> dict:
        return {
            "id": user_id,
            "name": user_id,
            "role": "user",
            "plan": "free",
            "team_id": team_id,
        }

    app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


def _create_team(owner_id: str = "team-test-owner") -> str:
    _seed_user(owner_id)
    with _client(owner_id) as c:
        r = c.post("/api/v1/teams", json={"name": "Study Squad"})
    assert r.status_code == 201
    return r.json()["team"]["id"]


def _create_invite(team_id: str, owner_id: str = "team-test-owner") -> str:
    with _client(owner_id) as c:
        r = c.post(f"/api/v1/teams/{team_id}/invites", json={"role": "member"})
    assert r.status_code == 201
    return r.json()["token"]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_create_team_links_creator_and_member_row() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamMember, User

    _seed_user("team-test-owner")
    with _client("team-test-owner") as c:
        r = c.post("/api/v1/teams", json={"name": "Study Squad"})

    assert r.status_code == 201
    body = r.json()["team"]
    assert body["name"] == "Study Squad"
    assert body["seat_limit"] == 5
    assert body["member_count"] == 1
    assert body["my_role"] == "owner"

    with get_sync_session() as s:
        user = s.get(User, "team-test-owner")
        member = s.get(
            TeamMember,
            {"team_id": body["id"], "user_uid": "team-test-owner"},
        )
    assert user.team_id == body["id"]
    assert member.role == "admin"


def test_create_team_blocks_existing_team_member() -> None:
    _create_team("team-test-owner")
    with _client("team-test-owner") as c:
        r = c.post("/api/v1/teams", json={"name": "Another"})

    assert r.status_code == 409
    assert r.json()["error"]["code"] == ERR.team_already_joined.code


def test_create_invite_returns_shareable_path() -> None:
    team_id = _create_team()
    with _client("team-test-owner") as c:
        r = c.post(f"/api/v1/teams/{team_id}/invites", json={"role": "member"})

    assert r.status_code == 201
    body = r.json()
    assert body["token"]
    assert body["invite_url"] == f"/team/invite/{body['token']}"
    assert body["expires_at"]


def test_non_admin_cannot_create_invite() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamMember, User

    team_id = _create_team()
    _seed_user("team-test-member")
    with get_sync_session() as s, s.begin():
        s.add(
            TeamMember(
                team_id=team_id,
                user_uid="team-test-member",
                role="member",
                joined_at=datetime.now(timezone.utc),
            )
        )
        s.execute(
            update(User).where(User.id == "team-test-member").values(team_id=team_id),
        )

    with _client("team-test-member", team_id=team_id) as c:
        r = c.post(f"/api/v1/teams/{team_id}/invites", json={"role": "member"})

    assert r.status_code == 403


def test_preview_invite_returns_public_team_summary() -> None:
    team_id = _create_team()
    token = _create_invite(team_id)

    with TestClient(create_app()) as c:
        r = c.get(f"/api/v1/teams/invites/{token}")

    assert r.status_code == 200
    assert r.json()["team_name"] == "Study Squad"
    assert r.json()["member_count"] == 1
    assert r.json()["seat_limit"] == 5


def test_accept_invite_links_user_to_team() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamMember, User

    team_id = _create_team()
    token = _create_invite(team_id)
    _seed_user("team-test-invited")

    with _client("team-test-invited") as c:
        r = c.post(f"/api/v1/teams/invites/{token}/accept")

    assert r.status_code == 200
    assert r.json()["team"]["id"] == team_id
    assert r.json()["team"]["my_role"] == "member"
    with get_sync_session() as s:
        user = s.get(User, "team-test-invited")
        member = s.get(
            TeamMember,
            {"team_id": team_id, "user_uid": "team-test-invited"},
        )
    assert user.team_id == team_id
    assert member.role == "member"


def test_accept_invite_blocks_full_team() -> None:
    from services.db import get_sync_session
    from services.db.models import Team

    team_id = _create_team()
    token = _create_invite(team_id)
    _seed_user("team-test-invited")
    with get_sync_session() as s, s.begin():
        team = s.get(Team, team_id)
        team.seat_limit = 1

    with _client("team-test-invited") as c:
        r = c.post(f"/api/v1/teams/invites/{token}/accept")

    assert r.status_code == 409
    assert r.json()["error"]["code"] == ERR.team_seat_limit_reached.code


def test_accept_invite_rejects_expired_token() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamInvite

    team_id = _create_team()
    token = "expired-token"
    with get_sync_session() as s, s.begin():
        s.add(
            TeamInvite(
                team_id=team_id,
                token_hash=_hash_token(token),
                role="member",
                created_by="team-test-owner",
                created_at=datetime.now(timezone.utc) - timedelta(days=10),
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
                metadata_json={},
            )
        )
    _seed_user("team-test-invited")

    with _client("team-test-invited") as c:
        r = c.post(f"/api/v1/teams/invites/{token}/accept")

    assert r.status_code == 410
    assert r.json()["error"]["code"] == ERR.team_invite_expired.code
