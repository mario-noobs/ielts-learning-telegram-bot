import pytest
from starlette.requests import Request
from fastapi.security import HTTPAuthorizationCredentials

from api import auth as auth_module

pytestmark = pytest.mark.asyncio


def _request_with_cookie(value: str | None = None) -> Request:
    headers = []
    if value:
        headers.append((b"cookie", f"access_token={value}".encode()))
    return Request({"type": "http", "headers": headers})


async def _local_user(token: str) -> dict:
    return {"id": f"local-{token}"}


async def _firebase_user(token: str) -> dict:
    return {"id": f"firebase-{token}"}


async def test_get_current_user_prefers_bearer_over_stale_local_cookie(monkeypatch):
    monkeypatch.setattr(auth_module, "_verify_local_token", _local_user)
    monkeypatch.setattr(auth_module, "_verify_firebase_token", _firebase_user)

    user = await auth_module.get_current_user(
        _request_with_cookie("old-local"),
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="new-firebase"),
    )

    assert user == {"id": "firebase-new-firebase"}


async def test_get_current_user_uses_local_cookie_when_no_bearer(monkeypatch):
    monkeypatch.setattr(auth_module, "_verify_local_token", _local_user)
    monkeypatch.setattr(auth_module, "_verify_firebase_token", _firebase_user)

    user = await auth_module.get_current_user(_request_with_cookie("local-token"), None)

    assert user == {"id": "local-local-token"}
