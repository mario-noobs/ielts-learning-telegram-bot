"""Smoke test for the Postgres async engine + session factory."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping Postgres tests",
)


async def test_session_runs_select_1() -> None:
    from services.db import close, get_session, init

    await init()
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT 1 AS ok"))
            assert result.scalar() == 1
    finally:
        await close()
