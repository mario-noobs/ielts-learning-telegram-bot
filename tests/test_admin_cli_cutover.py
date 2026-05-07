"""US-M8.6 AC5 — ``scripts/admin.py grant-admin`` works end-to-end on
a fresh web signup with no Firestore edit.

Skipped unless DATABASE_URL is set.
"""

from __future__ import annotations

import argparse
import os
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping admin CLI cutover tests",
)


@pytest.fixture(autouse=True)
def _truncate_users():
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.execute(delete(User))
    yield
    with get_sync_session() as s, s.begin():
        s.execute(delete(User))


@pytest.fixture(autouse=True)
def _stub_firestore():
    with patch("api.routes.auth.firebase_service._get_db", return_value=object()):
        yield


@pytest.fixture()
def client():
    from api.main import create_app
    return TestClient(create_app())


def test_grant_admin_after_signup_then_me_returns_platform_admin(client) -> None:
    """End-to-end: signup → grant-admin via CLI → /me returns
    role=platform_admin. No Firestore edit anywhere in the flow."""
    from scripts import admin as admin_cli
    from services.db import get_sync_session
    from services.db.models import User

    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"

    # 1. Signup via the API (Postgres write path).
    with patch(
        "api.routes.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "admin@example.com"},
    ):
        signup = client.post(
            "/api/v1/users",
            json={"name": "Admin Candidate", "target_band": 7.0,
                  "topics": ["education"]},
            headers={"Authorization": "Bearer t"},
        )
    assert signup.status_code == 201
    assert signup.json()["role"] == "user"

    # 2. Run the CLI grant-admin against the auth_uid.
    args = argparse.Namespace(uid=auth_uid)
    with patch.object(admin_cli, "audit_service"):
        rc = admin_cli._cmd_grant_admin(args)
    assert rc == 0

    # 3. Postgres reflects role=platform_admin.
    with get_sync_session() as s:
        row = s.execute(select(User).where(User.auth_uid == auth_uid)).scalar_one()
    assert row.role == "platform_admin"

    # 4. /api/v1/me echoes the new role for the same token.
    with patch(
        "api.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "admin@example.com"},
    ):
        me = client.get("/api/v1/me", headers={"Authorization": "Bearer t"})
    assert me.status_code == 200
    assert me.json()["role"] == "platform_admin"
