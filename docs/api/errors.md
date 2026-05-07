# API error codes

> **Generated from `api/errors.py` — do not hand-edit.**
> Regenerate: `python scripts/gen_error_docs.py`.

Every API error follows a single response shape (US-M7.3):

```json
{
  "error": {
    "code": "reading.passage.not_found",
    "params": { "passage_id": "p001" },
    "http_status": 404
  }
}
```

The frontend keeps a per-locale `web/public/locales/{lng}/errors.json`
mapping the dotted code to an ICU-formatted message. Unknown codes fall
back to `common.unknown_error`.

## Codes

| Code | HTTP | Summary |
|------|------|---------|
| `common.unknown_error` | 500 | Unhandled server error. |
| `common.not_found` | 404 | Resource not found. |
| `common.unauthorized` | 401 | Authentication required. |
| `common.forbidden` | 403 | Not allowed. |
| `common.validation` | 400 | Request failed validation. |
| `common.rate_limited` | 429 | Too many requests. |
| `common.upstream_error` | 502 | Upstream service error. |
| `reading.passage.not_found` | 404 | Requested reading passage does not exist. |
| `reading.session.not_found` | 404 | Reading session not found. |
| `reading.session.already_submitted` | 409 | Session is already submitted; re-submit with matching idempotency_key. |
| `reading.session.expired` | 410 | Reading session has expired. |
| `plan.not_found` | 404 | No plan exists for the given date; fetch /plan/today first. |
| `plan.activity.not_found` | 404 | Activity is not part of today's plan. |
| `auth.token.invalid` | 401 | Invalid or expired auth token. |
| `auth.user.not_registered` | 404 | No user record is linked to this account yet. |
| `auth.user.exists` | 409 | User already exists for this account. |
| `auth.link_code.invalid` | 400 | Link code must be 6 digits. |
| `auth.link_code.not_found` | 404 | Link code not found. |
| `auth.link_code.expired` | 410 | Link code has expired. |
| `auth.link.conflict` | 409 | This Google account is already linked to a different user. |
| `writing.text.too_short` | 400 | Essay is below the minimum word count. |
| `writing.submission.not_found` | 404 | Writing submission not found. |
| `writing.scoring.failed` | 502 | Essay scoring service returned invalid data. |
| `settings.exam_date.invalid` | 400 | exam_date must be YYYY-MM-DD. |
| `admin.forbidden_role` | 403 | Action requires a higher role. |
