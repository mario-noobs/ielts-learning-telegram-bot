"""FastAPI middlewares.

``RequestIDMiddleware`` gives every request a correlation ID:
- Reads incoming ``X-Request-ID`` header; generates a UUID4 if missing.
- Binds it into a ``ContextVar`` so structlog (and anything else that
  reads from ``request_id_ctx``) can stamp every log line emitted during
  the request, including downstream service calls (e.g. Gemini).
- Echoes the ID back on the response as ``X-Request-ID``.
- Emits one structured access log per request with path/method/status/
  latency/request_id/user_id.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.logging_config import get_logger, request_id_ctx, user_id_ctx

REQUEST_ID_HEADER = "X-Request-ID"

_access_logger = get_logger("api.access")


def _coerce_request_id(raw: str | None) -> str:
    """Validate/clean incoming header. Generate UUID4 if missing or empty."""
    if raw:
        cleaned = raw.strip()
        # Cap at 128 chars to keep logs sane and avoid header abuse.
        if cleaned and len(cleaned) <= 128:
            return cleaned
    return str(uuid.uuid4())


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Stamp every request with a correlation ID and log an access line."""

    async def dispatch(self, request: Request, call_next):
        request_id = _coerce_request_id(request.headers.get(REQUEST_ID_HEADER))
        rid_token = request_id_ctx.set(request_id)
        uid_token = user_id_ctx.set(None)

        # Expose on request.state so route handlers can read it if useful.
        request.state.request_id = request_id

        start = time.perf_counter()
        status_code = 500
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)

            # Pull user id if downstream populated request.state.user.
            user_id: str | None = None
            user_obj = getattr(request.state, "user", None)
            if isinstance(user_obj, dict):
                raw_uid = user_obj.get("id") or user_obj.get("auth_uid")
                if raw_uid is not None:
                    user_id = str(raw_uid)
                    user_id_ctx.set(user_id)

            _access_logger.info(
                "api.request",
                path=request.url.path,
                method=request.method,
                status=status_code,
                latency_ms=latency_ms,
                request_id=request_id,
                user_id=user_id,
            )

            if response is not None:
                response.headers[REQUEST_ID_HEADER] = request_id

            request_id_ctx.reset(rid_token)
            user_id_ctx.reset(uid_token)
