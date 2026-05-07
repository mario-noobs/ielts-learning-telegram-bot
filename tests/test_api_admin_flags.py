"""Integration tests for ``/api/v1/admin/flags`` (US-M11.3).

These mock ``services.feature_flag_service`` rather than spinning up
Firestore — the route is a thin wrapper, the service has its own
tests.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from api.auth import get_current_user
from api.errors import ERR
from api.main import create_app
from services import feature_flag_service as ffs

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping admin/flags integration tests",
)


@pytest.fixture(autouse=True)
def _clean_audit():
    from services.db import get_sync_session
    from services.db.models import AuditLog

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AuditLog))

    _wipe()
    yield
    _wipe()


def _client() -> TestClient:
    app = create_app()

    async def _fake_user() -> dict:
        return {"id": "u-admin", "role": "platform_admin", "plan": "free"}

    app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


def _flag(
    name: str,
    enabled: bool = True,
    rollout_pct: int = 100,
    allowlist: list[str] | None = None,
    description: str = "",
) -> ffs.FeatureFlag:
    return ffs.FeatureFlag(
        name=name,
        enabled=enabled,
        rollout_pct=rollout_pct,
        uid_allowlist=tuple(allowlist or []),
        description=description,
        updated_at=None,
    )


# ─── GET /flags ─────────────────────────────────────────────────────


def test_list_flags_returns_service_results() -> None:
    fake = [_flag("design_system_v2"), _flag("reading_lab", enabled=False)]
    with patch.object(ffs, "list_flags", return_value=fake), _client() as c:
        r = c.get("/api/v1/admin/flags")
    assert r.status_code == 200
    body = r.json()
    assert {f["name"] for f in body} == {"design_system_v2", "reading_lab"}


# ─── PUT /flags/{name} ──────────────────────────────────────────────


def test_put_creates_flag_and_writes_audit_when_new() -> None:
    from services.repositories import get_audit_log_repo

    with (
        patch.object(ffs, "get_flag", return_value=None),
        patch.object(ffs, "set_flag") as mock_set,
        _client() as c,
    ):
        r = c.put(
            "/api/v1/admin/flags/design_system_v2",
            json={
                "enabled": True,
                "rollout_pct": 25,
                "uid_allowlist": ["uid1", "uid2"],
                "description": "Design system v2",
            },
        )
    assert r.status_code == 200
    mock_set.assert_called_once()
    # set_flag invoked with the body's params
    kwargs = mock_set.call_args.kwargs
    assert kwargs == {
        "enabled": True,
        "rollout_pct": 25,
        "uid_allowlist": ["uid1", "uid2"],
        "description": "Design system v2",
    }

    rows = get_audit_log_repo().list_by_target("flag", "design_system_v2")
    assert any(r.event_type == "admin.flag_upserted" for r in rows)
    audit = next(r for r in rows if r.event_type == "admin.flag_upserted")
    assert audit.before is None
    assert audit.after["enabled"] is True


def test_put_updates_existing_flag_with_before() -> None:
    from services.repositories import get_audit_log_repo

    existing = _flag("design_system_v2", enabled=False, rollout_pct=10)
    with (
        patch.object(ffs, "get_flag", return_value=existing),
        patch.object(ffs, "set_flag"),
        _client() as c,
    ):
        c.put(
            "/api/v1/admin/flags/design_system_v2",
            json={"enabled": True, "rollout_pct": 100,
                  "uid_allowlist": [], "description": ""},
        )

    audit = get_audit_log_repo().list_by_target("flag", "design_system_v2")[0]
    assert audit.before["enabled"] is False
    assert audit.before["rollout_pct"] == 10
    assert audit.after["enabled"] is True
    assert audit.after["rollout_pct"] == 100


# ─── DELETE /flags/{name} ───────────────────────────────────────────


def test_delete_existing_flag_succeeds() -> None:
    existing = _flag("design_system_v2", enabled=True)
    with (
        patch.object(ffs, "get_flag", return_value=existing),
        patch.object(ffs, "delete_flag") as mock_del,
        _client() as c,
    ):
        r = c.delete("/api/v1/admin/flags/design_system_v2")
    assert r.status_code == 200
    mock_del.assert_called_once_with("design_system_v2")


def test_delete_unknown_flag_404s() -> None:
    with patch.object(ffs, "get_flag", return_value=None), _client() as c:
        r = c.delete("/api/v1/admin/flags/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == ERR.admin_target_not_found.code
