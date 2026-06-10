import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import func, select, update

import config

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _ph.verify(hashed, plain)
        return True
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def issue_access_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "typ": "local+jwt",
        "iat": now,
        "exp": now + timedelta(minutes=config.LOCAL_ACCESS_TTL_MINUTES),
    }
    return jwt.encode(payload, config.LOCAL_JWT_SECRET, algorithm="HS256")


def verify_access_token(token: str) -> str:
    """Decode local JWT; return email. Raises ValueError on invalid/expired."""
    try:
        payload = jwt.decode(token, config.LOCAL_JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise ValueError(str(e))
    if payload.get("typ") != "local+jwt":
        raise ValueError("not a local token")
    return payload["sub"]


def issue_refresh_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Store hash; send raw to client."""
    raw = secrets.token_hex(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def _hash_raw(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def store_refresh_token(session, email: str, raw_token: str) -> None:
    from services.db.models.local_auth import LocalRefreshToken
    hashed = _hash_raw(raw_token)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=config.LOCAL_REFRESH_TTL_DAYS)
    session.add(LocalRefreshToken(
        token_hash=hashed,
        user_email=email,
        issued_at=now,
        expires_at=expires,
    ))
    session.commit()


def rotate_refresh_token(session, raw_token: str) -> tuple[str, str, str]:
    """Revoke old refresh token; issue new access + refresh tokens.

    Returns (email, new_access_token, new_raw_refresh_token).
    Raises ValueError if token is invalid/expired/revoked.
    Raises ValueError with "reuse_detected" if a revoked token is presented
    (full revocation of all user tokens follows).
    """
    from services.db.models.local_auth import LocalRefreshToken
    hashed = _hash_raw(raw_token)
    now = datetime.now(timezone.utc)
    row = session.get(LocalRefreshToken, hashed)
    if row is None:
        raise ValueError("token_not_found")
    if row.revoked_at is not None:
        # Refresh token reuse detected — revoke all tokens for this user
        session.execute(
            update(LocalRefreshToken)
            .where(LocalRefreshToken.user_email == row.user_email)
            .where(LocalRefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        session.commit()
        raise ValueError("reuse_detected")
    if row.expires_at < now:
        raise ValueError("token_expired")
    # Revoke old
    row.revoked_at = now
    # Issue new
    new_raw, new_hash = issue_refresh_token()
    session.add(LocalRefreshToken(
        token_hash=new_hash,
        user_email=row.user_email,
        issued_at=now,
        expires_at=now + timedelta(days=config.LOCAL_REFRESH_TTL_DAYS),
    ))
    session.commit()
    return row.user_email, issue_access_token(row.user_email), new_raw


def revoke_all_tokens(session, email: str) -> None:
    from services.db.models.local_auth import LocalRefreshToken
    now = datetime.now(timezone.utc)
    session.execute(
        update(LocalRefreshToken)
        .where(LocalRefreshToken.user_email == email)
        .where(LocalRefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    session.commit()


def revoke_token(session, raw_token: str) -> None:
    from services.db.models.local_auth import LocalRefreshToken
    hashed = _hash_raw(raw_token)
    now = datetime.now(timezone.utc)
    row = session.get(LocalRefreshToken, hashed)
    if row and row.revoked_at is None:
        row.revoked_at = now
        session.commit()


def check_brute_force(session, email: str) -> None:
    """Raise ValueError('too_many_attempts') if threshold exceeded."""
    from services.db.models.local_auth import LoginAttempt
    window = datetime.now(timezone.utc) - timedelta(minutes=10)
    count = session.execute(
        select(func.count()).select_from(LoginAttempt)
        .where(LoginAttempt.email == email)
        .where(LoginAttempt.attempted_at >= window)
    ).scalar()
    if count >= 5:
        raise ValueError("too_many_attempts")


def record_login_attempt(session, email: str, ip: str | None) -> None:
    from services.db.models.local_auth import LoginAttempt
    session.add(LoginAttempt(email=email, attempted_at=datetime.now(timezone.utc), ip=ip))
    session.commit()
