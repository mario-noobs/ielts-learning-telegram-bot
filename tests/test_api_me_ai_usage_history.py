"""Tests for ``GET /api/v1/me/ai-usage/history`` (US-M13.4)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping /me/ai-usage/history tests",
)


def _client(user: dict) -> TestClient:
    app = create_app()

    async def _fake() -> dict:
        return user

    app.dependency_overrides[get_current_user] = _fake
    return TestClient(app)


def test_zero_state_returns_empty_list() -> None:
    """A user with no ai_usage rows gets ``[]`` (no error, no padding)."""
    with _client({"id": "u-no-history", "plan": "free"}) as c:
        r = c.get("/api/v1/me/ai-usage/history?days=30")
    assert r.status_code == 200
    assert r.json() == []


def test_days_above_max_is_rejected() -> None:
    """``days=200`` exceeds the ``le=90`` clamp → FastAPI returns 422."""
    with _client({"id": "u-clamp", "plan": "free"}) as c:
        r = c.get("/api/v1/me/ai-usage/history?days=200")
    assert r.status_code == 422
