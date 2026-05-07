import asyncio
from datetime import datetime, timezone

import firebase_admin.auth
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import get_current_user, security
from api.errors import ApiError, ERR
from api.models.user import LinkCodeRequest, UserCreate, UserProfile, UserUpdate
from services import firebase_service

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/me", response_model=UserProfile)
async def get_me(user: dict = Depends(get_current_user)) -> UserProfile:
    """Return the authenticated user's profile."""
    return _to_profile(user)


def _to_profile(user: dict) -> UserProfile:
    exam_raw = user.get("exam_date")
    if isinstance(exam_raw, datetime):
        exam_date = exam_raw.date().isoformat()
    elif exam_raw:
        exam_date = str(exam_raw)
    else:
        exam_date = None

    preferred_locale = user.get("preferred_locale")
    if preferred_locale not in ("en", "vi"):
        preferred_locale = None

    plan_expires_at_raw = user.get("plan_expires_at")
    if hasattr(plan_expires_at_raw, "isoformat"):
        plan_expires_at = plan_expires_at_raw.isoformat()
    elif plan_expires_at_raw:
        plan_expires_at = str(plan_expires_at_raw)
    else:
        plan_expires_at = None

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
        exam_date=exam_date,
        weekly_goal_minutes=int(user.get("weekly_goal_minutes") or 150),
        preferred_locale=preferred_locale,
        role=user.get("role") or "user",
        plan=user.get("plan") or "free",
        plan_expires_at=plan_expires_at,
        team_id=user.get("team_id"),
        org_id=user.get("org_id"),
        quota_override=user.get("quota_override"),
    )


@router.patch("/me", response_model=UserProfile)
async def update_me(
    body: UserUpdate,
    user: dict = Depends(get_current_user),
) -> UserProfile:
    """Partial update of the authenticated user's profile."""
    updates: dict = {}

    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.target_band is not None:
        updates["target_band"] = float(body.target_band)
    if body.topics is not None:
        updates["topics"] = [t.strip() for t in body.topics if t and t.strip()]
    if body.weekly_goal_minutes is not None:
        updates["weekly_goal_minutes"] = int(body.weekly_goal_minutes)
    if body.exam_date is not None:
        if body.exam_date == "":
            updates["exam_date"] = None
        else:
            try:
                parsed = datetime.strptime(body.exam_date, "%Y-%m-%d").date()
            except ValueError:
                raise ApiError(ERR.settings_invalid_exam_date, got=body.exam_date)
            updates["exam_date"] = parsed.isoformat()
    if body.preferred_locale is not None:
        updates["preferred_locale"] = body.preferred_locale

    if updates:
        await asyncio.to_thread(
            firebase_service.update_user, user["id"], updates
        )

    merged = {**user, **updates}
    return _to_profile(merged)


@router.post("/users", response_model=UserProfile, status_code=201)
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
        raise ApiError(ERR.auth_invalid_token)

    # Check if user already exists for this auth UID
    existing = await asyncio.to_thread(firebase_service.get_user_by_auth_uid, auth_uid)
    if existing:
        raise ApiError(ERR.auth_user_exists)

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
        raise ApiError(ERR.auth_invalid_token)

    code = body.code.strip()
    if not code.isdigit() or len(code) != 6:
        raise ApiError(ERR.auth_link_code_invalid)

    record = await asyncio.to_thread(firebase_service.get_link_code, code)
    if not record:
        raise ApiError(ERR.auth_link_code_not_found)

    expires_at = record.get("expires_at")
    if expires_at and expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        await asyncio.to_thread(firebase_service.delete_link_code, code)
        raise ApiError(ERR.auth_link_code_expired)

    telegram_id = int(record["telegram_id"])

    existing = await asyncio.to_thread(firebase_service.get_user_by_auth_uid, auth_uid)
    if existing:
        existing_id = str(existing.get("id"))
        if existing_id != str(telegram_id) and not existing_id.startswith("web_"):
            raise ApiError(ERR.auth_link_conflict)

    telegram_user = await asyncio.to_thread(firebase_service.get_user, telegram_id)
    if not telegram_user:
        raise ApiError(ERR.auth_user_not_registered)

    existing_auth = telegram_user.get("auth_uid")
    if existing_auth and existing_auth != auth_uid:
        raise ApiError(ERR.auth_link_conflict)

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
