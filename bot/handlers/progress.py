import logging
from telegram import Update
from telegram.ext import ContextTypes

from services import firebase_service
from services.srs_service import get_word_strength

logger = logging.getLogger(__name__)


def _estimate_band(total_words: int, accuracy: float) -> str:
    """Rough estimate of vocabulary band level."""
    if total_words >= 300 and accuracy >= 85:
        return "7.5 - 8.0"
    elif total_words >= 200 and accuracy >= 75:
        return "7.0 - 7.5"
    elif total_words >= 150 and accuracy >= 65:
        return "6.5 - 7.0"
    elif total_words >= 100 and accuracy >= 55:
        return "6.0 - 6.5"
    elif total_words >= 50:
        return "5.5 - 6.0"
    else:
        return "Keep learning!"


async def progress_command(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    """Handle /progress — personal stats dashboard (DM only)."""
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        await update.message.reply_text(
            "DM me for your personal stats! \U0001f4ac"
        )
        return

    user_data = firebase_service.get_user(user.id)
    if not user_data:
        await update.message.reply_text("Please /start in the group first!")
        return

    # Get quiz stats
    stats = firebase_service.get_quiz_stats(user.id)

    # Get word strength breakdown
    words = firebase_service.get_user_vocabulary(user.id, limit=500)
    strength_counts = {"New": 0, "Weak": 0, "Learning": 0,
                       "Good": 0, "Mastered": 0}
    for w in words:
        s = get_word_strength(w)
        strength_counts[s] = strength_counts.get(s, 0) + 1

    # Get due words count
    due = firebase_service.get_due_words(user.id, limit=100)

    total_words = user_data.get("total_words", 0)
    accuracy = stats["accuracy"]
    est_band = _estimate_band(total_words, accuracy)

    text = (
        f"\U0001f4ca *Your IELTS Progress*\n\n"
        f"\U0001f3af Target Band: *{user_data.get('target_band', 7.0)}*\n"
        f"\U0001f4c8 Estimated Level: *{est_band}*\n\n"
        f"\U0001f4d6 *Vocabulary*\n"
        f"  Total words: *{total_words}*\n"
        f"  \U0001f195 New: {strength_counts['New']}\n"
        f"  \U0001f534 Weak: {strength_counts['Weak']}\n"
        f"  \U0001f7e1 Learning: {strength_counts['Learning']}\n"
        f"  \U0001f7e2 Good: {strength_counts['Good']}\n"
        f"  \u2b50 Mastered: {strength_counts['Mastered']}\n"
        f"  \U0001f504 Due for review: *{len(due)}*\n\n"
        f"\u2753 *Quizzes*\n"
        f"  Total answered: *{stats['total']}*\n"
        f"  Correct: *{stats['correct']}*\n"
        f"  Accuracy: *{accuracy}%*\n\n"
        f"\U0001f525 *Streak*: {user_data.get('streak', 0)} days\n"
        f"\u26a1 *Challenge Wins*: {user_data.get('challenge_wins', 0)}\n\n"
        f"_Keep going! Consistency is key to IELTS success!_ \U0001f4aa"
    )

    await update.message.reply_text(text, parse_mode="Markdown")
