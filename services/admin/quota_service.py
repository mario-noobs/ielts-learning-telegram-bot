"""AI quota enforcement (US-M11.2).

``check_and_increment(user_uid, feature)`` is the single primitive
through which every AI-backed route bumps and gates its caller's
daily counter:

1. Resolve the effective daily cap.
   - ``users.quota_override`` if set (admin override)
   - else ``plans.daily_ai_quota`` for the user's plan
2. Atomically increment the per-user-per-day-per-feature counter via
   ``AiUsageRepo.increment`` (one Postgres round-trip,
   ``INSERT … ON CONFLICT DO UPDATE … RETURNING count``).
3. Sum today's per-feature counters into the day total.
4. Raise ``ApiError(quota.daily_exceeded)`` if the day total just
   crossed the cap. The increment is **not** rolled back — once we
   bumped, the count stands; the next call will still fail with
   the same 429. This matches the M11.5 dashboard expectation that
   `ai_calls` accurately reflects every attempt, accepted or not.

The service raises ``quota.plan_not_found`` if the user's plan
string isn't in the ``plans`` table. M11.1's FK makes that
impossible in practice but the defensive check keeps the error
surface honest if someone hand-edits the DB.
"""

from __future__ import annotations

from api.errors import ERR, ApiError
from services.repositories import get_ai_usage_repo, get_plan_repo

# Quota lookups read from Postgres directly: the M8.1 user row carries
# `plan` + `quota_override`, but the default `get_user_repo()` factory
# still returns the Firestore impl until the M8.2 cutover ships.
from services.repositories.postgres.user_repo import PostgresUserRepo

_postgres_user_repo = PostgresUserRepo()


def _effective_daily_quota(user_uid: str) -> int:
    """Return the per-user daily quota (override > plan default)."""
    user = _postgres_user_repo.get(user_uid)
    if user is None:
        # Treat missing user as 0 quota — never silently allow.
        raise ApiError(ERR.quota_plan_not_found, plan="<no-user>")

    if user.quota_override is not None:
        return int(user.quota_override)

    plan = get_plan_repo().get(user.plan)
    if plan is None:
        raise ApiError(ERR.quota_plan_not_found, plan=user.plan)
    return int(plan.daily_ai_quota)


def check_and_increment(user_uid: str, feature: str) -> int:
    """Bump the user's day counter for ``feature``; raise if over cap.

    Returns the day total (sum across features) post-increment.
    """
    cap = _effective_daily_quota(user_uid)

    usage_repo = get_ai_usage_repo()
    usage_repo.increment(user_uid=user_uid, feature=feature)

    today_by_feature = usage_repo.get_today(user_uid)
    day_total = sum(today_by_feature.values())

    if day_total > cap:
        raise ApiError(
            ERR.quota_daily_exceeded,
            plan_quota=cap,
            used=day_total,
            feature=feature,
        )
    return day_total


__all__ = ["check_and_increment"]
