"""Admin route package — every module attaches to the same ``router``.

Mounted from ``api/main.py``. All endpoints under ``/api/v1/admin/*``
are gated by ``api.permissions.require_role('platform_admin')`` (or a
narrower role on team-scoped routes that ship later).
"""

from fastapi import APIRouter

from api.routes.admin.audit import router as audit_router
from api.routes.admin.flags import router as flags_router
from api.routes.admin.metrics import router as metrics_router
from api.routes.admin.orgs import router as orgs_router
from api.routes.admin.plans import router as plans_router
from api.routes.admin.teams import router as teams_router
from api.routes.admin.users import router as users_router

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
router.include_router(users_router)
router.include_router(plans_router)
router.include_router(flags_router)
router.include_router(teams_router)
router.include_router(orgs_router)
router.include_router(metrics_router)
router.include_router(audit_router)

__all__ = ["router"]
