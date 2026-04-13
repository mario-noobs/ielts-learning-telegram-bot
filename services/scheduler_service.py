import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from services import vocab_service, challenge_service, firebase_service, word_service

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
        date_str = config.local_date_str()
        await vocab_service.save_daily_words_for_group(
            group_id, words, topic, date_str
        )

        from bot.utils import safe_send
        messages = vocab_service.format_daily_words(words, topic)
        for msg in messages:
            await safe_send(bot, msg, chat_id=group_id)
        logger.info(f"Daily vocab posted to group {group_id}")

        # Persist enriched words to cache (sync, no Gemini calls)
        try:
            word_service.persist_generated_words(words, band)
        except Exception:
            logger.exception("Failed to persist generated words")
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


def _pick_greeting_line(user: dict, user_id: int, due_count: int) -> str | None:
    """Evaluate rules 1-5 in priority order; return the personalized line.

    Args:
        user: The full user document dict (already loaded by caller).
        user_id: Telegram user ID (int), needed for subcollection queries.
        due_count: Number of due words (already computed by caller via get_due_words).

    Returns:
        A single formatted string for the greeting body, or None to fall back
        to the existing default greeting block.
    """
    try:
        # Rule 1: User has words due for SRS review (most common case, zero extra reads)
        if due_count > 0:
            return f"\U0001f4dd You have {due_count} words due for review. /review to keep your streak."

        # Rule 2: Any word mastered yesterday (uses 48h window to handle timezone edge cases)
        mastered_words = firebase_service.get_mastered_words(user_id)
        now = datetime.now(timezone.utc)
        mastered_recently = []
        for w in mastered_words:
            next_review = w.get("srs_next_review")
            interval = w.get("srs_interval", 0)
            if next_review and interval:
                # Derive the date the word was last reviewed (approximate mastery date).
                # SM-2 sets next_review = now + timedelta(days=interval), so
                # mastery_date ≈ next_review - interval.
                if hasattr(next_review, "timestamp"):
                    mastery_date = next_review - timedelta(days=interval)
                else:
                    continue
                # 48h window instead of strict "yesterday" to account for
                # timezone differences between UTC storage and VN-time greeting
                if (now - mastery_date).total_seconds() < 48 * 3600:
                    mastered_recently.append(w)
        if mastered_recently:
            word_name = mastered_recently[0].get("word", "a word")
            total_mastered = len(mastered_words)
            return f"\u2b50 You locked in '{word_name}' yesterday. {total_mastered} words mastered total."

        # Rule 3: No quiz in 3+ days
        latest_quiz = firebase_service.get_latest_quiz(user_id)
        if latest_quiz is None:
            return "\u23f8\ufe0f Quiz streak paused for a while. /quiz to restart."
        quiz_date = latest_quiz.get("created_at")
        if quiz_date and hasattr(quiz_date, "timestamp"):
            days_inactive = (now - quiz_date).days
            if days_inactive >= 3:
                return f"\u23f8\ufe0f Quiz streak paused for {days_inactive} days. /quiz to restart."

        # Rule 4: Brand new user with no words at all
        if user.get("total_words", 0) == 0:
            return "\U0001f195 You haven't received any words yet. Try /mydaily."

        # Rule 5: Default fallback — return None so caller uses the existing greeting body
        return None

    except Exception:
        logger.warning(f"Greeting personalization failed for {user_id}", exc_info=True)
        return None


async def scheduled_daily_greeting(bot):
    """Send a daily greeting/reminder to all users via DM."""
    try:
        users = firebase_service.get_all_users()
        sent = 0
        for user in users:
            user_id = int(user["id"])
            try:
                name = user.get("name", "there")
                streak = user.get("streak", 0)
                due_words = firebase_service.get_due_words(user_id, limit=100)
                due_count = len(due_words)

                lines = [
                    f"Good morning, {name}! \u2600\ufe0f",
                    "",
                    f"\U0001f525 Streak: {streak} day{'s' if streak != 1 else ''}",
                ]

                personalized = _pick_greeting_line(user, user_id, due_count)
                if personalized:
                    lines.append(personalized)
                else:
                    # Default block (Rule 5 fallback or personalization error)
                    lines.append(
                        "\u2705 No words due \u2014 you're all caught up!"
                    )
                    lines.extend([
                        "",
                        "Quick actions:",
                        "  /mydaily \u2014 Get personalized vocab",
                        "  /quiz \u2014 Test yourself",
                        "  /write \u2014 Practice writing",
                        "",
                        "Consistency is key. Let's go! \U0001f4aa",
                    ])

                await bot.send_message(
                    chat_id=user_id, text="\n".join(lines)
                )
                sent += 1
            except Exception as e:
                # User may have blocked the bot or never started a DM
                logger.debug(f"Could not send greeting to {user_id}: {e}")

        logger.info(f"Daily greeting sent to {sent}/{len(users)} users")
    except Exception as e:
        logger.error(f"Failed to send daily greetings: {e}")


def setup_greeting_schedule(bot):
    """Set up the daily greeting job at 07:00 Vietnam time."""
    scheduler = get_scheduler()
    job_id = "daily_greeting"

    existing = scheduler.get_job(job_id)
    if existing:
        existing.remove()

    scheduler.add_job(
        scheduled_daily_greeting,
        "cron",
        hour=7, minute=0,
        args=[bot],
        id=job_id,
        replace_existing=True
    )
    logger.info("Daily greeting scheduled at 07:00")


def restore_group_schedules(bot):
    """Restore all group schedules from Firebase on bot startup."""
    try:
        groups = firebase_service.get_all_groups()
        for group in groups:
            group_id = int(group["id"])
            daily_time = group.get("daily_time", config.DEFAULT_DAILY_TIME)
            setup_group_schedule(bot, group_id, daily_time)
        logger.info(f"Restored schedules for {len(groups)} groups")
    except Exception as e:
        logger.error(f"Failed to restore group schedules: {e}")


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
