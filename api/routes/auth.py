import asyncio

import firebase_admin.auth
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import get_current_user, security
from api.models.user import UserCreate, UserProfile
from services import firebase_service

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/me", response_model=UserProfile)
async def get_me(user: dict = Depends(get_current_user)) -> UserProfile:
    """Return the authenticated user's profile."""
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
