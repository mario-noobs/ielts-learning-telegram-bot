import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.utils import safe_send
from services import firebase_service, quiz_service
from services.srs_service import get_strength_emoji, get_word_strength

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

    from services.rate_limit_service import check_rate_limit
    allowed, limit_msg = check_rate_limit(user.id, "review")
    if not allowed:
        await update.message.reply_text(limit_msg)
        return

    # Auto-expire stale review sessions (older than 10 minutes)
    import time as _time
    if context.user_data.get("review_words"):
        if _time.time() - context.user_data.get("review_created_at", 0) > 600:
            for key in ("review_words", "review_questions", "review_index",
                         "review_correct", "review_total", "review_current",
                         "review_created_at"):
                context.user_data.pop(key, None)
        else:
            await update.message.reply_text(
                "You have an active review session! Finish it first."
            )
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

    await update.message.reply_text(
        f"\u23f3 Generating {len(due_words)} review questions..."
    )

    # Generate all review questions in a single AI call
    try:
        from services.ai_service import RateLimitError
        questions = await quiz_service.generate_review_batch(due_words)

        context.user_data["review_words"] = due_words
        context.user_data["review_questions"] = questions
        context.user_data["review_index"] = 0
        context.user_data["review_correct"] = 0
        context.user_data["review_total"] = len(questions)
        context.user_data["review_created_at"] = _time.time()

        await update.message.reply_text(
            f"\U0001f504 *Review Session*\n\n"
            f"You have *{len(questions)}* words to review.\n"
            f"Let's go!\n",
            parse_mode="Markdown"
        )

        # Send first question
        await _send_review_question(update, context)

    except RateLimitError as e:
        from bot.utils import rate_limit_message
        await update.message.reply_text(rate_limit_message(e))
    except Exception as e:
        logger.error(f"Review batch generation failed: {e}")
        await update.message.reply_text(
            "\u274c Failed to generate review questions. Please try again."
        )


async def _send_review_question(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    """Send the next pre-generated review question."""
    words = context.user_data.get("review_words", [])
    questions = context.user_data.get("review_questions", [])
    idx = context.user_data.get("review_index", 0)

    if idx >= len(questions):
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
        for key in ("review_words", "review_questions", "review_index",
                     "review_correct", "review_total", "review_current",
                     "review_created_at"):
            context.user_data.pop(key, None)
        return

    word_data = words[idx] if idx < len(words) else {}
    strength = get_word_strength(word_data)
    emoji = get_strength_emoji(strength)

    question = questions[idx]

    # Store current question for answer callbacks
    context.user_data["review_current"] = question

    progress = f"[{idx + 1}/{len(questions)}]"
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
