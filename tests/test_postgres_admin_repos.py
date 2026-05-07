"""CRUD round-trips for the M11.1 admin Postgres repos."""

from __future__ import annotations

import os
import uuid
from datetime import date as _date
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping Postgres admin repo tests",
)


@pytest.fixture(autouse=True)
def _truncate_admin_tables():
    """Wipe admin tables in FK-safe order around each test. Plans are
    seed data and stay."""
    from services.db import get_sync_session
    from services.db.models import (
        AiUsage,
        AuditLog,
        Org,
        OrgAdmin,
        OrgTeam,
        PlatformMetric,
        Team,
        TeamMember,
    )

    def _wipe():
        with get_sync_session() as s, s.begin():
            for model in (
                AiUsage,
                AuditLog,
                PlatformMetric,
                OrgTeam,
                OrgAdmin,
                Org,
                TeamMember,
                Team,
            ):
                s.execute(delete(model))

    _wipe()
    yield
    _wipe()


def _plans():
    from services.repositories.postgres.plan_repo import PostgresPlanRepo
    return PostgresPlanRepo()


def _teams():
    from services.repositories.postgres.team_repo import PostgresTeamRepo
    return PostgresTeamRepo()


def _orgs():
    from services.repositories.postgres.org_repo import PostgresOrgRepo
    return PostgresOrgRepo()


def _audit():
    from services.repositories.postgres.audit_repo import PostgresAuditLogRepo
    return PostgresAuditLogRepo()


def _ai_usage():
    from services.repositories.postgres.ai_usage_repo import PostgresAiUsageRepo
    return PostgresAiUsageRepo()


def _metrics():
    from services.repositories.postgres.metrics_repo import PostgresMetricsRepo
    return PostgresMetricsRepo()


# ─── Plans ──────────────────────────────────────────────────────────


def test_plan_list_all_returns_seeded_rows() -> None:
    plans = _plans().list_all()
    ids = {p.id for p in plans}
    assert ids == {"free", "personal_pro", "team_member", "org_member"}


def test_plan_get_free_returns_quota() -> None:
    p = _plans().get("free")
    assert p is not None
    assert p.daily_ai_quota == 10
    assert p.max_team_seats is None


def test_plan_get_unknown_returns_none() -> None:
    assert _plans().get("nope") is None


# ─── Teams ──────────────────────────────────────────────────────────


def test_team_create_then_get_roundtrip() -> None:
    t = _teams().create(
        name="Team A",
        owner_uid="auth-1",
        plan_id="team_member",
        seat_limit=10,
        created_by="auth-1",
    )
    assert t.id  # uuid populated by server default
    assert t.name == "Team A"

    fetched = _teams().get(t.id)
    assert fetched is not None
    assert fetched.id == t.id
    assert fetched.plan_id == "team_member"


def test_team_update_changes_name() -> None:
    t = _teams().create(name="Old", owner_uid="u", plan_id="team_member",
                         seat_limit=5, created_by="u")
    _teams().update(t.id, {"name": "New"})
    assert _teams().get(t.id).name == "New"


def test_team_delete_cascades_members() -> None:
    t = _teams().create(name="A", owner_uid="u", plan_id="team_member",
                         seat_limit=5, created_by="u")
    _teams().add_member(t.id, "u", "admin")
    _teams().add_member(t.id, "v", "member")
    assert len(_teams().list_members(t.id)) == 2

    _teams().delete(t.id)
    assert _teams().get(t.id) is None
    # Members gone too via ON DELETE CASCADE
    assert _teams().list_members(t.id) == []


def test_team_add_remove_members() -> None:
    t = _teams().create(name="A", owner_uid="u", plan_id="team_member",
                         seat_limit=5, created_by="u")
    _teams().add_member(t.id, "alice", "member")
    _teams().add_member(t.id, "bob", "admin")

    members = _teams().list_members(t.id)
    assert {m.user_uid for m in members} == {"alice", "bob"}
    assert {m.role for m in members} == {"member", "admin"}

    _teams().remove_member(t.id, "alice")
    assert {m.user_uid for m in _teams().list_members(t.id)} == {"bob"}


def test_team_list_for_user() -> None:
    t1 = _teams().create(name="A", owner_uid="u", plan_id="team_member",
                          seat_limit=5, created_by="u")
    t2 = _teams().create(name="B", owner_uid="u", plan_id="team_member",
                          seat_limit=5, created_by="u")
    _teams().add_member(t1.id, "alice", "member")
    _teams().add_member(t2.id, "alice", "admin")

    teams = _teams().list_for_user("alice")
    assert {t.id for t in teams} == {t1.id, t2.id}


def test_team_member_role_check_constraint_rejects_bad_role() -> None:
    from sqlalchemy.exc import IntegrityError
    t = _teams().create(name="A", owner_uid="u", plan_id="team_member",
                         seat_limit=5, created_by="u")
    with pytest.raises(IntegrityError):
        _teams().add_member(t.id, "alice", "owner")  # not in CHECK ('member','admin')


# ─── Orgs ───────────────────────────────────────────────────────────


def test_org_create_then_get() -> None:
    o = _orgs().create(name="Acme", owner_uid="u", plan_id="org_member")
    assert o.id
    fetched = _orgs().get(o.id)
    assert fetched is not None
    assert fetched.name == "Acme"


def test_org_admins_round_trip() -> None:
    o = _orgs().create(name="Acme", owner_uid="u", plan_id="org_member")
    _orgs().add_admin(o.id, "alice")
    _orgs().add_admin(o.id, "bob")

    assert set(_orgs().list_admins(o.id)) == {"alice", "bob"}

    _orgs().remove_admin(o.id, "bob")
    assert _orgs().list_admins(o.id) == ["alice"]


def test_org_link_unlink_team() -> None:
    o = _orgs().create(name="Acme", owner_uid="u", plan_id="org_member")
    t = _teams().create(name="A", owner_uid="u", plan_id="team_member",
                         seat_limit=5, created_by="u")
    _orgs().link_team(o.id, t.id)
    assert _orgs().list_teams(o.id) == [t.id]

    _orgs().unlink_team(o.id, t.id)
    assert _orgs().list_teams(o.id) == []


# ─── AuditLog ───────────────────────────────────────────────────────


def test_audit_append_returns_positive_id() -> None:
    log_id = _audit().append(
        event_type="user.role_changed",
        actor_uid="admin-1",
        target_kind="user",
        target_id="42",
        before={"role": "user"},
        after={"role": "team_admin"},
        request_id="req-abc",
    )
    assert isinstance(log_id, int)
    assert log_id > 0


def test_audit_list_by_target_orders_desc() -> None:
    for i in range(3):
        _audit().append(
            event_type=f"user.update.{i}",
            actor_uid="admin",
            target_kind="user",
            target_id="42",
            before=None, after={"i": i},
            request_id=None,
        )
    rows = _audit().list_by_target("user", "42")
    assert len(rows) == 3
    # Most recent first
    assert rows[0].after["i"] == 2
    assert rows[2].after["i"] == 0


def test_audit_list_by_actor() -> None:
    _audit().append("a", "admin1", "user", "1", None, None, None)
    _audit().append("a", "admin2", "user", "1", None, None, None)
    rows = _audit().list_by_actor("admin1")
    assert len(rows) == 1
    assert rows[0].actor_uid == "admin1"


def test_audit_list_recent_caps_at_limit() -> None:
    for i in range(5):
        _audit().append("a", "admin", "user", str(i), None, None, None)
    assert len(_audit().list_recent(limit=3)) == 3


# ─── AiUsage ────────────────────────────────────────────────────────


def test_ai_usage_increment_counts_up() -> None:
    n1 = _ai_usage().increment("u1", "quiz")
    n2 = _ai_usage().increment("u1", "quiz")
    n3 = _ai_usage().increment("u1", "quiz")
    assert (n1, n2, n3) == (1, 2, 3)


def test_ai_usage_per_feature_isolated() -> None:
    _ai_usage().increment("u1", "quiz")
    _ai_usage().increment("u1", "quiz")
    _ai_usage().increment("u1", "writing")

    today = _ai_usage().get_today("u1")
    assert today == {"quiz": 2, "writing": 1}


def test_ai_usage_window_returns_recent_days() -> None:
    repo = _ai_usage()
    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)
    repo.increment("u1", "quiz", when=yesterday)
    repo.increment("u1", "quiz", when=today)

    window = repo.get_window("u1", days=2)
    assert len(window) == 2
    assert {row.date for row in window} == {today.date(), yesterday.date()}


# ─── Metrics ────────────────────────────────────────────────────────


def test_metrics_upsert_then_get_latest() -> None:
    today = _date.today()
    _metrics().upsert_daily(
        date=today,
        total_users=100, dau=42, signups=5, ai_calls=300,
        plan_distribution={"free": 90, "personal_pro": 10},
    )
    latest = _metrics().get_latest()
    assert latest is not None
    assert latest.date == today
    assert latest.dau == 42
    assert latest.plan_distribution == {"free": 90, "personal_pro": 10}


def test_metrics_upsert_overwrites_same_date() -> None:
    today = _date.today()
    _metrics().upsert_daily(today, 100, 42, 5, 300, {})
    _metrics().upsert_daily(today, 100, 99, 5, 300, {})
    assert _metrics().get_latest().dau == 99


def test_metrics_get_range_filters() -> None:
    today = _date.today()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    repo = _metrics()
    repo.upsert_daily(two_days_ago, 1, 1, 1, 1, {})
    repo.upsert_daily(yesterday, 1, 1, 1, 1, {})
    repo.upsert_daily(today, 1, 1, 1, 1, {})

    rows = repo.get_range(yesterday, today)
    assert {r.date for r in rows} == {yesterday, today}


# ─── User FK enforcement (cross-cutting) ────────────────────────────


def test_user_team_id_fk_rejects_unknown_team() -> None:
    """Smoke-test the FK constraint added in 0002."""
    from sqlalchemy import update as sql_update
    from sqlalchemy.exc import IntegrityError

    from services.db import get_sync_session
    from services.db.models import User

    bogus = str(uuid.uuid4())
    with get_sync_session() as s, s.begin():
        s.add(User(id="fk-test", name="X"))
    try:
        with pytest.raises(IntegrityError):
            with get_sync_session() as s, s.begin():
                s.execute(
                    sql_update(User).where(User.id == "fk-test").values(team_id=bogus)
                )
    finally:
        with get_sync_session() as s, s.begin():
            s.execute(delete(User).where(User.id == "fk-test"))
