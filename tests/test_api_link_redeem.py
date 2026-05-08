"""US-M12.2 ``POST /api/v1/link/redeem`` coverage (AC2-AC6, AC10)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping link redeem tests",
)


@pytest.fixture(autouse=True)
def _truncate():
    from services.db import get_sync_session
    from services.db.models import AuditLog, LinkToken, User
    with get_sync_session() as s, s.begin():
        s.execute(delete(AuditLog))
        s.execute(delete(LinkToken))
        s.execute(delete(User))
    yield
    with get_sync_session() as s, s.begin():
        s.execute(delete(AuditLog))
        s.execute(delete(LinkToken))
        s.execute(delete(User))


@pytest.fixture(autouse=True)
def _stub_firestore():
    """Block Firestore client init across the whole test for safety."""
    class _StubFirestoreRepo:
        """No-op stand-in so merge_web_into_telegram doesn't touch
        Firestore in the redeem-test fixtures (we don't seed any
        subcollection docs here)."""
        def copy_subcollections(self, source_id, target_id):
            return {
                "vocab_merged": 0, "vocab_dropped": 0,
                "quiz_merged": 0, "writing_merged": 0,
                "daily_merged": 0, "daily_skipped": 0,
            }

    with patch(
        "services.firebase_service._get_db", return_value=object(),
    ), patch(
        "api.routes.auth.firebase_service._get_db", return_value=object(),
    ), patch(
        "services.firebase_service._firestore_user_repo_instance",
        return_value=_StubFirestoreRepo(),
    ), patch(
        "services.firebase_service._delete_source_subcollections",
    ):
        yield


@pytest.fixture()
def client():
    from api.main import create_app
    return TestClient(create_app())


def _seed_user(uid: str, **kwargs):
    from services.db import get_sync_session
    from services.db.models import User
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.add(User(
            id=str(uid),
            name=kwargs.get("name", "U"),
            username="",
            email=kwargs.get("email", ""),
            auth_uid=kwargs.get("auth_uid"),
            target_band=7.0,
            topics=["edu"],
            streak=0,
            total_words=kwargs.get("total_words", 0),
            total_quizzes=0,
            total_correct=0,
            challenge_wins=0,
            role="user",
            plan="free",
            created_at=now,
        ))


def _mint_token(direction: str, **kw):
    from services.repositories.postgres import PostgresLinkTokenRepo
    return PostgresLinkTokenRepo().create(direction=direction, **kw)


def _redeem(client, token: str, auth_uid: str, **claims):
    payload = {"uid": auth_uid, **claims}
    with patch(
        "api.routes.auth.firebase_admin.auth.verify_id_token",
        return_value=payload,
    ):
        return client.post(
            "/api/v1/link/redeem",
            json={"token": token},
            headers={"Authorization": "Bearer t"},
        )


# ── AC2: sub-case A (new web account, fresh auth_uid) ────────────────

def test_redeem_new_web_account_links_telegram_row(client):
    """Sub-case A — `auth_uid` doesn't resolve to any existing row.
    The route stamps `auth_uid` onto the Telegram row directly; no
    `web_xxx` is created."""
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed_user("4242", auth_uid=None, name="Telly")

    minted = _mint_token("tg_to_web", telegram_id=4242)

    res = _redeem(client, minted.token, auth_uid, email="g@e.test", name="Google Name")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "linked"
    assert body["counts"] is None
    assert body["profile"]["id"] == "4242"

    from services.db import get_sync_session
    from services.db.models import User
    with get_sync_session() as s:
        row = s.get(User, "4242")
    assert row.auth_uid == auth_uid
    # Email/name fill-in only happens when the TG row was missing them.
    assert row.email == "g@e.test"
    assert row.name == "Telly"  # name was already non-empty


# ── AC3: sub-case B (existing web_xxx → merge) ───────────────────────

def test_redeem_existing_web_xxx_triggers_merge(client):
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    web_id = f"web_{uuid.uuid4().hex[:12]}"
    _seed_user(web_id, auth_uid=auth_uid, total_words=12)
    _seed_user("9090", auth_uid=None, total_words=8)

    minted = _mint_token("tg_to_web", telegram_id=9090)
    res = _redeem(client, minted.token, auth_uid)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "merged"
    assert body["counts"] is not None  # merge_web_into_telegram returns counts
    assert body["profile"]["id"] == "9090"

    from services.db import get_sync_session
    from services.db.models import AuditLog, User
    with get_sync_session() as s:
        rows = [r.id for r in s.execute(select(User)).scalars().all()]
        merged_audits = s.execute(
            select(AuditLog).where(AuditLog.event_type == "user.merged"),
        ).scalars().all()
    assert rows == ["9090"]  # web_xxx absorbed
    assert len(merged_audits) == 1


# ── AC4: sub-case C (already linked) ──────────────────────────────────

def test_redeem_already_linked_is_idempotent(client):
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed_user("3030", auth_uid=auth_uid)

    minted = _mint_token("tg_to_web", telegram_id=3030)
    res = _redeem(client, minted.token, auth_uid)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "already_linked"
    assert body["counts"] is None


# ── AC5: token expiration ─────────────────────────────────────────────

def test_redeem_expired_token_returns_410(client):
    from services.db import get_sync_session
    from services.db.models import LinkToken

    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed_user("5555", auth_uid=None)
    minted = _mint_token("tg_to_web", telegram_id=5555, ttl_seconds=60)
    with get_sync_session() as s, s.begin():
        s.get(LinkToken, minted.token).expires_at = (
            datetime.now(timezone.utc) - timedelta(seconds=10)
        )

    res = _redeem(client, minted.token, auth_uid)
    assert res.status_code == 410
    assert res.json()["error"]["code"] == "auth.link.token_expired"


# ── AC6: token single-use ─────────────────────────────────────────────

def test_redeem_already_used_token_returns_410(client):
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed_user("6060", auth_uid=None)
    minted = _mint_token("tg_to_web", telegram_id=6060)

    first = _redeem(client, minted.token, auth_uid)
    assert first.status_code == 200, first.text

    second = _redeem(client, minted.token, auth_uid)
    assert second.status_code == 410
    assert second.json()["error"]["code"] == "auth.link.token_already_used"


# ── AC10 (sliver): legacy /api/v1/users/link still works + has Sunset header ──

def test_legacy_users_link_carries_sunset_header(client):
    """The 6-digit code path stays online for a 30-day deprecation window."""
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed_user("7777", auth_uid=None)
    record = {
        "telegram_id": 7777,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=300),
    }
    with patch(
        "api.routes.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid},
    ), patch(
        "api.routes.auth.firebase_service.get_link_code",
        return_value=record,
    ), patch(
        "api.routes.auth.firebase_service.delete_link_code",
    ):
        res = client.post(
            "/api/v1/users/link",
            json={"code": "123456"},
            headers={"Authorization": "Bearer t"},
        )
    assert res.status_code == 200
    assert "sunset" in {k.lower() for k in res.headers}
    assert res.headers.get("deprecation") == "true"
