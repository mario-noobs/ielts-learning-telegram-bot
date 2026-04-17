import logging
import random
import time as _time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.utils import rate_limit_message
from services import firebase_service, quiz_service
from services.ai_service import RateLimitError

logger = logging.getLogger(__name__)

QUIZ_TOTAL = 5


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /quiz — start a 5-question quiz session (DM only)."""
    message = update.message or update.effective_message
    if not message:
        return
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        await message.reply_text("DM me for quiz sessions! \U0001f4ac")
        return

    if not firebase_service.get_user(user.id):
        await message.reply_text("Please /start first!")
        return

    from services.rate_limit_service import check_rate_limit
    allowed, limit_msg = check_rate_limit(user.id, "quiz")
    if not allowed:
        await message.reply_text(limit_msg)
        return

    # Check if already in a session (auto-expire after 10 minutes)
    session_key = f"quiz_session_{chat.id}_{user.id}"
    existing_session = context.bot_data.get(session_key)
    if existing_session:
        if _time.time() - existing_session.get("created_at", 0) > 600:
            context.bot_data.pop(session_key, None)
            context.bot_data.pop(f"quiz_{chat.id}_{user.id}", None)
        else:
            await message.reply_text("You have an active quiz! Finish it first.")
            return

    await message.reply_text(
        f"\u23f3 Generating {QUIZ_TOTAL} questions..."
    )

    # Generate all questions in a single AI call
    types = ["multiple_choice"] * 3 + ["fill_blank"] * 2
    random.shuffle(types)

    try:
        questions = await quiz_service.generate_quiz_batch(
            user.id, count=QUIZ_TOTAL, types=types
        )
        if not questions:
            await message.reply_text(
                "Not enough vocabulary. Use /daily first."
            )
            return

        context.bot_data[session_key] = {
            "questions": questions,
            "index": 0,
            "correct": 0,
            "total": len(questions),
            "created_at": _time.time(),
        }

        await message.reply_text(
            f"Quiz time! {len(questions)} questions (MC + Fill in blank)\n"
            f"Let's go!"
        )
        await _send_next_quiz(update, context, chat.id, user)

    except RateLimitError as e:
        await message.reply_text(rate_limit_message(e))
    except Exception as e:
        logger.error(f"Quiz batch generation failed: {e}")
        await message.reply_text(
            "\u274c Failed to generate quiz. Please try again."
        )


async def _send_next_quiz(update, context, chat_id, user):
    """Send the next pre-generated quiz question."""
    session_key = f"quiz_session_{chat_id}_{user.id}"
    session = context.bot_data.get(session_key)
    if not session:
        return

    idx = session["index"]
    total = session["total"]

    # Session complete
    if idx >= total:
        correct = session["correct"]
        context.bot_data.pop(session_key, None)
        context.bot_data.pop(f"quiz_{chat_id}_{user.id}", None)

        pct = round(correct / total * 100)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Quiz done! {user.first_name}: {correct}/{total} ({pct}%)\n"
                 f"{'Great job!' if pct >= 60 else 'Keep practicing!'}"
        )
        return

    question = session["questions"][idx]

    # Store current question for answer callbacks
    q_key = f"quiz_{chat_id}_{user.id}"
    context.bot_data[q_key] = question

    formatted = quiz_service.format_question(question, idx + 1)
    header = f"[{idx + 1}/{total}] "

    # All question types use inline buttons
    options = question.get("options", [])
    keyboard = []
    for i, opt in enumerate(options):
        label = chr(65 + i)
        keyboard.append([InlineKeyboardButton(
            f"{label}. {opt}",
            callback_data=f"quiz_{label}_{user.id}"
        )])

    await context.bot.send_message(
        chat_id=chat_id,
        text=header + formatted,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def quiz_answer_callback(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz MC answer button press."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")  # quiz_A_12345
    if len(parts) != 3:
        return

    answer_letter = parts[1]
    target_user_id = int(parts[2])
    answering_user = query.from_user

    # Only target user can answer
    if answering_user.id != target_user_id:
        return

    chat = update.effective_chat
    q_key = f"quiz_{chat.id}_{target_user_id}"
    question = context.bot_data.get(q_key)

    if not question:
        await query.edit_message_text("Quiz expired.")
        return

    is_correct, feedback = await quiz_service.check_answer(
        question, answer_letter, answering_user.id
    )

    result = f"{answering_user.first_name}: {answer_letter}\n\n{feedback}"
    await query.edit_message_text(result)

    # Clean up question
    context.bot_data.pop(q_key, None)

    # Advance session
    session_key = f"quiz_session_{chat.id}_{answering_user.id}"
    session = context.bot_data.get(session_key)
    if session:
        if is_correct:
            session["correct"] += 1
        session["index"] += 1
        await _send_next_quiz(update, context, chat.id, answering_user)


async def quiz_text_answer(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    """Handle text answers for fill-blank."""
    if not update.message:
        return
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text

    q_key = f"quiz_{chat.id}_{user.id}"
    question = context.bot_data.get(q_key)

    if not question:
        return

    if question["type"] not in ("fill_blank", "paraphrase"):
        return

    is_correct, feedback = await quiz_service.check_answer(
        question, text, user.id
    )

    await update.message.reply_text(feedback)

    # Clean up question
    context.bot_data.pop(q_key, None)

    # Advance session
    session_key = f"quiz_session_{chat.id}_{user.id}"
    session = context.bot_data.get(session_key)
    if session:
        if is_correct:
            session["correct"] += 1
        session["index"] += 1
        await _send_next_quiz(update, context, chat.id, user)
