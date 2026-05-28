import asyncio
import logging
from datetime import datetime, timezone

import firebase_admin.auth
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.errors import ERR, ApiError
from services import firebase_service

security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def _today_iso(d) -> str | None:
    """Coerce date | str | None to YYYY-MM-DD or None."""
    if d is None:
        return None
    if hasattr(d, "isoformat"):
        return d.isoformat()
    return str(d)


async def _touch_last_active(user: dict) -> None:
    """Bump ``users/{uid}.last_active_date`` once per UTC day (US-M11.5).

    Reads the field already loaded on ``user`` and only writes when the
    stored date differs from today. Failures are logged but never raise —
    activity tracking must not block the request path.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    if _today_iso(user.get("last_active_date")) == today:
        return
    try:
        await asyncio.to_thread(
            firebase_service.update_user, user["id"], {"last_active_date": today},
        )
        user["last_active_date"] = today
    except Exception as exc:  # noqa: BLE001 — best-effort hook
        logger.warning("activity_touch_failed user_id=%s err=%s", user.get("id"), exc)


async def _verify_local_token(access_token: str) -> dict:
    from services import local_auth_service
    try:
        email = local_auth_service.verify_access_token(access_token)
    except ValueError:
        raise ApiError(ERR.auth_local_token_invalid)

    user = await asyncio.to_thread(firebase_service.get_user_by_email_local, email)
    if not user:
        raise ApiError(ERR.auth_user_not_registered)
    await _touch_last_active(user)
    return user


async def _verify_firebase_token(token: str) -> dict:
    from services.firebase_auth import ensure_admin_initialized
    ensure_admin_initialized()
    try:
        decoded = firebase_admin.auth.verify_id_token(token)
        uid = decoded["uid"]
    except Exception as e:
        raise ApiError(ERR.auth_invalid_token) from e

    user = await asyncio.to_thread(firebase_service.get_user_by_auth_uid, uid)
    if not user:
        raise ApiError(ERR.auth_user_not_registered)
    await _touch_last_active(user)
    return user


def _is_local_access_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return False
    return payload.get("typ") == "local+jwt"


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials:
        token = credentials.credentials
        if _is_local_access_token(token):
            return await _verify_local_token(token)
        return await _verify_firebase_token(token)
    access_token = request.cookies.get("access_token")
    if access_token:
        return await _verify_local_token(access_token)
    raise ApiError(ERR.unauthorized)
