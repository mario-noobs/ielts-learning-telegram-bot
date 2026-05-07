import logging

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from bot.handlers.challenge import (
    challenge_answer_callback,
    challenge_command,
    challenge_results_command,
)
from bot.handlers.leaderboard import leaderboard_command
from bot.handlers.link import link_command
from bot.handlers.progress import progress_command
from bot.handlers.quiz import quiz_answer_callback, quiz_command, quiz_text_answer
from bot.handlers.review import review_answer_callback, review_command, review_text_answer
from bot.handlers.settings import (
    groupsettings_command,
    gsave_topics_callback,
    gset_band_callback,
    gset_challenge_time_callback,
    gset_deadline_callback,
    gset_question_count_callback,
    gset_time_callback,
    gset_topic_toggle,
    gset_word_count_callback,
    gsettings_callback,
    save_topics_callback,
    set_band_callback,
    set_time_callback,
    set_topic_toggle,
    settings_callback,
    settings_command,
)
from bot.handlers.start import get_start_handler, help_command
from bot.handlers.vocabulary import (
    audio_command,
    daily_command,
    mydaily_command,
    mywords_command,
    newdaily_command,
    share_mydaily_callback,
    word_command,
)
from bot.handlers.writing import share_callback, translate_command, write_command
from services.scheduler_service import (
    restore_group_schedules,
    setup_greeting_schedule,
    start_scheduler,
    stop_scheduler,
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set! Check your .env file.")
        return

    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connect_timeout=10.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=10.0,
    )
    app = (ApplicationBuilder()
           .token(config.TELEGRAM_BOT_TOKEN)
           .request(request)
           .build())

    # ─── Conversation handler for /start onboarding ────────────
    app.add_handler(get_start_handler())

    # ─── Group commands ────────────────────────────────────────
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("newdaily", newdaily_command))
    app.add_handler(CommandHandler("word", word_command))
    app.add_handler(CommandHandler("audio", audio_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("challenge", challenge_command))
    app.add_handler(CommandHandler("results", challenge_results_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))

    # ─── Private DM commands ──────────────────────────────────
    app.add_handler(CommandHandler("mydaily", mydaily_command))
    app.add_handler(CommandHandler("review", review_command))
    app.add_handler(CommandHandler("write", write_command))
    app.add_handler(CommandHandler("translate", translate_command))
    app.add_handler(CommandHandler("mywords", mywords_command))
    app.add_handler(CommandHandler("progress", progress_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("link", link_command))
    app.add_handler(CommandHandler("groupsettings", groupsettings_command))

    # ─── Callback query handlers ──────────────────────────────
    # Quiz answers (group)
    app.add_handler(CallbackQueryHandler(
        quiz_answer_callback, pattern=r"^quiz_[A-D]_"
    ))
    # Challenge answers
    app.add_handler(CallbackQueryHandler(
        challenge_answer_callback, pattern=r"^ch_"
    ))
    # Review answers (DM)
    app.add_handler(CallbackQueryHandler(
        review_answer_callback, pattern=r"^review_[A-D]$"
    ))
    # Share mydaily to group
    app.add_handler(CallbackQueryHandler(
        share_mydaily_callback, pattern=r"^share_mydaily$"
    ))
    # Share writing/translation to group
    app.add_handler(CallbackQueryHandler(
        share_callback, pattern=r"^share_"
    ))
    # Personal settings (DM)
    app.add_handler(CallbackQueryHandler(
        settings_callback, pattern=r"^settings_"
    ))
    app.add_handler(CallbackQueryHandler(
        set_band_callback, pattern=r"^setband_"
    ))
    app.add_handler(CallbackQueryHandler(
        set_topic_toggle, pattern=r"^settopic_"
    ))
    app.add_handler(CallbackQueryHandler(
        save_topics_callback, pattern=r"^settopics_save$"
    ))
    app.add_handler(CallbackQueryHandler(
        set_time_callback, pattern=r"^settime_"
    ))
    # Group settings
    app.add_handler(CallbackQueryHandler(
        gsettings_callback, pattern=r"^gsettings_"
    ))
    app.add_handler(CallbackQueryHandler(
        gset_band_callback, pattern=r"^gsetband_"
    ))
    app.add_handler(CallbackQueryHandler(
        gset_topic_toggle, pattern=r"^gsettopic_"
    ))
    app.add_handler(CallbackQueryHandler(
        gsave_topics_callback, pattern=r"^gsettopics_save$"
    ))
    app.add_handler(CallbackQueryHandler(
        gset_time_callback, pattern=r"^gsettime_"
    ))
    app.add_handler(CallbackQueryHandler(
        gset_challenge_time_callback, pattern=r"^gsetchtime_"
    ))
    app.add_handler(CallbackQueryHandler(
        gset_word_count_callback, pattern=r"^gsetwc_"
    ))
    app.add_handler(CallbackQueryHandler(
        gset_question_count_callback, pattern=r"^gsetqc_"
    ))
    app.add_handler(CallbackQueryHandler(
        gset_deadline_callback, pattern=r"^gsetdl_"
    ))

    # ─── Text message handlers ──────────────────────────────
    # Review text answers (DM)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        review_text_answer
    ))
    # Quiz text answers (any chat)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        quiz_text_answer
    ))

    # ─── Start scheduler ──────────────────────────────────────
    start_scheduler()
    restore_group_schedules(app.bot)
    setup_greeting_schedule(app.bot)

    # ─── Run bot ──────────────────────────────────────────────
    logger.info("IELTS Bot starting...")
    logger.info("user_repo_cutover_active=postgres")
    app.run_polling(drop_pending_updates=True)

    # Cleanup
    stop_scheduler()


if __name__ == "__main__":
    main()
