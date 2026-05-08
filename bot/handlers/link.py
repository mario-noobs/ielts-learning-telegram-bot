"""Bot ``/link`` command — return a 1-click web URL (US-M12.2).

Replaces the 6-digit code paste flow. Bot mints a token via
``create_link_token_for_telegram`` and replies with the deep-link URL
``${WEB_BASE_URL}/link?token=<token>``. Web side handles redemption
through ``POST /api/v1/link/redeem``.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services import firebase_service

logger = logging.getLogger(__name__)


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not user:
        return

    if chat and chat.type != "private":
        await message.reply_text("Dùng lệnh /link trong tin nhắn riêng với bot.")
        return

    if not firebase_service.get_user(user.id):
        await message.reply_text("Gõ /start trước để đăng ký hồ sơ nhé.")
        return

    try:
        result = firebase_service.create_link_token_for_telegram(user.id)
    except Exception:
        logger.exception("Failed to mint link token for tg user %s", user.id)
        await message.reply_text("Không tạo được link lúc này, thử lại sau.")
        return

    await message.reply_text(
        "🔗 Liên kết web cho bạn\n\n"
        "Nhấn link bên dưới để mở web và liên kết tự động "
        "(hết hạn sau 15 phút):\n\n"
        f"{result['url']}\n\n"
        "Hoặc copy paste vào trình duyệt nếu link không tự mở.",
        disable_web_page_preview=False,
    )
