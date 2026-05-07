"""Admin route package — every module attaches to the same ``router``.

Mounted from ``api/main.py``. All endpoints under ``/api/v1/admin/*``
are gated by ``api.permissions.require_role('platform_admin')`` (or a
narrower role on team-scoped routes that ship later).
"""

from fastapi import APIRouter

from api.routes.admin.users import router as users_router

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
router.include_router(users_router)

__all__ = ["router"]
