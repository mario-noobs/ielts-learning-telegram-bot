import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services import ai_service, firebase_service
from services.ai_service import RateLimitError
from bot.utils import safe_send, rate_limit_message

logger = logging.getLogger(__name__)


async def write_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /write <text> — get AI writing feedback (DM only)."""
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        await update.message.reply_text("DM me for writing feedback! \U0001f4ac")
        return

    user_data = firebase_service.get_user(user.id)
    if not user_data:
        await update.message.reply_text("Please /start in the group first!")
        return

    if not context.args:
        await update.message.reply_text(
            "\u270d\ufe0f *Writing Feedback*\n\n"
            "Send me your text and I'll give you IELTS-style feedback!\n\n"
            "Usage: `/write Your text here...`\n\n"
            "Examples:\n"
            "  `/write The environment is very important for our future`\n"
            "  `/write In many countries, people are living longer. "
            "Discuss the causes and effects.`",
            parse_mode="Markdown"
        )
        return

    text = " ".join(context.args)
    band = user_data.get("target_band", 7.0)

    await update.message.reply_text(
        "\U0001f4dd Analyzing your writing...",
    )

    try:
        feedback = await ai_service.get_writing_feedback(text, band)

        # Save to history
        firebase_service.save_writing(user.id, {
            "original_text": text,
            "language": "en",
            "feedback": feedback,
            "shared_to_group": False,
        })

        await safe_send(update.message, feedback)

        # Store last writing for sharing
        context.user_data["last_writing"] = {
            "text": text,
            "feedback": feedback,
        }

        # Offer to share if in DM
        if chat.type == "private" and user_data.get("group_id"):
            keyboard = [[InlineKeyboardButton(
                "Share to group", callback_data="share_writing"
            )]]
            await update.message.reply_text(
                "Want to share this in the group for others to learn?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    except RateLimitError as e:
        await update.message.reply_text(rate_limit_message(e))
    except Exception as e:
        logger.error(f"Writing feedback failed: {e}")
        await update.message.reply_text(
            "\u274c Failed to analyze your writing. Please try again."
        )


async def translate_command(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    """Handle /translate <text> — translate between EN and VI (DM only)."""
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        await update.message.reply_text("DM me for translations! \U0001f4ac")
        return

    user_data = firebase_service.get_user(user.id)
    if not user_data:
        await update.message.reply_text("Please /start in the group first!")
        return

    if not context.args:
        await update.message.reply_text(
            "\U0001f310 *Translation*\n\n"
            "I auto-detect the language and translate!\n\n"
            "Usage: `/translate Your text here`\n\n"
            "Examples:\n"
            "  `/translate Toi muon hoc tieng Anh`\n"
            "  `/translate The impact of technology on education`",
            parse_mode="Markdown"
        )
        return

    text = " ".join(context.args)
    band = user_data.get("target_band", 7.0)

    await update.message.reply_text("\U0001f310 Translating...")

    try:
        result = await ai_service.translate_text(text, band)

        # Save to history
        firebase_service.save_writing(user.id, {
            "original_text": text,
            "language": "auto",
            "feedback": result,
            "shared_to_group": False,
        })

        await safe_send(update.message, result)

        # Store last translation for sharing
        context.user_data["last_translation"] = {
            "text": text,
            "result": result,
        }

        if update.effective_chat.type == "private" and user_data.get("group_id"):
            keyboard = [[InlineKeyboardButton(
                "Share to group", callback_data="share_translation"
            )]]
            await update.message.reply_text(
                "Want to share this in the group?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    except RateLimitError as e:
        await update.message.reply_text(rate_limit_message(e))
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        await update.message.reply_text(
            "\u274c Translation failed. Please try again."
        )


async def share_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle share to group button."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    user_data = firebase_service.get_user(user.id)
    group_id = user_data.get("group_id") if user_data else None

    if not group_id:
        await query.edit_message_text("No group found. Join a group first.")
        return

    try:
        if query.data == "share_writing":
            data = context.user_data.get("last_writing")
            if not data:
                await query.edit_message_text("Nothing to share.")
                return

            share_text = (
                f"\u270d\ufe0f {user.first_name} shared their writing:\n\n"
                f"\"{data['text']}\"\n\n"
                f"Feedback:\n{data['feedback']}"
            )
            await context.bot.send_message(chat_id=group_id, text=share_text[:4000])
            await query.edit_message_text("Shared to group!")

        elif query.data == "share_translation":
            data = context.user_data.get("last_translation")
            if not data:
                await query.edit_message_text("Nothing to share.")
                return

            share_text = (
                f"\U0001f310 {user.first_name} shared a translation:\n\n"
                f"\"{data['text']}\"\n\n"
                f"{data['result']}"
            )
            await context.bot.send_message(chat_id=group_id, text=share_text[:4000])
            await query.edit_message_text("Shared to group!")

    except Exception as e:
        logger.error(f"Share failed: {e}")
        await query.edit_message_text(
            "Failed to share. Make sure the bot is still in the group and try /start in the group again."
        )
