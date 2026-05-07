"""Role-based access control + AI quota dependencies.

``require_role(min_role)`` builds a FastAPI dependency that defers to
``api.auth.get_current_user`` and then checks the resolved user's role
against the requested minimum. On insufficient role it raises
``ApiError(ERR.admin_forbidden_role, ...)`` which the global handler
in ``api.main`` serialises into the ``{error: {code, params,
http_status}}`` contract.

``enforce_ai_quota(feature)`` is the dependency every AI-backed route
hangs on: it bumps and gates the caller's daily counter via
``services.admin.quota_service.check_and_increment`` and lets
``ApiError`` propagate (429 ``quota.daily_exceeded`` or
404 ``quota.plan_not_found``).
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends

from api.auth import get_current_user
from api.errors import ERR, ApiError
from services.admin import quota_service

# Hierarchy: higher ordinal = more privileged.
ROLE_LEVELS: dict[str, int] = {
    "user": 0,
    "team_admin": 1,
    "org_admin": 2,
    "platform_admin": 3,
}


def _level(role: str) -> int:
    """Return the ordinal for a role; unknown strings → 0 ('user' floor)."""
    return ROLE_LEVELS.get(role, 0)


def require_role(min_role: str) -> Callable:
    """FastAPI dependency factory enforcing ``user.role >= min_role``.

    Usage::

        @router.get("/admin/users", dependencies=[Depends(require_role("platform_admin"))])
        def list_users(...): ...

    The user dict resolved by ``get_current_user`` is also returned, so
    routes that need both gating and the user payload can do::

        def list_users(user: dict = Depends(require_role("platform_admin"))):
            ...
    """
    if min_role not in ROLE_LEVELS:
        raise ValueError(
            f"unknown role: {min_role!r}; must be one of {sorted(ROLE_LEVELS)}",
        )

    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        role = user.get("role", "user")
        if _level(role) < _level(min_role):
            raise ApiError(
                ERR.admin_forbidden_role,
                role=role,
                required=min_role,
            )
        return user

    return _dep


def enforce_ai_quota(feature: str) -> Callable:
    """FastAPI dependency factory bumping + gating ``feature``'s daily counter.

    Usage::

        @router.post(
            "/quiz",
            dependencies=[Depends(enforce_ai_quota("quiz"))],
        )
        def make_quiz(...): ...

    The user dict from ``get_current_user`` is also returned, so routes
    that need both can do::

        def make_quiz(user: dict = Depends(enforce_ai_quota("quiz"))):
            ...

    Raises 429 ``quota.daily_exceeded`` once the day total crosses the
    user's effective cap, or 404 ``quota.plan_not_found`` if the user's
    plan isn't registered (defensive — M11.1's FK makes that
    unreachable in practice).
    """

    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        quota_service.check_and_increment(
            user_uid=str(user["id"]),
            feature=feature,
            plan=user.get("plan", "free"),
            quota_override=user.get("quota_override"),
        )
        return user

    return _dep


__all__ = ["ROLE_LEVELS", "require_role", "enforce_ai_quota"]
