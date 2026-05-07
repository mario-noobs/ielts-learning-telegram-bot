"""Audit log service — every admin mutation flows through ``log_event``.

The service is the single choke point for the M11 audit trail. Behind
it sits ``services.repositories.postgres.audit_repo.PostgresAuditLogRepo``
which writes the row; the service adds two value-adds:

1. **Structlog mirror.** Every audit row also fires a structlog event
   so the same trail is searchable in our log aggregator without
   joining against Postgres. The structlog event reuses the same
   payload + the resulting ``audit_log.id``.
2. **Request-id auto-fill.** When ``request_id`` is omitted, the
   service pulls it from ``api.logging_config.request_id_ctx`` so
   admin routes don't have to thread it through manually.

Call it from admin route handlers (M11.3+) after the underlying mutation
commits, e.g.::

    from services.admin import audit_service

    audit_service.log_event(
        actor_uid=current_user["id"],
        event_type="user.role_changed",
        target_kind="user",
        target_id=str(target.id),
        before={"role": before_role},
        after={"role": new_role},
    )
"""

from __future__ import annotations

from typing import Optional

import structlog

from api.logging_config import request_id_ctx
from services.repositories import get_audit_log_repo


def log_event(
    *,
    actor_uid: str,
    event_type: str,
    target_kind: str,
    target_id: str,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    request_id: Optional[str] = None,
) -> int:
    """Record one admin mutation; return the new ``audit_log.id``.

    Keyword-only so call sites stay readable. Fields match the
    ``AuditLogRepo.append`` Protocol exactly.
    """
    if request_id is None:
        request_id = request_id_ctx.get()

    log_id = get_audit_log_repo().append(
        event_type=event_type,
        actor_uid=actor_uid,
        target_kind=target_kind,
        target_id=target_id,
        before=before,
        after=after,
        request_id=request_id,
    )

    # Fetch the logger inline (mirrors services/ai_service.py:28) so
    # ``structlog.testing.capture_logs`` in tests sees emissions even
    # after the app's cache_logger_on_first_use kicks in elsewhere.
    structlog.get_logger("audit").info(
        "admin.audit",
        audit_log_id=log_id,
        event_type=event_type,
        actor_uid=actor_uid,
        target_kind=target_kind,
        target_id=target_id,
        before=before,
        after=after,
        request_id=request_id,
    )
    return log_id


__all__ = ["log_event"]
