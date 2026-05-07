"""Platform metrics + audit aggregation (US-M11.5).

Two responsibilities:

1. **Daily aggregation.** ``aggregate_daily(target_date)`` computes
   yesterday's DAU, signups, AI calls, plan distribution and total user
   count, then upserts a single ``platform_metrics`` row. The cron in
   ``services.scheduler_service`` calls this once a day; manual reruns
   are idempotent.
2. **On-demand reads** for the admin dashboard: DAU/MAU time series,
   AI usage stacked by feature, plan distribution snapshot, signup
   cohort retention, and a paginated audit-log query with filters.

Firestore is authoritative for users (signups, plan distribution, last
active); Postgres holds ``ai_usage`` (AI calls, retention proxy) and
``platform_metrics`` (the daily snapshot).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date as _date
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, select

from services import firebase_service
from services.db import get_sync_session
from services.db.models import AiUsage, AuditLog
from services.repositories import get_metrics_repo

# ─── Daily aggregation ─────────────────────────────────────────────


def aggregate_daily(target_date: _date) -> dict[str, Any]:
    """Compute and upsert the platform_metrics row for ``target_date``.

    Returns the snapshot dict for callers that want to log/inspect it.
    """
    users = firebase_service.get_all_users()
    target_iso = target_date.isoformat()

    total_users = len(users)
    dau = sum(1 for u in users if _last_active_iso(u) == target_iso)
    signups = sum(1 for u in users if _signup_date_iso(u) == target_iso)

    plan_distribution: dict[str, int] = defaultdict(int)
    for u in users:
        plan_distribution[u.get("plan") or "free"] += 1

    with get_sync_session() as s:
        ai_calls = (
            s.execute(
                select(func.coalesce(func.sum(AiUsage.count), 0))
                .where(AiUsage.date == target_date),
            ).scalar_one()
        )

    snapshot = {
        "date": target_date,
        "total_users": total_users,
        "dau": dau,
        "signups": signups,
        "ai_calls": int(ai_calls),
        "plan_distribution": dict(plan_distribution),
        "errors_count": 0,
    }
    get_metrics_repo().upsert_daily(**snapshot)
    return snapshot


# ─── DAU / MAU ─────────────────────────────────────────────────────


def dau_series(days: int) -> list[dict[str, Any]]:
    """Return one row per day for the last ``days`` days (oldest first).

    MAU is computed as the rolling 30-day sum of DAU per day. Approximate
    when individual days are missing — good enough for trend display.
    """
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    rows = get_metrics_repo().get_range(start, today)

    by_date: dict[_date, dict] = {
        r.date: {"dau": r.dau, "signups": r.signups} for r in rows
    }
    out: list[dict[str, Any]] = []
    window: list[int] = []
    cursor = start
    while cursor <= today:
        d = by_date.get(cursor, {"dau": 0, "signups": 0})
        window.append(d["dau"])
        if len(window) > 30:
            window.pop(0)
        out.append({
            "date": cursor.isoformat(),
            "dau": d["dau"],
            "signups": d["signups"],
            "mau": sum(window),
        })
        cursor = cursor + timedelta(days=1)
    return out


# ─── AI usage time series ──────────────────────────────────────────


def ai_usage_series(days: int) -> list[dict[str, Any]]:
    """Per-day, per-feature AI call counts for the last ``days`` days."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    with get_sync_session() as s:
        rows = s.execute(
            select(AiUsage.date, AiUsage.feature, func.sum(AiUsage.count))
            .where(AiUsage.date >= start)
            .where(AiUsage.date <= today)
            .group_by(AiUsage.date, AiUsage.feature)
            .order_by(AiUsage.date, AiUsage.feature),
        ).all()
    return [
        {"date": d.isoformat(), "feature": f, "count": int(c)}
        for (d, f, c) in rows
    ]


# ─── Plan distribution ─────────────────────────────────────────────


def plan_distribution() -> dict[str, int]:
    """Live snapshot of users grouped by ``plan`` (Firestore truth)."""
    users = firebase_service.get_all_users()
    out: dict[str, int] = defaultdict(int)
    for u in users:
        out[u.get("plan") or "free"] += 1
    return dict(out)


# ─── Signup cohort retention ───────────────────────────────────────


def signup_cohorts(weeks: int = 8) -> list[dict[str, Any]]:
    """Weekly signup cohorts + day-7 / day-30 retention.

    Retention is measured against ``ai_usage`` activity (the only per-day
    user-level signal we keep). For each cohort week W::

        signups        = # users whose ``created_at`` falls in W
        retained_d7    = # of those with any ai_usage row in [W+0, W+13]
        retained_d30   = # of those with any ai_usage row in [W+0, W+29]

    Cohorts are returned oldest first.
    """
    today = datetime.now(timezone.utc).date()
    # Anchor cohort weeks on Mondays.
    monday_today = today - timedelta(days=today.weekday())
    earliest_week = monday_today - timedelta(weeks=weeks - 1)

    users = firebase_service.get_all_users()
    cohort_uids: dict[_date, list[str]] = defaultdict(list)
    for u in users:
        d_iso = _signup_date_iso(u)
        if not d_iso:
            continue
        try:
            d = _date.fromisoformat(d_iso)
        except ValueError:
            continue
        if d < earliest_week:
            continue
        week_start = d - timedelta(days=d.weekday())
        if week_start > monday_today:
            continue
        cohort_uids[week_start].append(str(u.get("id")))

    out: list[dict[str, Any]] = []
    cursor = earliest_week
    while cursor <= monday_today:
        uids = cohort_uids.get(cursor, [])
        d7_end = cursor + timedelta(days=13)
        d30_end = cursor + timedelta(days=29)
        retained_d7 = _active_user_count(uids, cursor, d7_end) if uids else 0
        retained_d30 = _active_user_count(uids, cursor, d30_end) if uids else 0
        out.append({
            "cohort_week": cursor.isoformat(),
            "signups": len(uids),
            "retained_d7": retained_d7,
            "retained_d30": retained_d30,
        })
        cursor = cursor + timedelta(weeks=1)
    return out


def _active_user_count(uids: list[str], start: _date, end: _date) -> int:
    if not uids:
        return 0
    with get_sync_session() as s:
        return int(
            s.execute(
                select(func.count(func.distinct(AiUsage.user_uid)))
                .where(AiUsage.user_uid.in_(uids))
                .where(AiUsage.date >= start)
                .where(AiUsage.date <= end),
            ).scalar_one()
        )


# ─── Audit log query ───────────────────────────────────────────────


def audit_page(
    *,
    actor_uid: Optional[str] = None,
    event_type: Optional[str] = None,
    target_kind: Optional[str] = None,
    since: Optional[_date] = None,
    until: Optional[_date] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Paginated audit log query with optional filters.

    Returns ``{items, total, page, page_size}`` mirroring the admin users
    list shape so the frontend can reuse its pagination component.
    """
    page = max(1, page)
    page_size = max(1, min(200, page_size))
    filters = []
    if actor_uid:
        filters.append(AuditLog.actor_uid == actor_uid)
    if event_type:
        filters.append(AuditLog.event_type == event_type)
    if target_kind:
        filters.append(AuditLog.target_kind == target_kind)
    if since:
        filters.append(AuditLog.created_at >= datetime.combine(since, time.min, tzinfo=timezone.utc))
    if until:
        filters.append(AuditLog.created_at <= datetime.combine(until, time.max, tzinfo=timezone.utc))
    where = and_(*filters) if filters else None

    with get_sync_session() as s:
        count_stmt = select(func.count()).select_from(AuditLog)
        if where is not None:
            count_stmt = count_stmt.where(where)
        total = int(s.execute(count_stmt).scalar_one())

        list_stmt = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if where is not None:
            list_stmt = list_stmt.where(where)
        rows = s.execute(list_stmt).scalars().all()

    items = [
        {
            "id": r.id,
            "event_type": r.event_type,
            "actor_uid": r.actor_uid,
            "target_kind": r.target_kind,
            "target_id": r.target_id,
            "before": r.before,
            "after": r.after,
            "request_id": r.request_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def audit_event_types() -> list[str]:
    """Distinct ``event_type`` values currently in the audit log."""
    with get_sync_session() as s:
        rows = (
            s.execute(
                select(AuditLog.event_type).distinct().order_by(AuditLog.event_type),
            ).scalars().all()
        )
    return list(rows)


# ─── Helpers ────────────────────────────────────────────────────────


def _last_active_iso(u: dict) -> Optional[str]:
    v = u.get("last_active_date")
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _signup_date_iso(u: dict) -> Optional[str]:
    v = u.get("created_at") or u.get("signup_date") or u.get("signup_cohort")
    if v is None:
        return None
    if hasattr(v, "date"):
        return v.date().isoformat()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    s = str(v)
    return s[:10] if len(s) >= 10 else s


__all__ = [
    "aggregate_daily",
    "ai_usage_series",
    "audit_event_types",
    "audit_page",
    "dau_series",
    "plan_distribution",
    "signup_cohorts",
]
