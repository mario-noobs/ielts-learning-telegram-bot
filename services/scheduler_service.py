import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services import vocab_service, challenge_service, firebase_service

logger = logging.getLogger(__name__)

_scheduler = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")
    return _scheduler


async def scheduled_daily_vocab(bot, group_id: int):
    """Called by scheduler to post daily vocabulary."""
    try:
        import config
        group = firebase_service.get_group_settings(group_id)
        count = config.DEFAULT_WORD_COUNT
        band = group.get("default_band", 7.0) if group else 7.0

        words, topic = await vocab_service.generate_daily_words(
            group_id=group_id, count=count, band=band
        )
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await vocab_service.save_daily_words_for_group(
            group_id, words, topic, date_str
        )

        from bot.utils import safe_send
        messages = vocab_service.format_daily_words(words, topic)
        for msg in messages:
            await safe_send(bot, msg, chat_id=group_id)
        logger.info(f"Daily vocab posted to group {group_id}")
    except Exception as e:
        logger.error(f"Failed to post daily vocab: {e}")


async def scheduled_daily_challenge(bot, group_id: int):
    """Called by scheduler to post daily challenge."""
    try:
        questions, date_str = await challenge_service.create_daily_challenge(
            group_id
        )
        message = challenge_service.format_challenge(questions, date_str)
        await bot.send_message(
            chat_id=group_id, text=message, parse_mode="Markdown"
        )
        logger.info(f"Daily challenge posted to group {group_id}")
    except Exception as e:
        logger.error(f"Failed to post daily challenge: {e}")


def setup_group_schedule(bot, group_id: int, daily_time: str = "08:00"):
    """Set up scheduled jobs for a group.

    Args:
        bot: Telegram Bot instance
        group_id: Telegram group chat ID
        daily_time: Time in HH:MM format
    """
    scheduler = get_scheduler()
    hour, minute = map(int, daily_time.split(":"))

    # Remove existing jobs for this group
    job_ids = [f"daily_vocab_{group_id}", f"daily_challenge_{group_id}"]
    for job_id in job_ids:
        existing = scheduler.get_job(job_id)
        if existing:
            existing.remove()

    # Daily vocabulary at the scheduled time
    scheduler.add_job(
        scheduled_daily_vocab,
        "cron",
        hour=hour, minute=minute,
        args=[bot, group_id],
        id=f"daily_vocab_{group_id}",
        replace_existing=True
    )

    # Daily challenge 30 minutes after vocab
    challenge_minute = (minute + 30) % 60
    challenge_hour = hour if minute + 30 < 60 else (hour + 1) % 24
    scheduler.add_job(
        scheduled_daily_challenge,
        "cron",
        hour=challenge_hour, minute=challenge_minute,
        args=[bot, group_id],
        id=f"daily_challenge_{group_id}",
        replace_existing=True
    )

    logger.info(f"Scheduled daily jobs for group {group_id} at {daily_time}")


def start_scheduler():
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
