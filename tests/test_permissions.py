"""Tests for ``api.permissions.require_role`` (US-M11.2)."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.errors import ERR, ApiError
from api.main import lifespan
from api.permissions import ROLE_LEVELS, require_role


def _build_app(user_dict: dict | None, min_role: str) -> FastAPI:
    """Build a tiny FastAPI app whose single route uses ``require_role``."""
    app = FastAPI(lifespan=lifespan)

    @app.exception_handler(ApiError)
    async def _api_error_handler(request, exc: ApiError):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.http_status, content=exc.to_response())

    async def _fake_user() -> dict:
        if user_dict is None:
            from fastapi import HTTPException, status
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no token")
        return user_dict

    app.dependency_overrides[get_current_user] = _fake_user

    @app.get("/admin/probe")
    def _probe(u: dict = Depends(require_role(min_role))):
        return {"role": u.get("role")}

    return app


def test_role_hierarchy_ordering() -> None:
    assert ROLE_LEVELS["user"] < ROLE_LEVELS["team_admin"]
    assert ROLE_LEVELS["team_admin"] < ROLE_LEVELS["org_admin"]
    assert ROLE_LEVELS["org_admin"] < ROLE_LEVELS["platform_admin"]


def test_unknown_role_raises() -> None:
    with pytest.raises(ValueError, match="unknown role"):
        require_role("god")


def test_user_with_no_role_is_403() -> None:
    """Default role is 'user'; require_role('platform_admin') must reject."""
    app = _build_app({"id": "u1"}, "platform_admin")
    with TestClient(app) as c:
        r = c.get("/admin/probe", headers={"Authorization": "Bearer x"})
        assert r.status_code == 403
        body = r.json()
        assert body["error"]["code"] == ERR.admin_forbidden_role.code
        assert body["error"]["params"]["role"] == "user"
        assert body["error"]["params"]["required"] == "platform_admin"


def test_team_admin_blocked_from_org_admin_route() -> None:
    app = _build_app({"id": "u1", "role": "team_admin"}, "org_admin")
    with TestClient(app) as c:
        r = c.get("/admin/probe", headers={"Authorization": "Bearer x"})
        assert r.status_code == 403


def test_team_admin_passes_team_admin_gate() -> None:
    app = _build_app({"id": "u1", "role": "team_admin"}, "team_admin")
    with TestClient(app) as c:
        r = c.get("/admin/probe", headers={"Authorization": "Bearer x"})
        assert r.status_code == 200
        assert r.json() == {"role": "team_admin"}


def test_platform_admin_passes_every_gate() -> None:
    for gate in ("user", "team_admin", "org_admin", "platform_admin"):
        app = _build_app({"id": "u1", "role": "platform_admin"}, gate)
        with TestClient(app) as c:
            r = c.get("/admin/probe", headers={"Authorization": "Bearer x"})
            assert r.status_code == 200, f"gate={gate} should accept platform_admin"


def test_unauthenticated_request_is_401_not_403() -> None:
    """When get_current_user itself fails (no/invalid token), require_role
    never even runs; the auth dep returns 401."""
    app = _build_app(None, "platform_admin")
    with TestClient(app) as c:
        r = c.get("/admin/probe")
        assert r.status_code == 401
