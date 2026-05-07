import asyncio
import logging
from datetime import datetime, timezone

import firebase_admin.auth
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services import firebase_service

security = HTTPBearer()
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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify Firebase ID token and return the corresponding user dict.

    Raises 401 for invalid/expired tokens, 404 when no user record is linked.
    """
    # Ensure Firebase Admin SDK is initialized before verifying tokens
    firebase_service._get_db()

    try:
        decoded_token = firebase_admin.auth.verify_id_token(credentials.credentials)
        uid = decoded_token["uid"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
        )

    user = await asyncio.to_thread(firebase_service.get_user_by_auth_uid, uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please register first.",
        )
    await _touch_last_active(user)
    return user
