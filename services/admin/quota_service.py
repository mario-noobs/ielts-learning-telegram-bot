"""AI quota enforcement (US-M11.2).

``check_and_increment(user_uid, feature, plan, quota_override)`` is
the single primitive every AI-backed route gates on:

1. Resolve the effective daily cap from the inputs.
   - ``quota_override`` if not ``None`` (admin override on the user)
   - else ``plans.daily_ai_quota`` for the named ``plan``
2. Atomically bump the per-user-per-day-per-feature counter via
   ``AiUsageRepo.increment`` (one Postgres round-trip,
   ``INSERT … ON CONFLICT DO UPDATE … RETURNING count``).
3. Sum today's per-feature counters into the day total.
4. Raise ``ApiError(quota.daily_exceeded)`` if the day total just
   crossed the cap. The increment is **not** rolled back — once we
   bumped, the count stands; the next call still 429s. This matches
   M11.5's expectation that ``ai_calls`` accurately reflects every
   attempt, accepted or not.

The service does **not** read the user from any store. Callers
(typically ``api.permissions.enforce_ai_quota``) extract ``plan`` and
``quota_override`` from the user dict already loaded by
``api.auth.get_current_user`` and pass them through. This keeps
quota enforcement agnostic to whether user data lives in Firestore
or Postgres (the M8.2 cutover is still in flight).
"""

from __future__ import annotations

from typing import Optional

from api.errors import ERR, ApiError
from services.repositories import get_ai_usage_repo, get_plan_repo


def _plan_quota(plan: str) -> int:
    plan_doc = get_plan_repo().get(plan)
    if plan_doc is None:
        raise ApiError(ERR.quota_plan_not_found, plan=plan)
    return int(plan_doc.daily_ai_quota)


def check_and_increment(
    user_uid: str,
    feature: str,
    *,
    plan: str = "free",
    quota_override: Optional[int] = None,
) -> int:
    """Bump the user's day counter for ``feature``; raise if over cap.

    Returns the day total (sum across features) post-increment.
    """
    cap = int(quota_override) if quota_override is not None else _plan_quota(plan)

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
