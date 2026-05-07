"""Tests for ``services.admin.quota_service`` + ``enforce_ai_quota`` (US-M11.2)."""

from __future__ import annotations

import os

import pytest
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import delete

from api.auth import get_current_user
from api.errors import ERR, ApiError
from api.permissions import enforce_ai_quota

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping quota tests",
)


@pytest.fixture(autouse=True)
def _seed_user_and_clean_usage():
    """Seed a free user (default plan='free', quota=10/day) and
    truncate ai_usage around each test."""
    from services.db import get_sync_session
    from services.db.models import AiUsage, User

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AiUsage))
            s.execute(delete(User).where(User.id.in_(["u1", "u2"])))

    _wipe()
    with get_sync_session() as s, s.begin():
        s.add(User(id="u1", name="U1"))
    yield
    _wipe()


def _override_user(uid: str) -> None:
    """Set users.quota_override on uid (write directly, no repo plumbing)."""
    from sqlalchemy import update as sql_update

    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.execute(sql_update(User).where(User.id == uid).values(quota_override=2))


def _build_app(user_dict: dict, feature: str = "quiz") -> FastAPI:
    """A tiny FastAPI app with ONE route gated by enforce_ai_quota."""
    app = FastAPI()

    @app.exception_handler(ApiError)
    async def _h(request, exc: ApiError):
        return JSONResponse(status_code=exc.http_status, content=exc.to_response())

    async def _fake_user() -> dict:
        return user_dict

    app.dependency_overrides[get_current_user] = _fake_user

    @app.post("/ai")
    def _route(u: dict = Depends(enforce_ai_quota(feature))):
        return {"id": u["id"]}

    return app


# ─── service-level ───────────────────────────────────────────────────


def test_free_user_allowed_up_to_cap_then_blocked() -> None:
    from services.admin import quota_service

    for i in range(10):
        quota_service.check_and_increment("u1", "quiz")
    with pytest.raises(ApiError) as exc:
        quota_service.check_and_increment("u1", "quiz")
    assert exc.value.code == ERR.quota_daily_exceeded.code
    assert exc.value.params["plan_quota"] == 10
    assert exc.value.params["used"] == 11


def test_quota_override_beats_plan_default() -> None:
    """quota_override=2 should block on the 3rd call."""
    from services.admin import quota_service

    _override_user("u1")
    quota_service.check_and_increment("u1", "quiz")
    quota_service.check_and_increment("u1", "quiz")
    with pytest.raises(ApiError) as exc:
        quota_service.check_and_increment("u1", "quiz")
    assert exc.value.params["plan_quota"] == 2


def test_unknown_user_raises_plan_not_found() -> None:
    from services.admin import quota_service

    with pytest.raises(ApiError) as exc:
        quota_service.check_and_increment("nope", "quiz")
    assert exc.value.code == ERR.quota_plan_not_found.code


def test_features_share_same_day_total() -> None:
    """quiz=5 + writing=5 == 10 == cap; 11th call (any feature) blocks."""
    from services.admin import quota_service

    for _ in range(5):
        quota_service.check_and_increment("u1", "quiz")
    for _ in range(5):
        quota_service.check_and_increment("u1", "writing")
    with pytest.raises(ApiError):
        quota_service.check_and_increment("u1", "listening")


# ─── enforce_ai_quota (FastAPI dependency) ──────────────────────────


def test_enforce_dep_returns_user_under_cap() -> None:
    app = _build_app({"id": "u1"})
    with TestClient(app) as c:
        r = c.post("/ai")
        assert r.status_code == 200
        assert r.json() == {"id": "u1"}


def test_enforce_dep_responds_429_when_cap_crossed() -> None:
    """11 quick POSTs: first 10 succeed, 11th gets a contract-shaped 429."""
    app = _build_app({"id": "u1"})
    with TestClient(app) as c:
        for _ in range(10):
            assert c.post("/ai").status_code == 200
        r = c.post("/ai")
        assert r.status_code == 429
        body = r.json()
        assert body["error"]["code"] == ERR.quota_daily_exceeded.code
        assert body["error"]["params"]["feature"] == "quiz"
        assert body["error"]["params"]["plan_quota"] == 10
