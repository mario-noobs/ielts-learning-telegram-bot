import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from services import challenge_service, firebase_service, vocab_service, word_service

logger = logging.getLogger(__name__)

_scheduler = None
_bot_username_cache = None


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
        count = group.get("word_count", config.DEFAULT_WORD_COUNT) if group else config.DEFAULT_WORD_COUNT
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
    """Called by scheduler to post daily challenge with deep-link button."""
    try:
        questions, date_str = await challenge_service.create_daily_challenge(
            group_id
        )

        # Get bot username for deep-link (cached)
        global _bot_username_cache
        if not _bot_username_cache:
            bot_info = await bot.get_me()
            _bot_username_cache = bot_info.username
        bot_username = _bot_username_cache

        # Get group info for topic/band display
        group = firebase_service.get_group_settings(group_id)
        topic = None
        band = None
        if group:
            import random
            topic = random.choice(group.get("topics", ["education"]))
            band = group.get("default_band", 7.0)

        text, markup = challenge_service.format_challenge_post(
            date_str, bot_username, group_id, topic=topic, band=band
        )
        await bot.send_message(
            chat_id=group_id, text=text,
            reply_markup=markup, parse_mode="Markdown"
        )
        logger.info(f"Daily challenge posted to group {group_id}")

        # Schedule expiry job
        challenge = firebase_service.get_challenge(group_id, date_str)
        if challenge:
            expires_at = challenge.get("expires_at")
            if expires_at:
                schedule_challenge_expiry(bot, group_id, date_str, expires_at)

    except Exception as e:
        logger.error(f"Failed to post daily challenge: {e}")


def schedule_challenge_expiry(bot, group_id: int, date_str: str, expires_at):
    """Register a one-shot APScheduler job to close the challenge at expires_at."""
    scheduler = get_scheduler()
    job_id = f"challenge_expiry_{group_id}_{date_str}"

    existing = scheduler.get_job(job_id)
    if existing:
        logger.info(f"Expiry job {job_id} already exists, skipping")
        return

    # If expires_at is already past, run immediately (misfire recovery)
    now = datetime.now(timezone.utc)
    if hasattr(expires_at, 'timestamp') and expires_at <= now:
        run_date = now + timedelta(seconds=5)
    else:
        run_date = expires_at

    scheduler.add_job(
        scheduled_challenge_expiry,
        trigger="date",
        run_date=run_date,
        args=[bot, group_id, date_str],
        id=job_id,
        misfire_grace_time=3600,  # allow up to 1 hour late
    )
    logger.info(f"Scheduled challenge expiry: {job_id} at {run_date}")


async def scheduled_challenge_expiry(bot, group_id: int, date_str: str):
    """One-shot expiry job: close the challenge and post leaderboard to group."""
    try:
        result = challenge_service.close_and_score(group_id, date_str)
        if not result:
            logger.warning(f"Expiry job: no challenge found for {group_id}/{date_str}")
            return

        text = challenge_service._build_results_text(result, date_str)
        from bot.utils import safe_send
        await safe_send(bot, text, chat_id=group_id)
        logger.info(f"Challenge expiry: posted results to group {group_id}")
    except Exception as e:
        logger.error(f"Challenge expiry job failed for {group_id}/{date_str}: {e}")


def setup_group_schedule(bot, group_id: int, daily_time: str = None,
                         challenge_time: str = None):
    """Set up scheduled jobs for a group.

    Args:
        bot: Telegram Bot instance
        group_id: Telegram group chat ID
        daily_time: Vocab time in HH:MM (reads from group settings if None)
        challenge_time: Challenge time in HH:MM (reads from group settings if None)
    """
    if daily_time is None or challenge_time is None:
        group = firebase_service.get_group_settings(group_id)
        if daily_time is None:
            daily_time = group.get("daily_time", config.DEFAULT_DAILY_TIME) if group else config.DEFAULT_DAILY_TIME
        if challenge_time is None:
            challenge_time = group.get("challenge_time", config.DEFAULT_CHALLENGE_TIME) if group else config.DEFAULT_CHALLENGE_TIME

    scheduler = get_scheduler()

    # Remove existing jobs for this group
    job_ids = [f"daily_vocab_{group_id}", f"daily_challenge_{group_id}"]
    for job_id in job_ids:
        existing = scheduler.get_job(job_id)
        if existing:
            existing.remove()

    # Daily vocabulary at configured time
    v_hour, v_minute = map(int, daily_time.split(":"))
    scheduler.add_job(
        scheduled_daily_vocab,
        "cron",
        hour=v_hour, minute=v_minute,
        args=[bot, group_id],
        id=f"daily_vocab_{group_id}",
        replace_existing=True
    )

    # Daily challenge at its own configured time
    c_hour, c_minute = map(int, challenge_time.split(":"))
    scheduler.add_job(
        scheduled_daily_challenge,
        "cron",
        hour=c_hour, minute=c_minute,
        args=[bot, group_id],
        id=f"daily_challenge_{group_id}",
        replace_existing=True
    )

    logger.info(f"Scheduled: vocab at {daily_time}, challenge at {challenge_time} for group {group_id}")


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


def aggregate_platform_metrics_daily():
    """US-M11.5: aggregate yesterday's metrics into ``platform_metrics``.

    Idempotent — re-running for the same date overwrites the row. Wired
    through ``setup_metrics_schedule`` to fire at 00:30 Asia/Ho_Chi_Minh.
    """
    try:
        from datetime import datetime, timedelta, timezone

        from services.admin import metrics_service

        # "Yesterday" in UTC — the day whose ai_usage / last_active_date
        # data has stopped accumulating by the 00:30 ICT cron tick.
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        snapshot = metrics_service.aggregate_daily(yesterday)
        logger.info(
            "platform_metrics aggregated date=%s dau=%s signups=%s ai_calls=%s",
            yesterday, snapshot["dau"], snapshot["signups"], snapshot["ai_calls"],
        )
    except Exception as e:  # noqa: BLE001 — swallowed so cron doesn't crash
        logger.exception(f"Failed to aggregate platform_metrics: {e}")


def setup_metrics_schedule():
    """Register the daily metrics aggregation cron (US-M11.5).

    Fires at 00:30 Asia/Ho_Chi_Minh — late enough that the previous UTC
    day's tail of activity has settled, early enough that admins see
    yesterday's numbers when they open the dashboard.
    """
    scheduler = get_scheduler()
    job_id = "aggregate_platform_metrics_daily"

    existing = scheduler.get_job(job_id)
    if existing:
        existing.remove()

    scheduler.add_job(
        aggregate_platform_metrics_daily,
        "cron",
        hour=0, minute=30,
        id=job_id,
        replace_existing=True,
    )
    logger.info("Platform metrics aggregation scheduled at 00:30 ICT")


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
    """Restore all group schedules from Firebase on bot startup.

    Also restores pending challenge expiry jobs for active challenges.
    """
    try:
        groups = firebase_service.get_all_groups()
        for group in groups:
            group_id = int(group["id"])
            daily_time = group.get("daily_time", config.DEFAULT_DAILY_TIME)
            challenge_time = group.get("challenge_time", config.DEFAULT_CHALLENGE_TIME)
            setup_group_schedule(bot, group_id, daily_time, challenge_time)
        logger.info(f"Restored schedules for {len(groups)} groups")
    except Exception as e:
        logger.error(f"Failed to restore group schedules: {e}")

    # Restore pending challenge expiry jobs
    try:
        active_challenges = firebase_service.get_active_challenges()
        for ch in active_challenges:
            group_id = int(ch["group_id"])
            date_str = ch["date_str"]
            expires_at = ch.get("expires_at")
            if expires_at:
                schedule_challenge_expiry(bot, group_id, date_str, expires_at)
        if active_challenges:
            logger.info(f"Restored {len(active_challenges)} challenge expiry jobs")
    except Exception as e:
        logger.error(f"Failed to restore challenge expiry jobs: {e}")


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
