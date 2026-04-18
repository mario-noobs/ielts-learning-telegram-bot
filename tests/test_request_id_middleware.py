"""Tests for RequestIDMiddleware + structlog plumbing (US-P.2)."""

from __future__ import annotations

import asyncio
import logging
import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from api.logging_config import request_id_ctx
from api.main import create_app
from api.middleware import RequestIDMiddleware


def _is_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except (TypeError, ValueError):
        return False
    return parsed.version == 4


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


class TestRequestIDHeader:
    def test_missing_header_generates_uuid4(self, client: TestClient) -> None:
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        rid = res.headers.get("X-Request-ID")
        assert rid is not None, "response must echo X-Request-ID"
        assert _is_uuid4(rid), f"generated request id must be UUID4, got: {rid}"

    def test_incoming_header_preserved_round_trip(self, client: TestClient) -> None:
        supplied = "trace-abc-123"
        res = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": supplied},
        )
        assert res.status_code == 200
        assert res.headers.get("X-Request-ID") == supplied

    def test_blank_incoming_header_generates_new(self, client: TestClient) -> None:
        res = client.get("/api/v1/health", headers={"X-Request-ID": "   "})
        rid = res.headers.get("X-Request-ID")
        assert rid is not None
        assert rid.strip() != ""
        assert _is_uuid4(rid)


class TestConcurrentRequests:
    async def test_two_concurrent_requests_get_different_ids(self) -> None:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r1, r2 = await asyncio.gather(
                ac.get("/api/v1/health"),
                ac.get("/api/v1/health"),
            )
        assert r1.status_code == 200 and r2.status_code == 200
        rid1 = r1.headers["X-Request-ID"]
        rid2 = r2.headers["X-Request-ID"]
        assert rid1 != rid2
        assert _is_uuid4(rid1)
        assert _is_uuid4(rid2)


class TestLogBinding:
    def test_log_record_contains_request_id(self) -> None:
        """Access log for each request must carry the request_id field.

        We attach our own handler *after* create_app() because
        configure_logging replaces root handlers.
        """
        supplied = "rid-log-test-42"
        app = create_app()  # triggers configure_logging()

        records: list[logging.LogRecord] = []

        class Collector(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
                records.append(record)

        collector = Collector(level=logging.INFO)
        logging.getLogger().addHandler(collector)
        try:
            client = TestClient(app)
            res = client.get(
                "/api/v1/health", headers={"X-Request-ID": supplied}
            )
        finally:
            logging.getLogger().removeHandler(collector)

        assert res.status_code == 200

        # The access log line emitted by RequestIDMiddleware has event
        # "api.request" and must carry the request_id field. structlog
        # passes the structured event through ProcessorFormatter, so the
        # request_id ends up either as a record attribute or embedded in
        # the formatted message.
        def _has_rid(r: logging.LogRecord) -> bool:
            if getattr(r, "request_id", None) == supplied:
                return True
            msg = r.getMessage()
            return supplied in msg

        matching = [r for r in records if _has_rid(r)]
        assert matching, (
            f"expected a log record tagged with request_id={supplied!r}; "
            f"got {[(r.name, r.getMessage()[:160]) for r in records]}"
        )


class TestContextVarScoping:
    def test_context_cleared_after_request(self, client: TestClient) -> None:
        # Sanity: after a request completes, the outer context is back
        # to None (middleware resets the contextvars token).
        assert request_id_ctx.get() is None
        client.get("/api/v1/health")
        assert request_id_ctx.get() is None


class TestStandaloneMiddleware:
    """Exercise the middleware in isolation to keep the contract pinned."""

    def _tiny_app(self) -> FastAPI:
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/ping")
        async def ping(request: Request) -> dict:
            return {"rid": request.state.request_id}

        return app

    def test_state_exposes_request_id(self) -> None:
        client = TestClient(self._tiny_app())
        res = client.get("/ping")
        body = res.json()
        assert _is_uuid4(body["rid"])
        assert res.headers["X-Request-ID"] == body["rid"]
