"""Per-user reminder scheduling (US-M14.3).

The bot owns a single ``AsyncIOScheduler`` (see ``scheduler_service``).
This module wraps it with helpers that add/remove a per-user cron job
keyed by the user's Telegram id. The job fires at the user's preferred
``daily_time`` resolved against ``users.timezone`` and DMs them a short
streak/due-words digest.

Eligibility for a reminder:
    - ``users.id`` is numeric (i.e. row is linked to a Telegram chat)
    - ``users.auth_uid`` is set (web identity merged or originated)
    - ``users.daily_time`` is a non-empty ``HH:MM`` string

Web-only rows (``id`` starts with ``web_``) cannot receive reminders in
v1 — reminders ride the Telegram DM channel. Email + browser push defer
to M15+.

Cross-process sync: the FastAPI process can persist a ``daily_time``
change without touching the scheduler (it lives in the bot process).
``setup_reminders_resync_schedule`` registers a 15-minute drift sync
that re-reads PG and fixes any deltas — eventual consistency. For v1
that beats wiring up Postgres LISTEN/NOTIFY or a shared job store.
"""

from __future__ import annotations

import logging
from typing import Optional
from zoneinfo import ZoneInfo

import config
from services.repositories import get_user_repo
from services.scheduler_service import get_scheduler

logger = logging.getLogger(__name__)

_RESYNC_JOB_ID = "reminders_resync"


def _job_id(user_id: int | str) -> str:
    return f"reminder:{user_id}"


def _parse_hhmm(value: str) -> Optional[tuple[int, int]]:
    try:
        hour_str, minute_str = value.split(":", 1)
        hour, minute = int(hour_str), int(minute_str)
    except (ValueError, AttributeError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def _eligible(user: dict) -> bool:
    """User must be linked to Telegram + have daily_time + auth_uid."""
    user_id = str(user.get("id") or "")
    if not user_id.isdigit():
        return False
    if not user.get("auth_uid"):
        return False
    if not user.get("daily_time"):
        return False
    return True


async def _send_reminder(bot, user_id: int) -> None:
    """Job callback — fire the reminder DM for ``user_id``.

    Re-reads the user from PG at fire time so streak / due-words are
    current. Swallows send errors (user may have blocked the bot or
    deleted the DM).
    """
    try:
        from services import firebase_service
        from bot.handlers._format_reminder import format_reminder_message

        user = firebase_service.get_user(user_id)
        if not user or not _eligible(user):
            # User unlinked or cleared daily_time since the job was
            # registered — drop self.
            cancel_user_reminder(user_id)
            return

        due_words = firebase_service.get_due_words(user_id, limit=100)
        message = format_reminder_message(user, len(due_words))
        await bot.send_message(chat_id=user_id, text=message)
    except Exception as e:  # noqa: BLE001 — never crash the cron
        logger.debug("Could not send reminder to %s: %s", user_id, e)


def schedule_user_reminder(
    bot,
    user_id: int,
    daily_time: str,
    user_tz: str,
) -> bool:
    """Add or replace the cron job for ``user_id``.

    Returns True if a job was registered, False if inputs were invalid
    (caller can log + skip).
    """
    parsed = _parse_hhmm(daily_time)
    if parsed is None:
        logger.warning("Invalid daily_time=%r for user %s — skipping", daily_time, user_id)
        return False
    hour, minute = parsed

    try:
        tz = ZoneInfo(user_tz or config.DEFAULT_TIMEZONE)
    except Exception:  # noqa: BLE001 — bad tz string falls back to default
        tz = ZoneInfo(config.DEFAULT_TIMEZONE)

    scheduler = get_scheduler()
    job_id = _job_id(user_id)
    existing = scheduler.get_job(job_id)
    if existing:
        existing.remove()

    scheduler.add_job(
        _send_reminder,
        "cron",
        hour=hour,
        minute=minute,
        timezone=tz,
        args=[bot, user_id],
        id=job_id,
        replace_existing=True,
    )
    return True


def cancel_user_reminder(user_id: int | str) -> bool:
    """Remove the cron job for ``user_id``. Returns True if removed."""
    scheduler = get_scheduler()
    job = scheduler.get_job(_job_id(user_id))
    if job is None:
        return False
    job.remove()
    return True


def restore_user_reminders(bot) -> int:
    """Drift-sync: register reminder jobs for every eligible user.

    Idempotent — replaces existing jobs in place. Returns the number of
    jobs touched (added or refreshed).
    """
    try:
        users = get_user_repo().list_all()
    except Exception:  # noqa: BLE001
        logger.exception("restore_user_reminders: failed to list users")
        return 0

    eligible_ids: set[str] = set()
    touched = 0
    for u in users:
        user_dict = u.model_dump() if hasattr(u, "model_dump") else dict(u.__dict__)
        if not _eligible(user_dict):
            continue
        try:
            tg_id = int(user_dict["id"])
        except (TypeError, ValueError):
            continue
        if schedule_user_reminder(
            bot,
            tg_id,
            user_dict.get("daily_time"),
            user_dict.get("timezone") or config.DEFAULT_TIMEZONE,
        ):
            eligible_ids.add(_job_id(tg_id))
            touched += 1

    # Clean up jobs whose underlying user no longer qualifies (unlinked,
    # cleared daily_time, etc.) — keeps the scheduler honest.
    scheduler = get_scheduler()
    for job in list(scheduler.get_jobs()):
        if job.id.startswith("reminder:") and job.id not in eligible_ids:
            job.remove()

    logger.info("Restored %d user reminders", touched)
    return touched


def setup_reminders_resync_schedule(bot) -> None:
    """Periodically re-run ``restore_user_reminders`` (every 15 min).

    Picks up ``daily_time``/``timezone`` changes that the FastAPI
    process persisted but couldn't push to the scheduler directly
    (bot + API are separate processes). Eventual consistency.
    """
    scheduler = get_scheduler()
    existing = scheduler.get_job(_RESYNC_JOB_ID)
    if existing:
        existing.remove()
    scheduler.add_job(
        restore_user_reminders,
        "interval",
        minutes=15,
        args=[bot],
        id=_RESYNC_JOB_ID,
        replace_existing=True,
    )
    logger.info("Reminder resync scheduled every 15 minutes")
