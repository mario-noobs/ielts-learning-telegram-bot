"""Bot ``/unlink`` command — detach Firebase Auth from this Telegram account.

Vietnamese-first text per project convention (bot stays VN-first per
CLAUDE.md). Idempotent: if the user isn't linked, replies a "chưa liên kết"
message instead of erroring.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services import firebase_service

logger = logging.getLogger(__name__)


async def unlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not user:
        return

    if chat and chat.type != "private":
        await message.reply_text("Dùng lệnh /unlink trong tin nhắn riêng với bot.")
        return

    try:
        unlinked = firebase_service.unlink_telegram(user.id, surface="bot")
    except Exception:
        logger.exception("Failed to unlink telegram user %s", user.id)
        await message.reply_text("Không huỷ liên kết được lúc này, thử lại sau.")
        return

    if unlinked:
        await message.reply_text(
            "Đã huỷ liên kết tài khoản web. Dữ liệu Telegram của bạn vẫn còn nguyên.",
        )
    else:
        await message.reply_text("Bạn chưa liên kết với tài khoản web nào.")
