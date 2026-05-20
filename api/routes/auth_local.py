import asyncio
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response

from api.errors import ERR, ApiError

router = APIRouter(prefix="/api/v1/auth/local", tags=["local-auth"])

_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    import config
    secure = config.ENV != "development"
    response.set_cookie(
        ACCESS_COOKIE, access,
        max_age=config.LOCAL_ACCESS_TTL_MINUTES * 60,
        httponly=True, samesite="lax", secure=secure,
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh,
        max_age=config.LOCAL_REFRESH_TTL_DAYS * 86400,
        httponly=True, samesite="lax", secure=secure,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE)


@router.post("/register", status_code=201)
async def register(body: dict, response: Response):
    from services import local_auth_service
    from services.db import get_sync_session

    email = (body.get("email") or "").strip().lower()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    confirm = body.get("confirm_password") or ""
    phone = (body.get("phone") or "").strip() or None
    address = (body.get("address") or "").strip() or None

    if not email or "@" not in email:
        raise ApiError(ERR.validation, field="email", message="Valid email required.")
    if not username or len(username) < 3:
        raise ApiError(ERR.validation, field="username", message="Username must be 3+ characters.")
    if password != confirm:
        raise ApiError(ERR.auth_local_password_mismatch)
    if not _PASSWORD_RE.match(password):
        raise ApiError(ERR.auth_local_weak_password)

    password_hash = local_auth_service.hash_password(password)
    user_id = f"web_{uuid.uuid4().hex}"

    def _create():
        with get_sync_session() as session:
            from sqlalchemy import select
            from services.db.models.user import User

            existing_email = session.execute(
                select(User).where(User.email == email).where(User.local_auth.is_(True))
            ).scalar_one_or_none()
            if existing_email:
                raise ApiError(ERR.auth_local_email_exists)

            existing_username = session.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()
            if existing_username:
                raise ApiError(ERR.auth_local_username_taken)

            now = datetime.now(timezone.utc)
            user = User(
                id=user_id,
                email=email,
                username=username,
                name=username,
                password_hash=password_hash,
                phone=phone,
                address=address,
                local_auth=True,
                email_verified=False,
                created_at=now,
                last_active=now,
            )
            session.add(user)
            session.flush()

            raw_refresh, _ = local_auth_service.issue_refresh_token()
            local_auth_service.store_refresh_token(session, email, raw_refresh)
            return user, raw_refresh

    user_row, raw_refresh = await asyncio.to_thread(_create)
    access = local_auth_service.issue_access_token(email)
    _set_auth_cookies(response, access, raw_refresh)

    return {"user": {"id": user_row.id, "email": email, "username": username, "name": username}}


@router.post("/login")
async def login(body: dict, request: Request, response: Response):
    from services import local_auth_service
    from services.db import get_sync_session

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    ip = request.client.host if request.client else None

    def _auth():
        with get_sync_session() as session:
            try:
                local_auth_service.check_brute_force(session, email)
            except ValueError:
                raise ApiError(ERR.auth_local_too_many_attempts)

            from sqlalchemy import select
            from services.db.models.user import User

            user = session.execute(
                select(User).where(User.email == email).where(User.local_auth.is_(True))
            ).scalar_one_or_none()

            # Always run verify to avoid timing oracle even when user not found
            dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$dummydummydummydummydummydummy$dummydummydummydummydummydummydummy"
            stored_hash = user.password_hash if user else dummy_hash
            ok = local_auth_service.verify_password(password, stored_hash)
            if not ok or user is None:
                local_auth_service.record_login_attempt(session, email, ip)
                raise ApiError(ERR.auth_local_invalid_credentials)

            raw_refresh, _ = local_auth_service.issue_refresh_token()
            local_auth_service.store_refresh_token(session, email, raw_refresh)
            return user, raw_refresh

    user_row, raw_refresh = await asyncio.to_thread(_auth)
    access = local_auth_service.issue_access_token(email)
    _set_auth_cookies(response, access, raw_refresh)

    return {
        "user": {
            "id": user_row.id,
            "email": email,
            "username": user_row.username,
            "name": user_row.name,
        }
    }


@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    from services import local_auth_service
    from services.db import get_sync_session

    raw = request.cookies.get("refresh_token")
    if not raw:
        raise ApiError(ERR.auth_local_token_invalid)

    def _rotate():
        with get_sync_session() as session:
            try:
                return local_auth_service.rotate_refresh_token(session, raw)
            except ValueError as e:
                raise ApiError(ERR.auth_local_token_invalid) from e

    email, new_access, new_refresh = await asyncio.to_thread(_rotate)
    _set_auth_cookies(response, new_access, new_refresh)
    return {}


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    from services import local_auth_service
    from services.db import get_sync_session

    raw = request.cookies.get("refresh_token")
    if raw:
        def _revoke():
            with get_sync_session() as session:
                local_auth_service.revoke_token(session, raw)
        await asyncio.to_thread(_revoke)

    _clear_auth_cookies(response)
