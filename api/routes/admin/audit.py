"""Paginated admin audit-log viewer (US-M11.5).

A single ``GET /admin/audit`` endpoint with optional filters. Page size
caps at 200 server-side; the frontend defaults to 50.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.models.admin import AdminAuditPage, AdminAuditRow
from api.permissions import require_role
from services.admin import metrics_service

router = APIRouter()


@router.get(
    "/audit",
    response_model=AdminAuditPage,
    dependencies=[Depends(require_role("platform_admin"))],
)
def list_audit(
    actor_uid: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    target_kind: Optional[str] = Query(default=None),
    since: Optional[_date] = Query(default=None),
    until: Optional[_date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> AdminAuditPage:
    page_data = metrics_service.audit_page(
        actor_uid=actor_uid,
        event_type=event_type,
        target_kind=target_kind,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )
    return AdminAuditPage(
        items=[AdminAuditRow(**row) for row in page_data["items"]],
        total=page_data["total"],
        page=page_data["page"],
        page_size=page_data["page_size"],
    )


@router.get(
    "/audit/event-types",
    response_model=list[str],
    dependencies=[Depends(require_role("platform_admin"))],
)
def list_audit_event_types() -> list[str]:
    return metrics_service.audit_event_types()
