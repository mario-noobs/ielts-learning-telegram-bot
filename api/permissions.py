"""Role-based access control dependencies for ``/api/v1/admin/*`` routes.

``require_role(min_role)`` builds a FastAPI dependency that defers to
``api.auth.get_current_user`` and then checks the resolved user's role
against the requested minimum. On insufficient role it raises
``ApiError(ERR.admin_forbidden_role, ...)`` which the global handler
in ``api.main`` serialises into the ``{error: {code, params,
http_status}}`` contract.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends

from api.auth import get_current_user
from api.errors import ERR, ApiError

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


__all__ = ["ROLE_LEVELS", "require_role"]
