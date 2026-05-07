"""Tests for ``scripts/admin.py`` + ``scripts/backfill_admin_fields.py`` (US-M11.2)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping admin scripts tests",
)


@pytest.fixture(autouse=True)
def _truncate():
    """Wipe AuditLog + the test users this module touches."""
    from services.db import get_sync_session
    from services.db.models import AuditLog, User

    test_ids = {"adm-1", "adm-2", "bf-a", "bf-b", "bf-c"}

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(delete(AuditLog))
            s.execute(delete(User).where(User.id.in_(test_ids)))

    _wipe()
    yield
    _wipe()


def _seed_user(uid: str, *, auth_uid: str, role: str = "user", plan: str = "free") -> None:
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.add(User(id=uid, name=uid, auth_uid=auth_uid, role=role, plan=plan))


def _user_role(uid: str) -> str | None:
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s:
        u = s.get(User, uid)
        return u.role if u else None


def _user_plan(uid: str) -> str | None:
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s:
        u = s.get(User, uid)
        return u.plan if u else None


# ─── admin.py ──────────────────────────────────────────────────────


def test_grant_admin_flips_role_and_writes_audit_log() -> None:
    from scripts import admin as admin_cli
    from services.repositories import get_audit_log_repo

    _seed_user("adm-1", auth_uid="auth-1")
    rc = admin_cli.main(["grant-admin", "--uid", "auth-1"])
    assert rc == 0
    assert _user_role("adm-1") == "platform_admin"

    rows = get_audit_log_repo().list_recent(5)
    assert any(r.event_type == "user.role_granted" and r.target_id == "adm-1" for r in rows)


def test_grant_admin_unknown_uid_returns_error() -> None:
    from scripts import admin as admin_cli

    rc = admin_cli.main(["grant-admin", "--uid", "does-not-exist"])
    assert rc == 1


def test_grant_admin_idempotent_on_already_admin() -> None:
    from scripts import admin as admin_cli

    _seed_user("adm-1", auth_uid="auth-1", role="platform_admin")
    rc = admin_cli.main(["grant-admin", "--uid", "auth-1"])
    assert rc == 0  # success, no-op
    assert _user_role("adm-1") == "platform_admin"


def test_revoke_admin_flips_back_to_user() -> None:
    from scripts import admin as admin_cli

    _seed_user("adm-1", auth_uid="auth-1", role="platform_admin")
    rc = admin_cli.main(["revoke-admin", "--uid", "auth-1"])
    assert rc == 0
    assert _user_role("adm-1") == "user"


def test_set_plan_assigns_known_plan() -> None:
    from scripts import admin as admin_cli

    _seed_user("adm-1", auth_uid="auth-1")
    rc = admin_cli.main(["set-plan", "--uid", "auth-1", "--plan", "personal_pro"])
    assert rc == 0
    assert _user_plan("adm-1") == "personal_pro"


def test_set_plan_rejects_unknown_plan_via_fk() -> None:
    """The plans.id FK rejects a bogus plan id."""
    from scripts import admin as admin_cli

    _seed_user("adm-1", auth_uid="auth-1")
    rc = admin_cli.main(["set-plan", "--uid", "auth-1", "--plan", "nope"])
    assert rc == 1
    assert _user_plan("adm-1") == "free"  # original


def test_set_plan_with_invalid_expires_format_returns_error() -> None:
    from scripts import admin as admin_cli

    _seed_user("adm-1", auth_uid="auth-1")
    rc = admin_cli.main([
        "set-plan", "--uid", "auth-1", "--plan", "personal_pro",
        "--expires", "not-a-date",
    ])
    assert rc == 1


def test_list_admins_returns_only_non_user_rows(capsys) -> None:
    from scripts import admin as admin_cli

    _seed_user("adm-1", auth_uid="auth-1", role="platform_admin")
    _seed_user("adm-2", auth_uid="auth-2", role="user")  # not an admin

    rc = admin_cli.main(["list-admins"])
    assert rc == 0

    out = capsys.readouterr().out
    assert "adm-1" in out
    assert "adm-2" not in out


# ─── backfill_admin_fields.py ─────────────────────────────────────


def test_backfill_computes_fields_from_timestamps() -> None:

    import scripts.backfill_admin_fields as bf
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.add(User(
            id="bf-a", name="A",
            created_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
            last_active=datetime(2026, 5, 1, tzinfo=timezone.utc),
        ))
        s.add(User(
            id="bf-b", name="B",
            created_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            last_active=None,
        ))

    updated = bf.run()
    assert updated == 2

    with get_sync_session() as s:
        a = s.get(User, "bf-a")
        b = s.get(User, "bf-b")
    assert str(a.last_active_date) == "2026-05-01"
    assert a.signup_cohort == "2026-04"
    # bf-b had no last_active → falls back to created_at
    assert str(b.last_active_date) == "2026-01-15"
    assert b.signup_cohort == "2026-01"

    # second run: idempotent
    assert bf.run() == 0


def test_backfill_skips_rows_with_pre_set_fields() -> None:
    from datetime import date as _date

    import scripts.backfill_admin_fields as bf
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.add(User(
            id="bf-c", name="C",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            last_active_date=_date(2026, 3, 15),
            signup_cohort="2025-12",  # intentionally wrong to verify idempotency
        ))

    bf.run()

    with get_sync_session() as s:
        c = s.get(User, "bf-c")
    # untouched
    assert str(c.last_active_date) == "2026-03-15"
    assert c.signup_cohort == "2025-12"


def test_backfill_skips_rows_with_no_created_at() -> None:
    """A row without created_at can't yield a cohort; backfill leaves it."""
    import scripts.backfill_admin_fields as bf
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.add(User(id="bf-a", name="A", created_at=None, last_active=None))

    bf.run()

    with get_sync_session() as s:
        a = s.get(User, "bf-a")
    assert a.last_active_date is None
    assert a.signup_cohort is None
