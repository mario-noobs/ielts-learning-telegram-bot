"""US-M8.6 cutover end-to-end: signup + link land in Postgres.

Skipped unless DATABASE_URL is set. The fixtures mock Firebase Auth
token verification and the legacy Firestore-side ``_get_db`` so the
test only relies on Postgres being reachable.
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
    reason="DATABASE_URL not set; skipping Postgres cutover tests",
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
    """Block any accidental Firestore client init during cutover tests."""
    with patch("api.routes.auth.firebase_service._get_db", return_value=object()):
        yield


@pytest.fixture()
def client():
    from api.main import create_app
    return TestClient(create_app())


def _row(auth_uid: str):
    from services.db import get_sync_session
    from services.db.models import User
    with get_sync_session() as s:
        return s.execute(select(User).where(User.auth_uid == auth_uid)).scalar_one_or_none()


# ── AC2: web signup lands in Postgres ───────────────────────────────

def test_post_users_creates_postgres_row_with_defaults(client) -> None:
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    with patch(
        "api.routes.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "a@b.test"},
    ):
        res = client.post(
            "/api/v1/users",
            json={"name": "Alice", "target_band": 7.5, "topics": ["education"]},
            headers={"Authorization": "Bearer valid-token"},
        )

    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Alice"
    assert body["role"] == "user"
    assert body["plan"] == "free"

    row = _row(auth_uid)
    assert row is not None
    assert row.id.startswith("web_")
    assert row.email == "a@b.test"
    assert row.role == "user"
    assert row.plan == "free"
    assert row.team_id is None
    assert row.org_id is None


def test_post_users_idempotent_on_repeat(client) -> None:
    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    with patch(
        "api.routes.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "a@b.test"},
    ):
        first = client.post(
            "/api/v1/users",
            json={"name": "A", "target_band": 7.0, "topics": ["education"]},
            headers={"Authorization": "Bearer t"},
        )
        second = client.post(
            "/api/v1/users",
            json={"name": "B", "target_band": 7.0, "topics": ["health"]},
            headers={"Authorization": "Bearer t"},
        )
    assert first.status_code == 201
    assert second.status_code == 409
    # Only one row total.
    from services.db import get_sync_session
    from services.db.models import User
    with get_sync_session() as s:
        rows = s.execute(select(User)).scalars().all()
    assert len([u for u in rows if u.auth_uid == auth_uid]) == 1


# ── AC4: link_telegram_to_auth upserts in Postgres ──────────────────

def test_link_telegram_updates_auth_uid_in_postgres(client) -> None:
    """Pre-seed a telegram-only Postgres row, redeem a link code, and
    assert auth_uid lands on the same row (no second row)."""
    from services.db import get_sync_session
    from services.db.models import User

    auth_uid = f"auth-{uuid.uuid4().hex[:8]}"
    telegram_id = 7777
    now = datetime.now(timezone.utc)

    with get_sync_session() as s, s.begin():
        s.add(User(
            id=str(telegram_id),
            name="Telly",
            username="telly",
            target_band=7.0,
            topics=["education"],
            streak=2,
            total_words=10,
            created_at=now,
        ))

    link_record = {
        "telegram_id": telegram_id,
        "created_at": now,
        "expires_at": now + timedelta(seconds=300),
    }
    with patch(
        "api.routes.auth.firebase_admin.auth.verify_id_token",
        return_value={"uid": auth_uid, "email": "t@y.com", "name": "Telly Linked"},
    ), patch(
        "api.routes.auth.firebase_service.get_link_code",
        return_value=link_record,
    ), patch(
        "api.routes.auth.firebase_service.delete_link_code",
    ):
        res = client.post(
            "/api/v1/users/link",
            json={"code": "123456"},
            headers={"Authorization": "Bearer t"},
        )

    assert res.status_code == 200
    row = _row(auth_uid)
    assert row is not None
    assert row.id == str(telegram_id)  # same row, not a new web_xxx
    assert row.auth_uid == auth_uid
    assert row.total_words == 10  # untouched

    with get_sync_session() as s:
        all_rows = s.execute(select(User)).scalars().all()
    assert len(all_rows) == 1
