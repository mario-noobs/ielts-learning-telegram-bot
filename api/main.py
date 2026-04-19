import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from api.logging_config import configure_logging
from api.middleware import RequestIDMiddleware
from api.routes.audio import router as audio_router
from api.routes.auth import router as auth_router
from api.routes.health import router as health_router
from api.routes.listening import router as listening_router
from api.routes.plan import router as plan_router
from api.routes.progress import router as progress_router
from api.routes.quiz import router as quiz_router
from api.routes.reading import router as reading_router
from api.routes.topics import router as topics_router
from api.routes.vocabulary import router as vocabulary_router
from api.routes.words import router as words_router
from api.routes.writing import router as writing_router
from services.ai_service import RateLimitError

# Configure logging once at import time so even module-level loggers
# (including services imported above) flow through the same pipeline.
configure_logging()

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    # Re-run in case ENV/LOG_LEVEL changed between app instantiations
    # (e.g. tests that twiddle config).
    configure_logging()

    app = FastAPI(title="IELTS Web API", version="0.1.0")

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

    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "rate_limit",
                    "message": str(exc),
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
                    "code": "internal_error",
                    "message": str(exc),
                }
            },
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(vocabulary_router)
    app.include_router(words_router)
    app.include_router(topics_router)
    app.include_router(quiz_router)
    app.include_router(audio_router)
    app.include_router(writing_router)
    app.include_router(listening_router)
    app.include_router(plan_router)
    app.include_router(progress_router)
    app.include_router(reading_router)

    return app
