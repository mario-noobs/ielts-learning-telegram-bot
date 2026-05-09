"""Unit tests for services/reminders_service.py (US-M14.3).

Pure scheduler-manipulation tests — no real bot, no real DB. We swap
the module's scheduler singleton for a fresh ``AsyncIOScheduler`` in
each test so cron jobs from other tests don't bleed in.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services import reminders_service


@pytest.fixture
def fresh_scheduler(monkeypatch):
    """Replace the singleton with an isolated, non-running scheduler."""
    sched = AsyncIOScheduler(timezone="UTC")
    monkeypatch.setattr(
        "services.scheduler_service._scheduler", sched, raising=False,
    )
    yield sched


def test_schedule_user_reminder_creates_cron_at_local_time(fresh_scheduler):
    bot = MagicMock()
    ok = reminders_service.schedule_user_reminder(
        bot, user_id=12345, daily_time="07:30", user_tz="Asia/Ho_Chi_Minh",
    )
    assert ok is True

    job = fresh_scheduler.get_job("reminder:12345")
    assert job is not None
    # CronTrigger exposes its fields via `.fields`. `hour`/`minute` are
    # stringified — looking up the active value confirms the parse.
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "7"
    assert fields["minute"] == "30"
    assert str(job.trigger.timezone) == "Asia/Ho_Chi_Minh"


def test_schedule_user_reminder_rejects_bad_time(fresh_scheduler):
    bot = MagicMock()
    assert (
        reminders_service.schedule_user_reminder(
            bot, user_id=999, daily_time="bogus", user_tz="UTC",
        )
        is False
    )
    # No job registered.
    assert fresh_scheduler.get_job("reminder:999") is None


def test_cancel_user_reminder_removes_job(fresh_scheduler):
    bot = MagicMock()
    reminders_service.schedule_user_reminder(
        bot, user_id=42, daily_time="08:00", user_tz="UTC",
    )
    assert fresh_scheduler.get_job("reminder:42") is not None

    removed = reminders_service.cancel_user_reminder(42)
    assert removed is True
    assert fresh_scheduler.get_job("reminder:42") is None

    # Idempotent: cancelling a non-existent job returns False, no raise.
    assert reminders_service.cancel_user_reminder(42) is False
