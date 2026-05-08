# AI quota counting rule

**Locked product decision (2026-05-08).**

The `ai_usage` table counts only **user-initiated** AI calls. The cap on a plan
(`plans.daily_ai_quota`) and any per-user `quota_override` apply to those calls
only.

## What counts

- HTTP routes triggered by an explicit user action (button click, form submit).
  Today these are the 5 already gated in M11.2:
  - `GET /api/v1/words/{word}` (feature `words`)
  - `POST /api/v1/quiz/start` (feature `quiz`)
  - `POST /api/v1/writing/submit` (feature `writing`)
  - `POST /api/v1/listening/generate` (feature `listening`)
  - `POST /api/v1/reading/sessions` (feature `reading`)
- Bot commands the user types — `/vocab`, `/quiz`, `/word`, etc.

## What doesn't

- APScheduler cron jobs. `services/scheduler_service.scheduled_daily_vocab` posts
  vocabulary to a *group*, not a user — there is no `user_uid` to charge anyway.
- Content-bootstrap HTTP routes the platform serves on page-load:
  - `POST /api/v1/vocabulary/daily` (today's word list)
  - `GET /api/v1/progress/recommendations` (coaching tips)
  These are platform freebies, not quota-burners.

## Implementation

Single source of truth for the effective cap:

```python
# services/admin/quota_service.py
def effective_daily_cap(plan: str, quota_override: int | None) -> int:
    if quota_override is not None:
        return int(quota_override)
    plan_doc = get_plan_repo().get(plan)
    if plan_doc is None:
        raise ApiError(ERR.quota_plan_not_found, plan=plan)
    return int(plan_doc.daily_ai_quota)
```

Used by both `check_and_increment` (the choke-point on every gated route via
`api.permissions.enforce_ai_quota`) and the M13.1 `/api/v1/me/ai-usage` read
endpoint.

## Adding a new AI route

1. If the route fires from an explicit user action: add
   `Depends(enforce_ai_quota("<feature>"))` to the route signature, pick a
   stable `feature` name (snake_case, used as the `ai_usage.feature` value).
2. If the route is content the platform serves automatically: do NOT add
   `enforce_ai_quota`. Document the AI call as a freebie in this file.

The 429 response carries `{plan_quota, used, feature}` params; the frontend
localizes via the `quota.daily_exceeded` key in `errors.json`.
