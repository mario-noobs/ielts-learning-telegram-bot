import asyncio
from datetime import datetime, timezone

import firebase_admin.auth
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import get_current_user, security
from api.models.user import LinkCodeRequest, UserCreate, UserProfile
from services import firebase_service

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/me", response_model=UserProfile)
async def get_me(user: dict = Depends(get_current_user)) -> UserProfile:
    """Return the authenticated user's profile."""
    return _to_profile(user)


def _to_profile(user: dict) -> UserProfile:
    return UserProfile(
        id=user["id"],
        name=user.get("name", ""),
        email=user.get("email"),
        target_band=user.get("target_band", 7.0),
        topics=user.get("topics", []),
        streak=user.get("streak", 0),
        total_words=user.get("total_words", 0),
        total_quizzes=user.get("total_quizzes", 0),
        total_correct=user.get("total_correct", 0),
        challenge_wins=user.get("challenge_wins", 0),
    )


@router.post("/users", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserProfile:
    """Register a new web user using the Firebase Auth token."""
    firebase_service._get_db()  # Ensure Firebase Admin is initialized

    try:
        decoded_token = firebase_admin.auth.verify_id_token(credentials.credentials)
        auth_uid = decoded_token["uid"]
        email = decoded_token.get("email", "")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Check if user already exists for this auth UID
    existing = await asyncio.to_thread(firebase_service.get_user_by_auth_uid, auth_uid)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists for this account.",
        )

    user = await asyncio.to_thread(
        firebase_service.create_web_user,
        auth_uid=auth_uid,
        email=email,
        name=body.name,
        target_band=body.target_band,
        topics=body.topics,
    )

    return _to_profile(user)


@router.post("/users/link", response_model=UserProfile)
async def link_telegram(
    body: LinkCodeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserProfile:
    """Redeem a single-use link code to map a Telegram account to the Google sign-in."""
    firebase_service._get_db()

    try:
        decoded_token = firebase_admin.auth.verify_id_token(credentials.credentials)
        auth_uid = decoded_token["uid"]
        email = decoded_token.get("email", "")
        display_name = decoded_token.get("name", "")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    code = body.code.strip()
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã không hợp lệ.",
        )

    record = await asyncio.to_thread(firebase_service.get_link_code, code)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mã. Hãy chạy /link trên bot để lấy mã mới.",
        )

    expires_at = record.get("expires_at")
    if expires_at and expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        await asyncio.to_thread(firebase_service.delete_link_code, code)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Mã đã hết hạn.",
        )

    telegram_id = int(record["telegram_id"])

    existing = await asyncio.to_thread(firebase_service.get_user_by_auth_uid, auth_uid)
    if existing:
        existing_id = str(existing.get("id"))
        if existing_id != str(telegram_id) and not existing_id.startswith("web_"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tài khoản Google này đã liên kết với người dùng khác.",
            )

    telegram_user = await asyncio.to_thread(firebase_service.get_user, telegram_id)
    if not telegram_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người dùng Telegram.",
        )

    existing_auth = telegram_user.get("auth_uid")
    if existing_auth and existing_auth != auth_uid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tài khoản Telegram này đã liên kết với tài khoản Google khác.",
        )

    await asyncio.to_thread(firebase_service.link_telegram_to_auth, telegram_id, auth_uid)
    updates: dict = {}
    if email and not telegram_user.get("email"):
        updates["email"] = email
    if display_name and not telegram_user.get("name"):
        updates["name"] = display_name
    if updates:
        await asyncio.to_thread(firebase_service.update_user, telegram_id, updates)

    await asyncio.to_thread(firebase_service.delete_link_code, code)

    merged = await asyncio.to_thread(firebase_service.get_user, telegram_id)
    return _to_profile(merged or telegram_user)
