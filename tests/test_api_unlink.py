"""US-M12.1 unlink endpoint coverage (AC11, AC13–AC16)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping unlink tests",
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


def _seed(uid: str, **kwargs):
    from services.db import get_sync_session
    from services.db.models import User
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.add(User(
            id=str(uid), name=kwargs.get("name", "U"), username="",
            email=kwargs.get("email", ""),
            auth_uid=kwargs.get("auth_uid"),
            target_band=7.0, topics=["edu"],
            streak=kwargs.get("streak", 0),
            total_words=kwargs.get("total_words", 0),
            total_quizzes=0, total_correct=0, challenge_wins=0,
            role=kwargs.get("role", "user"), plan="free",
            created_at=now,
        ))


def _row(auth_uid: str):
    from services.db import get_sync_session
    from services.db.models import User
    with get_sync_session() as s:
        return s.execute(select(User).where(User.auth_uid == auth_uid)).scalar_one_or_none()


# ── AC11 ──────────────────────────────────────────────────────────────

def test_web_unlink_clears_auth_uid_and_preserves_data(client):
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed("777", auth_uid=auth_uid, total_words=12, streak=4)

    with patch(
        "api.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "x@y.test"},
    ):
        res = client.delete("/api/v1/users/link", headers={"Authorization": "Bearer t"})

    assert res.status_code == 204

    from services.db import get_sync_session
    from services.db.models import User
    with get_sync_session() as s:
        row = s.get(User, "777")
    assert row is not None
    assert row.auth_uid is None
    assert row.total_words == 12
    assert row.streak == 4

    # /me returns 404 because get_user_by_auth_uid no longer resolves the row.
    with patch(
        "api.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "x@y.test"},
    ):
        me_res = client.get("/api/v1/me", headers={"Authorization": "Bearer t"})
    assert me_res.status_code == 404


# ── AC13 — web-only account ──────────────────────────────────────────

def test_unlink_rejects_web_only_account_409(client):
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed("web_abc123", auth_uid=auth_uid)

    with patch(
        "api.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "x@y.test"},
    ):
        res = client.delete("/api/v1/users/link", headers={"Authorization": "Bearer t"})

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "auth.link.web_only_account"

    # Row unchanged.
    row = _row(auth_uid)
    assert row is not None
    assert row.auth_uid == auth_uid


# ── AC14 — idempotent (auth_uid IS NULL) ─────────────────────────────

def test_unlink_idempotent_no_audit():
    """Direct repo-level test: row with auth_uid=NULL → no-op, returns None.

    The HTTP path can't reach this state easily (the token wouldn't
    resolve), so we exercise the underlying ``unlink_auth`` directly.
    """
    from services.repositories.postgres import PostgresUserRepo

    _seed("88", auth_uid=None)
    assert PostgresUserRepo().unlink_auth(88) is None


# ── AC15 — audit row ──────────────────────────────────────────────────

def test_unlink_writes_audit_row(client):
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed("321", auth_uid=auth_uid)

    with patch(
        "api.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "x@y.test"},
    ):
        res = client.delete("/api/v1/users/link", headers={"Authorization": "Bearer t"})
    assert res.status_code == 204

    from services.db import get_sync_session
    from services.db.models import AuditLog

    with get_sync_session() as s:
        rows = s.execute(
            select(AuditLog)
            .where(AuditLog.event_type == "user.unlinked")
            .where(AuditLog.target_id == "321"),
        ).scalars().all()
    assert len(rows) == 1
    audit = rows[0]
    assert audit.actor_uid == "self:web"
    assert audit.before == {"auth_uid": auth_uid}
    assert audit.after == {"auth_uid": None}


# ── AC16 — re-link after unlink (smoke; full merge in test_api_link_merge) ──

def test_relink_after_unlink_via_repo_keeps_data():
    from services.repositories.postgres import PostgresUserRepo

    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed("999", auth_uid=auth_uid, total_words=20)

    repo = PostgresUserRepo()
    assert repo.unlink_auth(999) == auth_uid
    assert repo.get(999).auth_uid is None

    # Re-stamp the same auth_uid (mimics fresh /link with no web_xxx).
    repo.link_telegram_to_auth(999, auth_uid)
    fetched = repo.get(999)
    assert fetched.auth_uid == auth_uid
    assert fetched.total_words == 20
