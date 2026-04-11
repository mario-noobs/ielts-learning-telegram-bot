import logging
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services import firebase_service, challenge_service
from services.ai_service import RateLimitError
from bot.utils import safe_send, rate_limit_message
import config

logger = logging.getLogger(__name__)


async def challenge_command(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    """Handle /challenge — start daily challenge, one question at a time."""
    user = update.effective_user
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "Daily challenges are for group chats!"
        )
        return

    if not firebase_service.get_user(user.id):
        await update.message.reply_text("Please /start first!")
        return

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Load or generate challenge
    challenge_key = f"challenge_{chat.id}_{date_str}"
    challenge_data = context.bot_data.get(challenge_key)

    if not challenge_data:
        existing = firebase_service.get_challenge(chat.id, date_str)
        if existing and existing.get("questions"):
            questions = existing["questions"]
        else:
            await update.message.reply_text(
                "\u26a1 Generating today's challenge..."
            )
            try:
                questions, date_str = await challenge_service.create_daily_challenge(
                    chat.id
                )
            except RateLimitError as e:
                await update.message.reply_text(rate_limit_message(e))
                return
            except Exception as e:
                logger.error(f"Challenge generation failed: {e}")
                await update.message.reply_text(
                    "Failed to generate challenge. Try again later."
                )
                return

        context.bot_data[challenge_key] = {
            "questions": questions,
            "scores": {},
        }
        challenge_data = context.bot_data[challenge_key]

    # Check if this user already completed
    user_key = str(user.id)
    user_scores = challenge_data["scores"].get(user_key, {})
    total_q = len(challenge_data["questions"])

    if len(user_scores) >= total_q:
        score = sum(1 for v in user_scores.values() if v)
        await update.message.reply_text(
            f"You already finished today's challenge!\n"
            f"Your score: {score}/{total_q}\n\n"
            f"Use /results to see the leaderboard."
        )
        return

    # Send intro if starting fresh
    if not user_scores:
        await update.message.reply_text(
            f"\u26a1 Daily Challenge - {date_str}\n\n"
            f"{total_q} questions. Answer one by one.\n"
            f"Let's go, {user.first_name}!"
        )

    # Send next unanswered question
    await _send_next_challenge_question(update, context, chat.id, user, date_str)


async def _send_next_challenge_question(update, context, chat_id, user, date_str):
    """Send the next unanswered question to the user."""
    challenge_key = f"challenge_{chat_id}_{date_str}"
    challenge_data = context.bot_data.get(challenge_key)
    if not challenge_data:
        return

    questions = challenge_data["questions"]
    user_key = str(user.id)
    user_scores = challenge_data["scores"].get(user_key, {})

    # Find next unanswered question
    q_idx = len(user_scores)
    if q_idx >= len(questions):
        # All done
        score = sum(1 for v in user_scores.values() if v)
        firebase_service.update_challenge_score(
            chat_id, date_str, user.id, score
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"\U0001f3c1 {user.first_name} finished! Score: {score}/{len(questions)}\n"
                 f"Use /results to see rankings."
        )
        return

    q = questions[q_idx]
    q_type = q.get("type", "multiple_choice")
    question_text = q.get("question", "")
    q_num = q_idx + 1
    total = len(questions)

    # Build options for all question types
    if q_type == "fill_blank":
        # Generate button options: correct word + 3 distractors from other questions
        correct_word = q.get("answer", "")
        other_words = []
        for other_q in questions:
            w = other_q.get("word", "")
            if w and w != correct_word:
                other_words.append(w)
        # Pad with generic distractors if not enough
        while len(other_words) < 3:
            other_words.append(f"option_{len(other_words)}")
        distractors = random.sample(other_words, min(3, len(other_words)))
        options = [correct_word] + distractors
        random.shuffle(options)
        q["_shuffled_options"] = options
        q["_shuffled_correct"] = options.index(correct_word)

        text = f"Q{q_num}/{total}  Fill in the blank:\n\n{question_text}\n"
    else:
        # MC / synonym_antonym
        options = q.get("options", [])
        correct_idx = q.get("correct_index", 0)
        correct_answer = options[correct_idx] if correct_idx < len(options) else options[0]
        shuffled = list(options)
        random.shuffle(shuffled)
        q["_shuffled_options"] = shuffled
        q["_shuffled_correct"] = shuffled.index(correct_answer)

        text = f"Q{q_num}/{total}  {question_text}\n"
        options = shuffled

    # Build inline buttons
    keyboard = []
    for i, opt in enumerate(options if q_type == "fill_blank" else q["_shuffled_options"]):
        label = chr(65 + i)
        text += f"\n{label}. {opt}"
        keyboard.append([InlineKeyboardButton(
            f"{label}. {opt}",
            callback_data=f"ch_{date_str}_{q_idx}_{label}_{user.id}"
        )])

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def challenge_answer_callback(update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
    """Handle challenge MC answer button press."""
    query = update.callback_query
    user = query.from_user
    chat = update.effective_chat

    # ch_2026-04-11_0_A_12345
    parts = query.data.split("_")
    if len(parts) != 5:
        await query.answer("Invalid.")
        return

    date_str = parts[1]
    q_idx = int(parts[2])
    answer_letter = parts[3]
    target_user_id = int(parts[4])

    # Only the target user can answer
    if user.id != target_user_id:
        await query.answer("This question is not for you!")
        return

    challenge_key = f"challenge_{chat.id}_{date_str}"
    challenge_data = context.bot_data.get(challenge_key)
    if not challenge_data:
        await query.answer("Challenge expired.")
        return

    questions = challenge_data["questions"]
    if q_idx >= len(questions):
        await query.answer("Invalid question.")
        return

    user_key = str(user.id)
    if user_key not in challenge_data["scores"]:
        challenge_data["scores"][user_key] = {}

    # Prevent double answer
    if str(q_idx) in challenge_data["scores"][user_key]:
        await query.answer("Already answered!")
        return

    q = questions[q_idx]
    answer_idx = ord(answer_letter) - ord("A")

    # Use shuffled correct index
    correct_idx = q.get("_shuffled_correct", q.get("correct_index", 0))
    shuffled_options = q.get("_shuffled_options", q.get("options", []))
    correct_letter = chr(65 + correct_idx)
    correct_text = shuffled_options[correct_idx] if correct_idx < len(shuffled_options) else "?"

    is_correct = answer_idx == correct_idx
    challenge_data["scores"][user_key][str(q_idx)] = is_correct

    explanation = q.get("explanation", "")

    if is_correct:
        result = f"\u2705 Correct!\n{explanation}"
    else:
        result = f"\u274c Wrong! Answer: {correct_letter}. {correct_text}\n{explanation}"

    await query.answer()
    await query.edit_message_text(
        query.message.text + f"\n\n{user.first_name}: {result}"
    )

    # Send next question
    await _send_next_challenge_question(update, context, chat.id, user, date_str)


async def challenge_results_command(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    """Handle /results — show challenge results."""
    chat = update.effective_chat
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    results = challenge_service.format_challenge_results(chat.id, date_str)
    await update.message.reply_text(results)
