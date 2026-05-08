"""US-M12.1 merge path coverage (AC1, AC5, AC6, AC8).

End-to-end via ``POST /api/v1/users/link`` with stubbed Firebase token,
stubbed Firestore (so the test focuses on Postgres-side state), and the
real ``merge_web_into_telegram`` orchestrator.

Subcollection-merge rules (AC2, AC3, AC4) are covered at the repo level
in ``tests/test_repositories/test_user_repo_merge.py`` against the
in-memory fake Firestore — exercising them through the API would require
emulator setup we don't have in CI today.
"""

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
    reason="DATABASE_URL not set; skipping merge tests",
)


@pytest.fixture(autouse=True)
def _truncate():
    from services.db import get_sync_session
    from services.db.models import AuditLog, User

    with get_sync_session() as s, s.begin():
        s.execute(delete(AuditLog))
        s.execute(delete(User))
    yield
    with get_sync_session() as s, s.begin():
        s.execute(delete(AuditLog))
        s.execute(delete(User))


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
            id=str(uid),
            name=kwargs.get("name", "U"),
            username=kwargs.get("username", ""),
            email=kwargs.get("email", ""),
            auth_uid=kwargs.get("auth_uid"),
            target_band=kwargs.get("target_band", 7.0),
            topics=kwargs.get("topics", ["edu"]),
            streak=kwargs.get("streak", 0),
            total_words=kwargs.get("total_words", 0),
            total_quizzes=kwargs.get("total_quizzes", 0),
            total_correct=kwargs.get("total_correct", 0),
            challenge_wins=0,
            role=kwargs.get("role", "user"),
            plan=kwargs.get("plan", "free"),
            created_at=kwargs.get("created_at", now),
        ))


def _stub_link_helpers(auth_uid: str, telegram_id: int):
    """Stub all the pieces ``link_telegram`` needs except merge_web_into_telegram.

    The merge runs for real against Postgres so we can assert the Postgres
    end state. Firestore subcollection ops are stubbed because we don't
    seed any subcollection docs in these tests.
    """
    now = datetime.now(timezone.utc)
    record = {
        "telegram_id": telegram_id,
        "created_at": now,
        "expires_at": now + timedelta(seconds=300),
    }
    return [
        patch(
            "api.routes.auth.firebase_admin.auth.verify_id_token",
            return_value={"uid": auth_uid, "email": "g@e.test", "name": "Google"},
        ),
        patch(
            "api.routes.auth.firebase_service._get_db",
            return_value=object(),
        ),
        patch(
            "api.routes.auth.firebase_service.get_link_code",
            return_value=record,
        ),
        patch("api.routes.auth.firebase_service.delete_link_code"),
        patch(
            "services.firebase_service._firestore_user_repo_instance",
            return_value=_NoopFirestoreRepo(),
        ),
        patch("services.firebase_service._delete_source_subcollections"),
    ]


class _NoopFirestoreRepo:
    """Stand-in for FirestoreUserRepo when subcollection state is irrelevant."""

    def copy_subcollections(self, source_id, target_id):
        return {
            "vocab_merged": 0, "vocab_dropped": 0,
            "quiz_merged": 0, "writing_merged": 0,
            "daily_merged": 0, "daily_skipped": 0,
        }


# ── AC1 + AC5: merge atomicity + plan/role escalation ───────────────

def test_merge_atomic_and_escalates_plan_role(client):
    """Web-first user with platform_admin + personal_pro merges into
    Telegram user with default role/plan → surviving row keeps the
    elevated values, web_xxx row deleted."""
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    web_id = f"web_{uuid.uuid4().hex[:12]}"
    telegram_id = 4242
    older = datetime.now(timezone.utc) - timedelta(days=30)

    _seed(
        web_id,
        auth_uid=auth_uid,
        email="w@e.test",
        total_words=12,
        total_quizzes=3,
        total_correct=2,
        role="platform_admin",
        plan="personal_pro",
        created_at=older,
    )
    _seed(
        str(telegram_id),
        auth_uid=None,
        username="tellt",
        total_words=8,
        total_quizzes=10,
        total_correct=7,
        role="user",
        plan="free",
        target_band=8.0,
    )

    stubs = _stub_link_helpers(auth_uid, telegram_id)
    for s in stubs:
        s.start()
    try:
        res = client.post(
            "/api/v1/users/link",
            json={"code": "123456"},
            headers={"Authorization": "Bearer t"},
        )
    finally:
        for s in reversed(stubs):
            s.stop()

    assert res.status_code == 200, res.text

    # AC1 — exactly one row, with telegram_id, with merged auth_uid.
    from services.db import get_sync_session
    from services.db.models import User
    with get_sync_session() as s:
        rows = s.execute(select(User)).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.id == str(telegram_id)
    assert row.auth_uid == auth_uid
    # AC5 — plan + role escalated.
    assert row.role == "platform_admin"
    assert row.plan == "personal_pro"
    # Counters summed (no vocab dropped → total_words = 20).
    assert row.total_words == 20
    assert row.total_quizzes == 13
    assert row.total_correct == 9
    # Target_band: TG was 8.0 (non-default) → kept.
    assert row.target_band == 8.0


# ── AC6: telegram-first regression (no merge enters) ────────────────

def test_no_merge_when_no_web_xxx_exists(client):
    """Telegram-first user with no `web_xxx` should hit the US-M8.6
    bare ``link_telegram_to_auth`` path, not ``merge_web_into_telegram``."""
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    telegram_id = 5151
    _seed(str(telegram_id), auth_uid=None, username="t", total_words=4)

    stubs = _stub_link_helpers(auth_uid, telegram_id)

    # Patch the merge entry point to fail loudly if invoked.
    def _no_merge(*_a, **_kw):
        raise AssertionError("merge_web_into_telegram must NOT be called when no web_xxx exists")

    stubs.append(
        patch(
            "services.firebase_service.merge_web_into_telegram",
            side_effect=_no_merge,
        ),
    )

    for s in stubs:
        s.start()
    try:
        res = client.post(
            "/api/v1/users/link",
            json={"code": "123456"},
            headers={"Authorization": "Bearer t"},
        )
    finally:
        for s in reversed(stubs):
            s.stop()

    assert res.status_code == 200, res.text

    # AC6 — auth_uid stamped via the bare update; no audit user.merged row.
    from services.db import get_sync_session
    from services.db.models import AuditLog, User
    with get_sync_session() as s:
        row = s.get(User, str(telegram_id))
        merged_audits = s.execute(
            select(AuditLog).where(AuditLog.event_type == "user.merged"),
        ).scalars().all()
    assert row.auth_uid == auth_uid
    assert merged_audits == []


# ── AC8: audit row written on merge ─────────────────────────────────

def test_merge_writes_audit_row(client):
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    web_id = f"web_{uuid.uuid4().hex[:12]}"
    telegram_id = 6969

    _seed(web_id, auth_uid=auth_uid, email="w@e.test", role="user", plan="free")
    _seed(str(telegram_id), auth_uid=None, role="user", plan="free")

    stubs = _stub_link_helpers(auth_uid, telegram_id)
    for s in stubs:
        s.start()
    try:
        client.post(
            "/api/v1/users/link",
            json={"code": "123456"},
            headers={"Authorization": "Bearer t"},
        )
    finally:
        for s in reversed(stubs):
            s.stop()

    from services.db import get_sync_session
    from services.db.models import AuditLog
    with get_sync_session() as s:
        audits = s.execute(
            select(AuditLog).where(AuditLog.event_type == "user.merged"),
        ).scalars().all()
    assert len(audits) == 1
    audit = audits[0]
    assert audit.target_kind == "user"
    assert audit.target_id == str(telegram_id)
    assert audit.actor_uid == "system:merge"
