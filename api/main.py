import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from api.errors import ERR, ApiError
from api.logging_config import configure_logging
from api.middleware import RequestIDMiddleware
from api.routes.admin import router as admin_router
from api.routes.audio import router as audio_router
from api.routes.auth import router as auth_router
from api.routes.health import router as health_router
from api.routes.listening import router as listening_router
from api.routes.plan import router as plan_router
from api.routes.progress import router as progress_router
from api.routes.quiz import router as quiz_router
from api.routes.reading import router as reading_router
from api.routes.review import router as review_router
from api.routes.topics import router as topics_router
from api.routes.vocabulary import router as vocabulary_router
from api.routes.words import router as words_router
from api.routes.writing import router as writing_router
from services import db as services_db
from services.ai_service import RateLimitError

# Configure logging once at import time so even module-level loggers
# (including services imported above) flow through the same pipeline.
configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Probe Postgres on startup so a misconfigured DATABASE_URL fails the
    # process immediately instead of at first request.
    if config.DATABASE_URL:
        await services_db.init()
    try:
        yield
    finally:
        if config.DATABASE_URL:
            await services_db.close()


def create_app() -> FastAPI:
    # Re-run in case ENV/LOG_LEVEL changed between app instantiations
    # (e.g. tests that twiddle config).
    configure_logging()

    app = FastAPI(title="IELTS Web API", version="0.1.0", lifespan=lifespan)

    # RequestIDMiddleware first so the context is set before CORS / routes
    # emit any logs. Starlette runs middlewares in reverse-add order, so
    # add CORS before RequestID to get RequestID on the outside.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        """Contract error responses (US-M7.3). Body: {error: {code, params, http_status}}."""
        return JSONResponse(status_code=exc.http_status, content=exc.to_response())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException,
    ) -> JSONResponse:
        """Bridge un-converted HTTPException into the error-code shape.

        Legacy routes still raise HTTPException(detail="Human message").
        We emit a provisional code keyed by status so the frontend's error
        renderer can at least pick a sensible fallback, and stash the
        detail in params.message for debugging / log inspection. This
        keeps existing tests green while routes migrate incrementally.
        """
        fallback_code = {
            400: ERR.validation.code,
            401: ERR.unauthorized.code,
            403: ERR.forbidden.code,
            404: ERR.not_found.code,
            409: ERR.auth_user_exists.code,
            410: ERR.reading_session_expired.code,
            429: ERR.rate_limited.code,
        }.get(exc.status_code, ERR.unknown_error.code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": fallback_code,
                    "params": {"message": str(exc.detail)} if exc.detail else {},
                    "http_status": exc.status_code,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError,
    ) -> JSONResponse:
        """FastAPI request-body validation → common.validation code."""
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ERR.validation.code,
                    "params": {"errors": exc.errors()},
                    "http_status": 422,
                }
            },
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": ERR.rate_limited.code,
                    "params": {"message": str(exc)},
                    "http_status": 429,
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": ERR.unknown_error.code,
                    "params": {"message": str(exc)},
                    "http_status": 500,
                }
            },
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(vocabulary_router)
    app.include_router(words_router)
    app.include_router(topics_router)
    app.include_router(quiz_router)
    app.include_router(review_router)
    app.include_router(audio_router)
    app.include_router(writing_router)
    app.include_router(listening_router)
    app.include_router(plan_router)
    app.include_router(progress_router)
    app.include_router(reading_router)
    app.include_router(admin_router)

    return app
