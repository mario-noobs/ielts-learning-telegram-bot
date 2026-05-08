"""US-M12.2 ``POST /api/v1/link/start`` coverage (AC7)."""

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
    reason="DATABASE_URL not set; skipping link/start tests",
)


@pytest.fixture(autouse=True)
def _truncate():
    from services.db import get_sync_session
    from services.db.models import LinkToken, User
    with get_sync_session() as s, s.begin():
        s.execute(delete(LinkToken))
        s.execute(delete(User))
    yield
    with get_sync_session() as s, s.begin():
        s.execute(delete(LinkToken))
        s.execute(delete(User))


@pytest.fixture(autouse=True)
def _stub_firestore():
    with patch(
        "api.auth.firebase_service._get_db", return_value=object(),
    ), patch(
        "services.firebase_service._get_db", return_value=object(),
    ):
        yield


@pytest.fixture(autouse=True)
def _config_bot_username(monkeypatch):
    """Seed BOT_USERNAME so deep-link generation has a target."""
    import config
    monkeypatch.setattr(config, "BOT_USERNAME", "ielts_test_bot", raising=False)


@pytest.fixture()
def client():
    from api.main import create_app
    return TestClient(create_app())


def _seed_user(uid, **kwargs):
    from services.db import get_sync_session
    from services.db.models import User
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.add(User(
            id=str(uid), name=kwargs.get("name", "U"), username="",
            email=kwargs.get("email", ""),
            auth_uid=kwargs.get("auth_uid"),
            target_band=7.0, topics=["edu"],
            streak=0, total_words=0, total_quizzes=0, total_correct=0,
            challenge_wins=0, role="user", plan="free",
            created_at=now,
        ))


def test_link_start_returns_token_and_bot_deep_link(client):
    """AC7 — web user with no Telegram link gets a fresh token + bot URL."""
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    web_id = f"web_{uuid.uuid4().hex[:12]}"
    _seed_user(web_id, auth_uid=auth_uid)

    with patch(
        "api.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "x@y.test"},
    ):
        res = client.post(
            "/api/v1/link/start",
            headers={"Authorization": "Bearer t"},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert "token" in body and len(body["token"]) >= 30
    assert body["bot_deep_link"].startswith("https://t.me/ielts_test_bot?start=link_")
    assert body["expires_at"]

    from services.db import get_sync_session
    from services.db.models import LinkToken
    with get_sync_session() as s:
        rows = s.execute(select(LinkToken)).scalars().all()
    assert len(rows) == 1
    assert rows[0].direction == "web_to_tg"
    assert rows[0].auth_uid == auth_uid


def test_link_start_rejects_already_linked_telegram_user(client):
    """A linked Telegram user shouldn't go through this flow — they're
    already connected. Return 409 to make the UX explicit."""
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    _seed_user("8080", auth_uid=auth_uid)

    with patch(
        "api.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "x@y.test"},
    ):
        res = client.post(
            "/api/v1/link/start",
            headers={"Authorization": "Bearer t"},
        )

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "auth.link.conflict"
