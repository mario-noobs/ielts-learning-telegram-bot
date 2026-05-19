"""Postgres engine + session factories.

Async path used by FastAPI lifespan + future async services.
Sync path used by the existing sync repository Protocols
(``services.repositories.protocols``) which back bot handlers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

import config

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_sync_engine: Engine | None = None
_sync_sessionmaker: sessionmaker[Session] | None = None


def _require_url() -> str:
    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. See .env.example for local dev config.",
        )
    return config.DATABASE_URL


def _replace_query_key(url: str, source: str, target: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url

    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append((target if key == source else key, value))
    return urlunsplit(parts._replace(query=urlencode(query)))


def get_async_database_url() -> str:
    """Return a SQLAlchemy URL that uses asyncpg."""
    url = _require_url()
    if url.startswith("postgresql://"):
        url = f"postgresql+asyncpg://{url.removeprefix('postgresql://')}"
    return _replace_query_key(url, "sslmode", "ssl")


def get_sync_database_url() -> str:
    """Return a SQLAlchemy URL that uses the default sync Postgres driver."""
    url = _require_url()
    if url.startswith("postgresql+asyncpg://"):
        url = f"postgresql://{url.removeprefix('postgresql+asyncpg://')}"
    return _replace_query_key(url, "ssl", "sslmode")


def get_engine() -> AsyncEngine:
    """Lazy-init the async engine; one engine per process."""
    global _engine, _sessionmaker
    if _engine is None:
        url = get_async_database_url()
        _engine = create_async_engine(
            url,
            pool_size=config.DB_POOL_SIZE,
            max_overflow=20,
            pool_pre_ping=True,
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sync_engine() -> Engine:
    """Lazy-init the sync engine for use by sync repos (bot handlers)."""
    global _sync_engine, _sync_sessionmaker
    if _sync_engine is None:
        url = get_sync_database_url()
        _sync_engine = create_engine(
            url,
            pool_size=config.DB_POOL_SIZE,
            max_overflow=20,
            pool_pre_ping=True,
        )
        _sync_sessionmaker = sessionmaker(_sync_engine, expire_on_commit=False)
    return _sync_engine


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession bound to the process engine."""
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session


@contextmanager
def get_sync_session() -> Iterator[Session]:
    """Yield a sync Session bound to the process engine."""
    if _sync_sessionmaker is None:
        get_sync_engine()
    assert _sync_sessionmaker is not None
    with _sync_sessionmaker() as session:
        yield session


async def init() -> None:
    """Probe the engine on startup; fail fast if the DB is unreachable."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("postgres connection probed OK")


async def close() -> None:
    """Dispose the engine on shutdown."""
    global _engine, _sessionmaker, _sync_engine, _sync_sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
        _sync_sessionmaker = None
    logger.info("postgres engine disposed")
