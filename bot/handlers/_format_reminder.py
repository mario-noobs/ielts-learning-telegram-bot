"""Vietnamese reminder DM formatter (US-M14.3).

The web profile has its preferred locale, but the bot-side voice has
always been Vietnamese (saved memory: bot stays VN-first), so reminders
DM in Vietnamese regardless of `users.preferred_locale`.
"""

from __future__ import annotations


def format_reminder_message(user: dict, due_count: int) -> str:
    """Compose the reminder body for a single user.

    Includes streak, due words, and a CTA. Kept short — Telegram mobile
    notifications truncate beyond ~120 chars.
    """
    name = (user.get("name") or "bạn").strip() or "bạn"
    streak = int(user.get("streak") or 0)
    total_words = int(user.get("total_words") or 0)

    lines = [f"⏰ Đến giờ học rồi, {name}!", ""]

    if streak > 0:
        lines.append(f"🔥 Streak: {streak} ngày — đừng bỏ lỡ hôm nay nhé.")
    else:
        lines.append("🌱 Bắt đầu streak mới — chỉ cần học một chút mỗi ngày.")

    if due_count > 0:
        lines.append(f"📝 Có {due_count} từ đang chờ ôn — gõ /review để giữ nhịp.")
    elif total_words == 0:
        lines.append("🆕 Chưa có từ nào — thử /mydaily để nhận bộ từ đầu tiên.")
    else:
        lines.append(f"⭐ Đã học {total_words} từ. /quiz để tự kiểm tra.")

    lines.extend([
        "",
        "Lệnh nhanh:",
        "  /mydaily — Từ vựng cá nhân",
        "  /quiz — Tự luyện",
        "  /write — Luyện Writing",
    ])

    return "\n".join(lines)
