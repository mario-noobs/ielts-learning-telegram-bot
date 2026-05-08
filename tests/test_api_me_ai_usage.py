"""Tests for ``GET /api/v1/me/ai-usage`` (US-M13.1)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from api.auth import get_current_user
from api.main import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping /me/ai-usage tests",
)


@pytest.fixture(autouse=True)
def _clean_ai_usage():
    from services.db import get_sync_session
    from services.db.models import AiUsage

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AiUsage))

    _wipe()
    yield
    _wipe()


def _client(user: dict) -> TestClient:
    app = create_app()

    async def _fake() -> dict:
        return user

    app.dependency_overrides[get_current_user] = _fake
    return TestClient(app)


def _seed(user_uid: str, feature: str, count: int) -> None:
    from services.db import get_sync_session
    from services.db.models import AiUsage

    today = datetime.now(timezone.utc).date()
    with get_sync_session() as s, s.begin():
        s.add(AiUsage(
            user_uid=user_uid, date=today, feature=feature,
            count=count, last_call_at=datetime.now(timezone.utc),
        ))


def test_zero_state_for_free_plan() -> None:
    """No ai_usage rows → free user gets quota=10, used=0, empty by_feature."""
    with _client({"id": "u1", "plan": "free"}) as c:
        r = c.get("/api/v1/me/ai-usage")
    assert r.status_code == 200
    body = r.json()
    assert body["plan"] == "free"
    assert body["quota_daily"] == 10
    assert body["used_today"] == 0
    assert body["by_feature"] == []
    assert body["reset_at"].endswith("+00:00")


def test_sums_per_feature_and_returns_breakdown() -> None:
    _seed("u1", "vocab", 3)
    _seed("u1", "writing", 2)
    with _client({"id": "u1", "plan": "free"}) as c:
        body = c.get("/api/v1/me/ai-usage").json()
    assert body["used_today"] == 5
    assert {f["feature"]: f["count"] for f in body["by_feature"]} == {
        "vocab": 3, "writing": 2,
    }


def test_quota_override_beats_plan_default() -> None:
    """quota_override on the user dict shadows the plan's daily_ai_quota."""
    with _client({"id": "u1", "plan": "free", "quota_override": 999}) as c:
        body = c.get("/api/v1/me/ai-usage").json()
    assert body["quota_daily"] == 999
