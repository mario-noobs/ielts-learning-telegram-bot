"""Structlog configuration for the API.

Sets up a single structlog pipeline that also handles standard library
`logging` call sites through `structlog.stdlib.ProcessorFormatter`. This
means existing `logging.getLogger(__name__)` calls elsewhere in the code
flow through the same JSON formatter — no call-site rewrites needed.

Context keys like ``request_id`` and ``user_id`` are merged in from a
``contextvars.ContextVar`` so FastAPI middleware can stamp every log
line emitted during a request.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

import config

# Per-request context. Populated by RequestIDMiddleware (and callers who
# want to propagate IDs further, e.g. services/ai_service.py).
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


def _merge_contextvars(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject request_id / user_id from contextvars into every log line."""
    rid = request_id_ctx.get()
    if rid and "request_id" not in event_dict:
        event_dict["request_id"] = rid
    uid = user_id_ctx.get()
    if uid and "user_id" not in event_dict:
        event_dict["user_id"] = uid
    return event_dict


def configure_logging() -> None:
    """Configure structlog + stdlib logging to share a single pipeline.

    Idempotent — safe to call multiple times (tests re-create the app).
    """
    env = (getattr(config, "ENV", "development") or "development").lower()
    level_name = getattr(config, "LOG_LEVEL", "INFO") or "INFO"
    level = getattr(logging, level_name.upper(), logging.INFO)

    # Processors that run for BOTH structlog loggers and stdlib loggers
    # (via ProcessorFormatter.foreign_pre_chain).
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Renderer: JSON in prod, human-friendly console in dev.
    if env == "production":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    # Configure structlog to hand off to stdlib logging. The final
    # rendering is done by ProcessorFormatter below so structlog and
    # stdlib logs share the same output format.
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Stdlib bridge — the formatter renders both foreign (stdlib) and
    # native (structlog) records through the same processor chain.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Replace handlers so we don't duplicate output across reloads / tests.
    root.handlers = [handler]
    root.setLevel(level)

    # Tame noisy third-party loggers a bit — they still flow through the
    # same JSON formatter, we just don't want DEBUG-level firehose.
    for noisy in ("uvicorn.access", "uvicorn.error", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(max(level, logging.INFO))


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger. Thin wrapper for call-site clarity."""
    return structlog.get_logger(name) if name else structlog.get_logger()
