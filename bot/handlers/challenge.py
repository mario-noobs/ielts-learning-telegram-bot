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


async def _get_bot_username(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Get bot username, cached in bot_data to avoid repeated API calls."""
    if "bot_username" not in context.bot_data:
        me = await context.bot.get_me()
        context.bot_data["bot_username"] = me.username
    return context.bot_data["bot_username"]


async def challenge_command(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    """Handle /challenge in group — show status or generate today's challenge."""
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "Daily challenges are for group chats!\n"
            "Use the deep-link button in your group to start."
        )
        return

    user = update.effective_user
    if not firebase_service.get_user(user.id):
        await update.message.reply_text("Please /start first!")
        return

    date_str = config.local_date_str()
    challenge = firebase_service.get_challenge(chat.id, date_str)

    if challenge and challenge.get("questions"):
        # Challenge exists — show status with deep-link button
        if challenge.get("status") == "closed":
            results = challenge_service.format_challenge_results(chat.id, date_str)
            await update.message.reply_text(results, parse_mode="Markdown")
            return

        if challenge_service.is_challenge_expired(challenge):
            # Expired but not closed — close it and show results
            result = challenge_service.close_and_score(chat.id, date_str)
            if result:
                text = challenge_service._build_results_text(result, date_str)
                await update.message.reply_text(text, parse_mode="Markdown")
            else:
                await update.message.reply_text("Challenge has ended.")
            return

        # Still active — show deep-link button
        bot_username = await _get_bot_username(context)
        text, markup = challenge_service.format_challenge_post(
            date_str, bot_username, chat.id
        )
        await update.message.reply_text(
            text, reply_markup=markup, parse_mode="Markdown"
        )
        return

    # No challenge yet — generate one
    await update.message.reply_text("\u26a1 Generating today's challenge...")
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

    # Post the announcement with deep-link
    bot_username = await _get_bot_username(context)
    group = firebase_service.get_group_settings(chat.id)
    topic = None
    band = None
    if group:
        topic = random.choice(group.get("topics", ["education"]))
        band = group.get("default_band", 7.0)

    text, markup = challenge_service.format_challenge_post(
        date_str, bot_username, chat.id, topic=topic, band=band
    )
    await update.message.reply_text(
        text, reply_markup=markup, parse_mode="Markdown"
    )

    # Schedule expiry job
    from services.scheduler_service import schedule_challenge_expiry
    challenge_data = firebase_service.get_challenge(chat.id, date_str)
    if challenge_data:
        expires_at = challenge_data.get("expires_at")
        if expires_at:
            schedule_challenge_expiry(
                context.bot, int(chat.id), date_str, expires_at
            )


async def start_challenge_dm(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              group_id: int, date_str: str):
    """Begin or resume a challenge in DM after deep-link tap.

    Called from the /start handler when payload matches challenge_*.
    """
    user = update.effective_user

    if not firebase_service.get_user(user.id):
        await update.message.reply_text(
            "Please /start first in the group to create your profile!"
        )
        return

    challenge = firebase_service.get_challenge(group_id, date_str)
    if not challenge:
        await update.message.reply_text("This challenge doesn't exist.")
        return

    if challenge.get("status") == "closed":
        await update.message.reply_text(
            "This challenge has already ended.\n"
            "Use /results in the group to see the leaderboard."
        )
        return

    if challenge_service.is_challenge_expired(challenge):
        await update.message.reply_text(
            "\u23f0 Time's up! This challenge has expired.\n"
            "Use /results in the group to see the leaderboard."
        )
        return

    questions = challenge.get("questions", [])
    total_q = len(questions)

    # Check existing progress
    answers_doc = firebase_service.get_user_challenge_answers(
        group_id, date_str, user.id
    )
    answered_count = 0
    if answers_doc:
        responses = answers_doc.get("responses", {})
        answered_count = len(responses)

    if answered_count >= total_q:
        score = sum(
            1 for v in answers_doc.get("responses", {}).values() if v
        )
        await update.message.reply_text(
            f"You already finished this challenge!\n"
            f"Your score: {score}/{total_q}\n\n"
            f"Use /results in the group to see the leaderboard."
        )
        return

    # Send intro if starting fresh
    if answered_count == 0:
        await update.message.reply_text(
            f"\u26a1 Daily Challenge \u2014 {date_str}\n\n"
            f"{total_q} questions. Answer one by one.\n"
            f"Let's go, {user.first_name}!"
        )

    # Send next question
    await _send_challenge_question_dm(
        context.bot, user, group_id, date_str, questions, answered_count
    )


async def _send_challenge_question_dm(bot, user, group_id, date_str,
                                       questions, q_idx):
    """Send a single challenge question to the user in DM."""
    if q_idx >= len(questions):
        return

    q = questions[q_idx]
    q_type = q.get("type", "multiple_choice")
    question_text = q.get("question", "")
    q_num = q_idx + 1
    total = len(questions)

    # Build options and shuffle
    if q_type == "fill_blank":
        correct_word = q.get("answer", "")
        # Try to use options from the question data first
        if q.get("options"):
            options = list(q["options"])
            if correct_word not in options:
                options[0] = correct_word
        else:
            other_words = []
            for other_q in questions:
                w = other_q.get("word", "")
                if w and w != correct_word:
                    other_words.append(w)
            while len(other_words) < 3:
                other_words.append(f"option_{len(other_words)}")
            distractors = random.sample(other_words, min(3, len(other_words)))
            options = [correct_word] + distractors

        random.shuffle(options)
        correct_idx = options.index(correct_word)
        text = f"Q{q_num}/{total}  Fill in the blank:\n\n{question_text}\n"
    else:
        # MC / synonym_antonym
        options = list(q.get("options", []))
        orig_correct_idx = q.get("correct_index", 0)
        correct_answer = options[orig_correct_idx] if orig_correct_idx < len(options) else options[0]
        random.shuffle(options)
        correct_idx = options.index(correct_answer)
        text = f"Q{q_num}/{total}  {question_text}\n"

    # Build inline buttons — callback_data: ch_{group_id}_{date_str}_{q_idx}_{letter}_{uid}
    keyboard = []
    for i, opt in enumerate(options):
        label = chr(65 + i)
        text += f"\n{label}. {opt}"
        callback_data = f"ch_{group_id}_{date_str}_{q_idx}_{label}_{user.id}"
        keyboard.append([InlineKeyboardButton(
            f"{label}. {opt}",
            callback_data=callback_data
        )])

    # The callback handler re-reads the question from Firestore and derives
    # the correct answer from the original correct_index/answer field,
    # then matches against the chosen option text from the displayed message.
    # No need to persist shuffle order.

    await bot.send_message(
        chat_id=user.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def challenge_answer_callback(update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
    """Handle challenge answer button press in DM.

    callback_data format: ch_{group_id}_{date_str}_{q_idx}_{letter}_{uid}
    """
    query = update.callback_query
    user = query.from_user

    parts = query.data.split("_")
    # ch_{group_id}_{date_str}_{q_idx}_{letter}_{uid}
    # date_str is YYYY-MM-DD which has dashes not underscores, so it's one token
    # Actually let's parse carefully:
    # parts[0] = "ch"
    # parts[1] = group_id (could be negative like -1001234567890)
    # Then date_str = YYYY-MM-DD (contains dashes, no underscores — one token)
    # Then q_idx, letter, uid
    #
    # But negative group_id has a leading minus, e.g. "-1001234567890"
    # split("_") on "ch_-1001234567890_2026-04-13_0_A_12345" gives:
    # ["ch", "-1001234567890", "2026-04-13", "0", "A", "12345"]
    # That's 6 parts. Good.
    if len(parts) != 6:
        await query.answer("Invalid.")
        return

    group_id = int(parts[1])
    date_str = parts[2]
    q_idx = int(parts[3])
    answer_letter = parts[4]
    target_user_id = int(parts[5])

    # Only the target user can answer
    if user.id != target_user_id:
        await query.answer("This question is not for you!")
        return

    # Load challenge from Firestore
    challenge = firebase_service.get_challenge(group_id, date_str)
    if not challenge:
        await query.answer("Challenge not found.")
        return

    if challenge.get("status") == "closed":
        await query.answer("Challenge has ended!")
        return

    if challenge_service.is_challenge_expired(challenge):
        await query.answer("Time's up! Challenge expired.")
        return

    questions = challenge.get("questions", [])
    if q_idx >= len(questions):
        await query.answer("Invalid question.")
        return

    # Check if already answered this question
    answers_doc = firebase_service.get_user_challenge_answers(
        group_id, date_str, user.id
    )
    if answers_doc:
        responses = answers_doc.get("responses", {})
        if str(q_idx) in responses:
            await query.answer("Already answered!")
            return

    # Evaluate the answer
    q = questions[q_idx]
    q_type = q.get("type", "multiple_choice")

    # Find the correct answer text from the original question data
    if q_type == "fill_blank":
        correct_answer_text = q.get("answer", "")
    else:
        opts = q.get("options", [])
        correct_idx = q.get("correct_index", 0)
        correct_answer_text = opts[correct_idx] if correct_idx < len(opts) else ""

    # The user chose a letter (A/B/C/D). We need to figure out which option
    # text that corresponds to. The options are displayed in the message text.
    # Parse the option text from the message.
    answer_idx = ord(answer_letter) - ord("A")
    message_text = query.message.text
    chosen_text = _parse_option_from_message(message_text, answer_letter)

    is_correct = (chosen_text.strip().lower() == correct_answer_text.strip().lower())

    # Persist to Firestore
    firebase_service.save_challenge_answer(group_id, date_str, user.id, q_idx, is_correct)

    explanation = q.get("explanation", "")

    if is_correct:
        result = f"\u2705 Correct!\n{explanation}"
    else:
        # Find the correct letter from the displayed options
        correct_display = _find_correct_letter_in_message(message_text, correct_answer_text)
        result = f"\u274c Wrong! Answer: {correct_display}\n{explanation}"

    await query.answer()
    await query.edit_message_text(
        query.message.text + f"\n\n{user.first_name}: {result}"
    )

    # Check progress — how many answered now
    answers_doc = firebase_service.get_user_challenge_answers(
        group_id, date_str, user.id
    )
    responses = answers_doc.get("responses", {}) if answers_doc else {}
    answered_count = len(responses)
    total_q = len(questions)

    if answered_count >= total_q:
        # All done — compute score and mark complete
        score = sum(1 for v in responses.values() if v)
        firebase_service.mark_challenge_answer_complete(group_id, date_str, user.id)
        firebase_service.update_challenge_score(group_id, date_str, user.id, score)

        await context.bot.send_message(
            chat_id=user.id,
            text=(
                f"\U0001f3c1 *Challenge Complete!*\n\n"
                f"Your score: *{score}/{total_q}*\n\n"
                f"The leaderboard will be posted in the group when the challenge ends."
            ),
            parse_mode="Markdown"
        )
    else:
        # Send next question
        await _send_challenge_question_dm(
            context.bot, user, group_id, date_str, questions, answered_count
        )


def _parse_option_from_message(message_text: str, letter: str) -> str:
    """Extract the option text for a given letter from the displayed message.

    Message format includes lines like:
    A. some option
    B. another option
    """
    for line in message_text.split("\n"):
        line = line.strip()
        if line.startswith(f"{letter}. "):
            return line[3:]  # Skip "X. "
    return ""


def _find_correct_letter_in_message(message_text: str, correct_text: str) -> str:
    """Find which letter label corresponds to the correct answer text."""
    correct_lower = correct_text.strip().lower()
    for line in message_text.split("\n"):
        line = line.strip()
        if len(line) >= 3 and line[1] == "." and line[0] in "ABCD":
            opt_text = line[3:].strip().lower()
            if opt_text == correct_lower:
                return line[:1] + ". " + line[3:].strip()
    return correct_text


async def challenge_results_command(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    """Handle /results — show challenge results in group."""
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "Use /results in a group chat to see challenge results."
        )
        return

    date_str = config.local_date_str()
    results = challenge_service.format_challenge_results(chat.id, date_str)
    await safe_send(update.message, results)
