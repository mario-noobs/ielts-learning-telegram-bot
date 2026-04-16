import asyncio

import firebase_admin.auth
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services import firebase_service

security = HTTPBearer()


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
    return user
