import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes

from services import ai_service, firebase_service, vocab_service, tts_service
from services.ai_service import RateLimitError
from bot.utils import safe_send, rate_limit_message
import config

logger = logging.getLogger(__name__)


async def _generate_daily(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          force: bool = False):
    """Core logic for daily vocabulary generation."""
    message = update.message or update.effective_message
    if not message:
        return
    chat = update.effective_chat
    user = update.effective_user

    # Ensure user is registered
    if not firebase_service.get_user(user.id):
        await message.reply_text(
            "Please /start first to register your profile!"
        )
        return

    group_id = chat.id if chat.type in ("group", "supergroup") else None

    if not group_id:
        await message.reply_text(
            "This command works in group chats. "
            "Use /review in DM to review your words."
        )
        return

    # Check if already generated today
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = firebase_service.get_daily_words(group_id, date_str)

    if existing and not force:
        # Ensure calling user has the words in their vocab
        user_words = firebase_service.get_user_word_list(user.id)
        if not user_words:
            for word_data in existing["words"]:
                firebase_service.add_word_to_user(user.id,
                    vocab_service._build_word_doc(word_data, existing["topic"]))
            firebase_service.update_user(user.id, {"group_id": group_id})

        messages = vocab_service.format_daily_words(
            existing["words"], existing["topic"]
        )
        for msg in messages:
            await safe_send(message, msg)
        return

    # Generate new words
    await message.reply_text("\u23f3 Generating today's vocabulary...")

    try:
        # Use group settings, not individual user settings
        group = firebase_service.get_group_settings(group_id)
        band = group.get("default_band", config.DEFAULT_BAND_TARGET) if group else config.DEFAULT_BAND_TARGET

        words, topic = await vocab_service.generate_daily_words(
            group_id=group_id,
            count=config.DEFAULT_WORD_COUNT,
            band=band,
        )

        # Save to group and all users
        await vocab_service.save_daily_words_for_group(
            group_id, words, topic, date_str, caller_id=user.id
        )

        messages = vocab_service.format_daily_words(words, topic)
        for msg in messages:
            await safe_send(message, msg)

        # Update streaks for all users
        users = firebase_service.get_all_users_in_group(group_id)
        for u in users:
            firebase_service.update_streak(int(u["id"]))

    except RateLimitError as e:
        await message.reply_text(rate_limit_message(e))
    except Exception as e:
        logger.error(f"Failed to generate daily words: {e}")
        await message.reply_text(
            "\u274c Failed to generate vocabulary. Please try again later."
        )


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /daily — post daily vocabulary in group."""
    await _generate_daily(update, context, force=False)


async def newdaily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /newdaily — force regenerate daily vocabulary."""
    await _generate_daily(update, context, force=True)


async def word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /word <word> — explain a word (DM only)."""
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        await update.message.reply_text("DM me to look up words! \U0001f4ac")
        return

    if not firebase_service.get_user(user.id):
        await update.message.reply_text("Please /start first!")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /word <word>\nExample: /word ubiquitous"
        )
        return

    word = " ".join(context.args)
    user_data = firebase_service.get_user(user.id)
    band = user_data.get("target_band", 7.0)

    await update.message.reply_text(f"\U0001f50d Looking up *{word}*...",
                                     parse_mode="Markdown")

    try:
        explanation = await ai_service.explain_word(word, band)
        await safe_send(update.message, explanation)
    except RateLimitError as e:
        await update.message.reply_text(rate_limit_message(e))
    except Exception as e:
        logger.error(f"Word lookup failed: {e}")
        await update.message.reply_text(
            f"\u274c Failed to look up '{word}'. Please try again."
        )


async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /audio <number> — send pronunciation audio."""
    chat = update.effective_chat

    if not context.args:
        await update.message.reply_text("Usage: /audio <word number>\nExample: /audio 1")
        return

    try:
        idx = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("Please provide a valid number.")
        return

    # Get today's words
    group_id = chat.id if chat.type in ("group", "supergroup") else None
    if not group_id:
        await update.message.reply_text("This command works in group chats.")
        return

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily = firebase_service.get_daily_words(group_id, date_str)

    if not daily:
        await update.message.reply_text("No daily words yet. Use /daily first.")
        return

    words = daily.get("words", [])
    if idx < 0 or idx >= len(words):
        await update.message.reply_text(
            f"Invalid number. Choose 1-{len(words)}."
        )
        return

    word = words[idx].get("word", "")
    example = words[idx].get("example", "")

    # Generate and send audio
    audio_path = tts_service.generate_audio(word)
    if audio_path:
        with open(audio_path, "rb") as f:
            await update.message.reply_voice(
                voice=f,
                caption=f"\U0001f3a7 *{word}* \u2014 {words[idx].get('ipa', '')}",
                parse_mode="Markdown"
            )

    # Also send example sentence audio
    if example:
        sentence_path = tts_service.generate_sentence_audio(example)
        if sentence_path:
            with open(sentence_path, "rb") as f:
                await update.message.reply_voice(
                    voice=f,
                    caption=f'\U0001f4dd _"{example}"_',
                    parse_mode="Markdown"
                )


async def mywords_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mywords — browse personal vocabulary (DM only)."""
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        await update.message.reply_text(
            "DM me to browse your vocabulary! \U0001f4ac"
        )
        return

    user_data = firebase_service.get_user(user.id)
    if not user_data:
        await update.message.reply_text("Please /start in the group first!")
        return

    # Get page from args
    page = 1
    if context.args:
        try:
            page = max(1, int(context.args[0]))
        except ValueError:
            pass

    page_size = 10
    words = firebase_service.get_user_vocabulary(user.id, limit=page_size * page)

    if not words:
        await update.message.reply_text(
            "Your vocabulary is empty. Wait for /daily in the group!"
        )
        return

    # Paginate
    start = (page - 1) * page_size
    page_words = words[start:start + page_size]
    total = len(words)

    from services.srs_service import get_word_strength, get_strength_emoji

    lines = [f"\U0001f4da *Your Vocabulary* (page {page})\n"]
    for i, w in enumerate(page_words, start + 1):
        strength = get_word_strength(w)
        emoji = get_strength_emoji(strength)
        word = w.get("word", "?")
        definition = w.get("definition", "")[:50]
        lines.append(f"{emoji} *{i}. {word}* \u2014 {definition}")

    lines.append(f"\n_Showing {start + 1}-{start + len(page_words)} of {total}_")
    if start + page_size < total:
        lines.append(f"Use /mywords {page + 1} for next page")

    lines.append("\n\U0001f534 Weak  \U0001f7e1 Learning  \U0001f7e2 Good  \u2b50 Mastered")

    await safe_send(update.message, "\n".join(lines))
