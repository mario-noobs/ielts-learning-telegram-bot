"""Error-code API contract (US-M7.3, #128).

Every API error response follows a single shape:

    {
      "error": {
        "code": "reading.passage.not_found",
        "params": {"passage_id": "p001"},
        "http_status": 404
      }
    }

The frontend maintains a per-locale `errors.json` bundle keyed by the
dotted code, so error UI is fully localized without the server ever
shipping a prose `detail` string.

Usage:

    from api.errors import ApiError, ERR

    raise ApiError(ERR.reading_passage_not_found, passage_id=body.passage_id)

Or with a literal code (less preferred — the registry gives doc generation
and IDE navigation):

    raise ApiError("reading.passage.not_found", http_status=404, passage_id=...)

`ApiError` is a plain exception handled by the global handler in
`api/main.py`. Internally the handler serialises to the contract shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ErrorCode:
    """A registered error code. Registry entries in `ERR` carry docs + default HTTP status."""

    code: str
    http_status: int
    summary: str


class _Registry:
    """Tiny namespaced holder for ErrorCode constants used by call sites."""

    # ─── Generic / cross-cutting ──────────────────────────────────────
    unknown_error = ErrorCode("common.unknown_error", 500, "Unhandled server error.")
    not_found = ErrorCode("common.not_found", 404, "Resource not found.")
    unauthorized = ErrorCode("common.unauthorized", 401, "Authentication required.")
    forbidden = ErrorCode("common.forbidden", 403, "Not allowed.")
    validation = ErrorCode("common.validation", 400, "Request failed validation.")
    rate_limited = ErrorCode("common.rate_limited", 429, "Too many requests.")
    upstream = ErrorCode("common.upstream_error", 502, "Upstream service error.")

    # ─── Reading (US-M9.2) ────────────────────────────────────────────
    reading_passage_not_found = ErrorCode(
        "reading.passage.not_found", 404,
        "Requested reading passage does not exist.",
    )
    reading_session_not_found = ErrorCode(
        "reading.session.not_found", 404, "Reading session not found.",
    )
    reading_session_already_submitted = ErrorCode(
        "reading.session.already_submitted", 409,
        "Session is already submitted; re-submit with matching idempotency_key.",
    )
    reading_session_expired = ErrorCode(
        "reading.session.expired", 410, "Reading session has expired.",
    )

    # ─── Plan (US-4.1) ────────────────────────────────────────────────
    plan_not_found = ErrorCode(
        "plan.not_found", 404,
        "No plan exists for the given date; fetch /plan/today first.",
    )
    plan_activity_not_found = ErrorCode(
        "plan.activity.not_found", 404, "Activity is not part of today's plan.",
    )

    # ─── Auth / user (US-4.3) ─────────────────────────────────────────
    auth_invalid_token = ErrorCode(
        "auth.token.invalid", 401, "Invalid or expired auth token.",
    )
    auth_user_not_registered = ErrorCode(
        "auth.user.not_registered", 404,
        "No user record is linked to this account yet.",
    )
    auth_user_exists = ErrorCode(
        "auth.user.exists", 409, "User already exists for this account.",
    )
    auth_link_code_invalid = ErrorCode(
        "auth.link_code.invalid", 400,
        "Link code must be 6 digits.",
    )
    auth_link_code_not_found = ErrorCode(
        "auth.link_code.not_found", 404, "Link code not found.",
    )
    auth_link_code_expired = ErrorCode(
        "auth.link_code.expired", 410, "Link code has expired.",
    )
    auth_link_conflict = ErrorCode(
        "auth.link.conflict", 409,
        "This Google account is already linked to a different user.",
    )
    auth_link_merge_failed = ErrorCode(
        "auth.link.merge_failed", 500,
        "Identity merge failed during link. Try again in a moment.",
    )
    auth_link_web_only_account = ErrorCode(
        "auth.link.web_only_account", 409,
        "This account is web-only and has no Telegram link to remove.",
    )
    auth_link_token_invalid = ErrorCode(
        "auth.link.token_invalid", 404,
        "Link token not found.",
    )
    auth_link_token_expired = ErrorCode(
        "auth.link.token_expired", 410,
        "Link token has expired. Generate a new one.",
    )
    auth_link_token_already_used = ErrorCode(
        "auth.link.token_already_used", 410,
        "Link token has already been used.",
    )

    # ─── Local auth (email/password) ──────────────────────────────────
    auth_local_email_exists = ErrorCode(
        "auth.local.email_exists", 409,
        "An account with this email already exists.",
    )
    auth_local_username_taken = ErrorCode(
        "auth.local.username_taken", 409,
        "This username is already taken.",
    )
    auth_local_invalid_credentials = ErrorCode(
        "auth.local.invalid_credentials", 401,
        "Incorrect email or password.",
    )
    auth_local_too_many_attempts = ErrorCode(
        "auth.local.too_many_attempts", 429,
        "Too many failed attempts. Please wait a few minutes.",
    )
    auth_local_token_invalid = ErrorCode(
        "auth.local.token_invalid", 401,
        "Session token is invalid or expired.",
    )
    auth_local_weak_password = ErrorCode(
        "auth.local.weak_password", 400,
        "Password must be at least 8 characters and contain a letter and a number.",
    )
    auth_local_password_mismatch = ErrorCode(
        "auth.local.password_mismatch", 400,
        "Passwords do not match.",
    )
    auth_local_mfa_required = ErrorCode(
        "auth.local.mfa_required", 403,
        "Multi-factor authentication required.",
    )

    # ─── Writing (US-2.1) ─────────────────────────────────────────────
    writing_too_short = ErrorCode(
        "writing.text.too_short", 400, "Essay is below the minimum word count.",
    )
    writing_submission_not_found = ErrorCode(
        "writing.submission.not_found", 404, "Writing submission not found.",
    )
    writing_scoring_failed = ErrorCode(
        "writing.scoring.failed", 502, "Essay scoring service returned invalid data.",
    )

    # ─── Settings (US-4.3) ────────────────────────────────────────────
    settings_invalid_exam_date = ErrorCode(
        "settings.exam_date.invalid", 400, "exam_date must be YYYY-MM-DD.",
    )
    users_daily_words_invalid = ErrorCode(
        "users.daily_words_count.out_of_range", 400,
        "daily_words_count must be between 5 and 50.",
    )

    # ─── Admin (US-M11.2 / US-M11.3) ──────────────────────────────────
    admin_forbidden_role = ErrorCode(
        "admin.forbidden_role", 403,
        "Action requires a higher role.",
    )
    admin_target_not_found = ErrorCode(
        "admin.target_not_found", 404,
        "Admin operation target does not exist.",
    )
    admin_invalid_role_change = ErrorCode(
        "admin.invalid_role_change", 400,
        "Role change not allowed for the current actor.",
    )

    # ─── Teams (US-M11.4) ─────────────────────────────────────────────
    team_seat_limit_reached = ErrorCode(
        "team.seat_limit_reached", 409,
        "Team is at its seat limit.",
    )
    team_member_already_exists = ErrorCode(
        "team.member_already_exists", 409,
        "User is already a member of this team.",
    )
    team_not_member = ErrorCode(
        "team.not_member", 404,
        "User is not a member of this team.",
    )

    # ─── Quota (US-M11.2) ─────────────────────────────────────────────
    quota_daily_exceeded = ErrorCode(
        "quota.daily_exceeded", 429,
        "Daily AI usage cap reached for this plan.",
    )
    quota_plan_not_found = ErrorCode(
        "quota.plan_not_found", 404,
        "User's plan is not registered in the plans table.",
    )

    # ─── AI router (US-#221) ──────────────────────────────────────────
    ai_provider_unavailable = ErrorCode(
        "ai.provider_unavailable", 503,
        "All AI providers in the chain are unavailable. Please try again.",
    )
    ai_rate_limited = ErrorCode(
        "ai.rate_limited", 503,
        "AI provider is rate-limited; no cached fallback available. Try again shortly.",
    )

    # ─── Group management (US-#227) ───────────────────────────────────
    groups_not_member = ErrorCode(
        "groups.not_member", 404,
        "Group not found or you are not a member.",
    )
    groups_forbidden_not_owner = ErrorCode(
        "groups.forbidden_not_owner", 403,
        "Only the group owner can edit settings.",
    )

    # ─── Vocab manual override (US-#231) ──────────────────────────────
    vocab_word_not_found = ErrorCode(
        "vocab.word_not_found", 404,
        "Word not found in your vocabulary.",
    )
    vocab_override_rate_limited = ErrorCode(
        "vocab.override_rate_limited", 429,
        "Too many manual mastery changes today. Try again tomorrow.",
    )


ERR = _Registry()


def all_codes() -> list[ErrorCode]:
    """Return every registered ErrorCode in declaration order (used by docs)."""
    return [
        v for k, v in vars(_Registry).items()
        if not k.startswith("_") and isinstance(v, ErrorCode)
    ]


@dataclass
class ApiError(Exception):
    """Exception raised by routes/services; serialised by the global handler.

    Callers pass an ``ErrorCode`` (registered) or a raw string code + http_status.
    Extra keyword args become the ``params`` dict surfaced to the client,
    available for ICU interpolation in ``errors.<lng>.json``.
    """

    code: str
    http_status: int = 500
    params: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        code: str | ErrorCode,
        *,
        http_status: int | None = None,
        **params: Any,
    ) -> None:
        if isinstance(code, ErrorCode):
            self.code = code.code
            self.http_status = http_status or code.http_status
        else:
            self.code = code
            self.http_status = http_status or 500
        self.params = params
        super().__init__(self.code)

    def to_response(self) -> dict[str, Any]:
        """Return the JSON body for the error handler."""
        return {
            "error": {
                "code": self.code,
                "params": self.params,
                "http_status": self.http_status,
            }
        }


__all__ = ["ApiError", "ERR", "ErrorCode", "all_codes"]
