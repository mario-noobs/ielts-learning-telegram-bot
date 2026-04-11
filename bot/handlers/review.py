import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services import firebase_service, quiz_service
from services.srs_service import get_word_strength, get_strength_emoji
from bot.utils import safe_send

logger = logging.getLogger(__name__)


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /review — SRS review of due words (DM only)."""
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        await update.message.reply_text(
            "DM me for review sessions! \U0001f4ac"
        )
        return

    user_data = firebase_service.get_user(user.id)
    if not user_data:
        await update.message.reply_text("Please /start first!")
        return

    # Get due words
    due_words = firebase_service.get_due_words(user.id, limit=10)

    if not due_words:
        await update.message.reply_text(
            "\u2705 *No words due for review!*\n\n"
            "All caught up! Check back later or wait for new daily vocab.",
            parse_mode="Markdown"
        )
        return

    # Store review session
    context.user_data["review_words"] = due_words
    context.user_data["review_index"] = 0
    context.user_data["review_correct"] = 0
    context.user_data["review_total"] = len(due_words)

    await update.message.reply_text(
        f"\U0001f504 *Review Session*\n\n"
        f"You have *{len(due_words)}* words to review.\n"
        f"Let's go!\n",
        parse_mode="Markdown"
    )

    # Send first question
    await _send_review_question(update, context)


async def _send_review_question(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    """Send the next review question."""
    words = context.user_data.get("review_words", [])
    idx = context.user_data.get("review_index", 0)

    if idx >= len(words):
        # Review complete
        correct = context.user_data.get("review_correct", 0)
        total = context.user_data.get("review_total", 0)
        pct = round(correct / total * 100) if total > 0 else 0

        await update.effective_chat.send_message(
            f"\U0001f389 *Review Complete!*\n\n"
            f"Score: *{correct}/{total}* ({pct}%)\n"
            f"{'Great job!' if pct >= 70 else 'Keep practicing!'}\n\n"
            f"Use /review again later for more practice.",
            parse_mode="Markdown"
        )
        # Clean up
        for key in ("review_words", "review_index",
                     "review_correct", "review_total"):
            context.user_data.pop(key, None)
        return

    word_data = words[idx]
    strength = get_word_strength(word_data)
    emoji = get_strength_emoji(strength)

    # Generate a quiz question for this word
    try:
        question = await quiz_service.generate_quiz_question.__wrapped__(
            word_data
        ) if False else None
    except Exception:
        question = None

    # Fallback: generate directly
    if not question:
        from services import ai_service
        import random
        quiz_type = random.choice(["multiple_choice", "synonym_antonym"])
        question = await ai_service.generate_quiz(
            word=word_data["word"],
            definition=word_data.get("definition", ""),
            quiz_type=quiz_type,
        )
        question["word_id"] = word_data["id"]

    question = quiz_service.shuffle_options(question)

    # Store current question
    context.user_data["review_current"] = question

    progress = f"[{idx + 1}/{len(words)}]"
    formatted = quiz_service.format_question(question, idx + 1)
    header = f"{emoji} {progress} _{strength}_ word\n\n"

    if question.get("type") in ("multiple_choice", "synonym_antonym"):
        options = question.get("options", [])
        keyboard = []
        row = []
        for i, opt in enumerate(options):
            label = chr(65 + i)
            row.append(InlineKeyboardButton(
                label, callback_data=f"review_{label}"
            ))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        await update.effective_chat.send_message(
            header + formatted,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.effective_chat.send_message(
            header + formatted, parse_mode="Markdown"
        )


async def review_answer_callback(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    """Handle review answer button press."""
    query = update.callback_query
    await query.answer()

    answer = query.data.replace("review_", "")
    question = context.user_data.get("review_current")

    if not question:
        await query.edit_message_text("Review session expired. Use /review.")
        return

    user = query.from_user
    is_correct, feedback = await quiz_service.check_answer(
        question, answer, user.id
    )

    if is_correct:
        context.user_data["review_correct"] = (
            context.user_data.get("review_correct", 0) + 1
        )

    context.user_data["review_index"] = (
        context.user_data.get("review_index", 0) + 1
    )

    try:
        await query.edit_message_text(feedback, parse_mode="Markdown")
    except Exception:
        from bot.utils import strip_markdown
        await query.edit_message_text(strip_markdown(feedback))

    # Send next question
    await _send_review_question(update, context)


async def review_text_answer(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Handle text answer during review (fill-blank, paraphrase)."""
    if update.effective_chat.type != "private":
        return

    question = context.user_data.get("review_current")
    if not question:
        return
    if question.get("type") not in ("fill_blank", "paraphrase"):
        return

    user = update.effective_user
    text = update.message.text

    is_correct, feedback = await quiz_service.check_answer(
        question, text, user.id
    )

    if is_correct:
        context.user_data["review_correct"] = (
            context.user_data.get("review_correct", 0) + 1
        )

    context.user_data["review_index"] = (
        context.user_data.get("review_index", 0) + 1
    )

    await safe_send(update.message, feedback)

    # Send next question
    await _send_review_question(update, context)
