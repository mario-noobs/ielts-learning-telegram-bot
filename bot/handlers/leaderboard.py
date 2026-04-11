import logging
from telegram import Update
from telegram.ext import ContextTypes

from services import firebase_service
from services.leaderboard_service import format_leaderboard
from bot.utils import safe_send

logger = logging.getLogger(__name__)


async def leaderboard_command(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Handle /leaderboard — show group rankings."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type in ("group", "supergroup"):
        group_id = chat.id
    else:
        user_data = firebase_service.get_user(user.id)
        group_id = user_data.get("group_id") if user_data else None

    if not group_id:
        await update.message.reply_text("No group found. Join a group first.")
        return

    leaderboard = format_leaderboard(group_id)
    await safe_send(update.message, leaderboard)
