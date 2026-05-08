"""US-M12.2 AC9 — hourly cleanup cron registration + behavior."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping cleanup tests",
)


@pytest.fixture(autouse=True)
def _truncate():
    from services.db import get_sync_session
    from services.db.models import LinkToken
    with get_sync_session() as s, s.begin():
        s.execute(delete(LinkToken))
    yield
    with get_sync_session() as s, s.begin():
        s.execute(delete(LinkToken))


def test_cleanup_link_tokens_hourly_calls_repo():
    """The bot's hourly job swallows errors and logs counts."""
    from services.db import get_sync_session
    from services.db.models import LinkToken
    from services.scheduler_service import cleanup_link_tokens_hourly
    from services.repositories.postgres import PostgresLinkTokenRepo

    repo = PostgresLinkTokenRepo()
    minted = repo.create(direction="tg_to_web", telegram_id=1)
    long_ago = datetime.now(timezone.utc) - timedelta(days=2)
    with get_sync_session() as s, s.begin():
        s.get(LinkToken, minted.token).expires_at = long_ago

    cleanup_link_tokens_hourly()

    with get_sync_session() as s:
        remaining = s.query(LinkToken).count()
    assert remaining == 0


def test_setup_link_token_cleanup_schedule_registers_job():
    """The setup hook registers an hourly job idempotently."""
    from services.scheduler_service import (
        get_scheduler,
        setup_link_token_cleanup_schedule,
        start_scheduler,
    )

    start_scheduler()
    setup_link_token_cleanup_schedule()
    job = get_scheduler().get_job("cleanup_link_tokens_hourly")
    assert job is not None

    # Calling again is idempotent — still exactly one job with the same id.
    setup_link_token_cleanup_schedule()
    assert get_scheduler().get_job("cleanup_link_tokens_hourly") is not None
