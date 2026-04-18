import logging
import secrets

from telegram import Update
from telegram.ext import ContextTypes

from services import firebase_service

logger = logging.getLogger(__name__)


def _generate_code() -> str:
    for _ in range(10):
        code = f"{secrets.randbelow(900000) + 100000}"
        if not firebase_service.get_link_code(code):
            return code
    raise RuntimeError("Could not allocate unique link code")


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
        code = _generate_code()
    except Exception:
        logger.exception("Failed to allocate link code")
        await message.reply_text("Không tạo được mã lúc này, thử lại sau.")
        return

    firebase_service.create_link_code(code, user.id)
    await message.reply_text(
        f"Mã liên kết của bạn:\n\n<code>{code}</code>\n\n"
        "Nhập mã này vào trang web trong 5 phút để đồng bộ từ vựng.",
        parse_mode="HTML",
    )
