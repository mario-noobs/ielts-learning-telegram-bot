"""Tests for ``services.admin.audit_service.log_event`` (US-M11.2)."""

from __future__ import annotations

import os

import pytest
import structlog
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping audit_service tests",
)


@pytest.fixture(autouse=True)
def _truncate_audit_log():
    from services.db import get_sync_session
    from services.db.models import AuditLog

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AuditLog))

    _wipe()
    yield
    _wipe()


def test_log_event_writes_row_and_returns_id() -> None:
    from services.admin import audit_service
    from services.repositories import get_audit_log_repo

    log_id = audit_service.log_event(
        actor_uid="admin-1",
        event_type="user.role_changed",
        target_kind="user",
        target_id="42",
        before={"role": "user"},
        after={"role": "team_admin"},
        request_id="req-x",
    )
    assert isinstance(log_id, int) and log_id > 0

    rows = get_audit_log_repo().list_recent(10)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == log_id
    assert row.event_type == "user.role_changed"
    assert row.actor_uid == "admin-1"
    assert row.target_kind == "user"
    assert row.target_id == "42"
    assert row.before == {"role": "user"}
    assert row.after == {"role": "team_admin"}
    assert row.request_id == "req-x"


def test_log_event_emits_structlog_record() -> None:
    """``capture_logs`` works regardless of the app's
    cache_logger_on_first_use config — tests run after create_app()."""
    from services.admin import audit_service

    with structlog.testing.capture_logs() as captured:
        audit_service.log_event(
            actor_uid="admin-1",
            event_type="plan.assigned",
            target_kind="user",
            target_id="42",
            before=None,
            after={"plan": "personal_pro"},
            request_id="req-y",
        )

    audit_events = [e for e in captured if e.get("event") == "admin.audit"]
    assert len(audit_events) == 1
    e = audit_events[0]
    assert e["actor_uid"] == "admin-1"
    assert e["event_type"] == "plan.assigned"
    assert e["target_kind"] == "user"
    assert e["target_id"] == "42"
    assert e["after"] == {"plan": "personal_pro"}
    assert e["request_id"] == "req-y"
    assert isinstance(e["audit_log_id"], int)


def test_log_event_pulls_request_id_from_ctx_when_missing() -> None:
    from api.logging_config import request_id_ctx
    from services.admin import audit_service
    from services.repositories import get_audit_log_repo

    token = request_id_ctx.set("ctx-req-123")
    try:
        audit_service.log_event(
            actor_uid="admin-1",
            event_type="x",
            target_kind="user",
            target_id="42",
            before=None,
            after=None,
        )
    finally:
        request_id_ctx.reset(token)

    rows = get_audit_log_repo().list_recent(1)
    assert rows[0].request_id == "ctx-req-123"


def test_log_event_request_id_none_when_no_ctx_and_not_passed() -> None:
    from services.admin import audit_service
    from services.repositories import get_audit_log_repo

    audit_service.log_event(
        actor_uid="admin-1",
        event_type="x",
        target_kind="user",
        target_id="42",
        before=None,
        after=None,
    )
    rows = get_audit_log_repo().list_recent(1)
    assert rows[0].request_id is None
