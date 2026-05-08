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

from datetime import datetime, time, timedelta, timezone
from typing import Optional

from api.errors import ERR, ApiError
from services.repositories import get_ai_usage_repo, get_plan_repo


def effective_daily_cap(plan: str, quota_override: Optional[int]) -> int:
    """Resolve the daily AI cap for a user (US-M13.2).

    Override wins over the plan default. Unknown plan raises
    ``ApiError(ERR.quota_plan_not_found)`` — same contract the previous
    private ``_plan_quota`` helper used.

    Single source of truth used by both ``check_and_increment`` (this
    module) and the M13.1 ``/api/v1/me/ai-usage`` read endpoint.
    """
    if quota_override is not None:
        return int(quota_override)
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
    cap = effective_daily_cap(plan, quota_override)

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


def get_usage_snapshot(
    user_uid: str,
    plan: str,
    quota_override: Optional[int],
) -> dict:
    """Read-only snapshot of today's AI usage for one user (US-M13.5).

    Returns ``{plan, used, cap, by_feature, reset_at}`` where:
    - ``cap`` = ``effective_daily_cap(plan, quota_override)``
    - ``by_feature`` = ``ai_usage_repo.get_today(user_uid)`` (raw counts)
    - ``used`` = ``min(sum(by_feature.values()), cap)`` (clamped per the
      M12 plan: handles the increment-then-read race and admin override-
      lowering, both of which can transiently leave raw used > cap)
    - ``reset_at`` = ISO timestamp at the next UTC midnight

    Used by the bot ``/usage`` command. Sync; bot wraps in
    ``asyncio.to_thread`` (precedent: ``services.ai_service.generate``).
    """
    cap = effective_daily_cap(plan, quota_override)
    by_feature = get_ai_usage_repo().get_today(user_uid)
    raw_used = sum(by_feature.values())
    today = datetime.now(timezone.utc).date()
    reset_at = datetime.combine(
        today + timedelta(days=1), time.min, tzinfo=timezone.utc,
    ).isoformat()
    return {
        "plan": plan,
        "used": min(raw_used, cap),
        "cap": cap,
        "by_feature": by_feature,
        "reset_at": reset_at,
    }


__all__ = ["check_and_increment", "effective_daily_cap", "get_usage_snapshot"]
