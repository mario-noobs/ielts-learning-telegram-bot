import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, ConversationHandler

from services import firebase_service

logger = logging.getLogger(__name__)

# Conversation states
BAND, TOPICS = range(2)

TOPIC_OPTIONS = [
    ("education", "Education"), ("environment", "Environment"),
    ("technology", "Technology"), ("health", "Health"),
    ("society", "Society"), ("economy", "Economy"),
    ("government", "Government"), ("media", "Media"),
    ("science", "Science"), ("travel", "Travel"),
    ("food", "Food"), ("arts", "Arts"),
]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — register user and begin onboarding.

    Also handles deep-link payloads like /start challenge_{group_id}_{date_str}.
    """
    user = update.effective_user
    chat = update.effective_chat

    # Deep-link: challenge payload (must check BEFORE onboarding)
    if context.args and context.args[0].startswith("challenge_"):
        return await _handle_challenge_deeplink(update, context)

    # Deep-link: web→TG link token (US-M12.2). The web app sent the user
    # here via `https://t.me/<bot>?start=link_<token>`; we redeem the
    # token and short-circuit onboarding because the user already chose
    # band + topics on web.
    if context.args and context.args[0].startswith("link_"):
        return await _handle_link_deeplink(update, context)

    # Check if user already exists
    existing = firebase_service.get_user(user.id)
    if existing:
        # Existing user re-running /start. Whether they're in DM or in
        # a group, send the welcome-back card. But if they're running
        # this *in a group*, also re-bind their group_id to that chat
        # — otherwise web `/settings/groups` won't see them as a member
        # (US-#227 / #230 follow-up). Without this, a DM-registered
        # user who joins a group later has group_id=NULL forever.
        in_group = chat.type in ("group", "supergroup")
        joined_msg = ""
        if in_group:
            existing_group = firebase_service.get_group_settings(chat.id)
            if existing_group is None:
                # Group not seen by the bot yet — create it and stamp
                # this user as owner.
                firebase_service.create_group(
                    chat.id, owner_telegram_id=user.id,
                )
            elif existing_group.get("owner_telegram_id") is None:
                # Legacy group with no owner — backfill on first
                # /start by any member.
                firebase_service.update_group_settings(
                    chat.id, {"owner_telegram_id": int(user.id)},
                )
            current_group_id = existing.get("group_id")
            if current_group_id != chat.id:
                firebase_service.update_user(user.id, {"group_id": chat.id})
                joined_msg = "\n\n\U0001f44b *Added you to this group.*"
        await update.message.reply_text(
            f"Welcome back, *{user.first_name}*! \U0001f44b\n\n"
            f"Target Band: *{existing.get('target_band', 7.0)}*\n"
            f"Words learned: *{existing.get('total_words', 0)}*\n"
            f"Streak: *{existing.get('streak', 0)} days*\n\n"
            f"Use /help to see all commands.{joined_msg}",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Ensure group is registered. The first user to /start in a group
    # becomes its owner — stamped on the doc so the web group-edit page
    # (US-#227) can permission-gate PATCH to only that user.
    if chat.type in ("group", "supergroup"):
        group = firebase_service.get_group_settings(chat.id)
        if not group:
            firebase_service.create_group(
                chat.id, owner_telegram_id=update.effective_user.id,
            )

    # Ask for target band
    keyboard = [
        [InlineKeyboardButton("Band 5.5", callback_data="band_5.5"),
         InlineKeyboardButton("Band 6.0", callback_data="band_6.0")],
        [InlineKeyboardButton("Band 6.5", callback_data="band_6.5"),
         InlineKeyboardButton("Band 7.0", callback_data="band_7.0")],
        [InlineKeyboardButton("Band 7.5", callback_data="band_7.5"),
         InlineKeyboardButton("Band 8.0+", callback_data="band_8.0")],
    ]

    await update.message.reply_text(
        f"Welcome to *IELTS Study Bot*, {user.first_name}! \U0001f393\n\n"
        f"Let's set up your profile.\n"
        f"What's your *target IELTS band score*?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return BAND


async def band_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle band selection callback."""
    query = update.callback_query
    await query.answer()

    band = float(query.data.replace("band_", ""))
    context.user_data["target_band"] = band

    # Ask for topic preferences
    keyboard = []
    row = []
    for topic_id, topic_name in TOPIC_OPTIONS:
        row.append(InlineKeyboardButton(
            topic_name, callback_data=f"topic_{topic_id}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(
        "\u2705 Done selecting", callback_data="topics_done"
    )])

    context.user_data["selected_topics"] = []

    await query.edit_message_text(
        f"Target Band: *{band}* \u2705\n\n"
        f"Now select your *preferred topics* (tap to toggle, then Done):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return TOPICS


async def topic_toggled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle topic toggle callback."""
    query = update.callback_query
    await query.answer()

    topic_id = query.data.replace("topic_", "")
    selected = context.user_data.get("selected_topics", [])

    if topic_id in selected:
        selected.remove(topic_id)
    else:
        selected.append(topic_id)
    context.user_data["selected_topics"] = selected

    # Rebuild keyboard with selection indicators
    keyboard = []
    row = []
    for tid, tname in TOPIC_OPTIONS:
        check = "\u2705 " if tid in selected else ""
        row.append(InlineKeyboardButton(
            f"{check}{tname}", callback_data=f"topic_{tid}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(
        f"\u2705 Done ({len(selected)} selected)", callback_data="topics_done"
    )])

    band = context.user_data.get("target_band", 7.0)
    await query.edit_message_text(
        f"Target Band: *{band}* \u2705\n\n"
        f"Selected topics: *{len(selected)}*\n"
        f"Tap topics to toggle, then press Done:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return TOPICS


async def topics_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle topic selection completion."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    chat = update.effective_chat
    band = context.user_data.get("target_band", 7.0)
    topics = context.user_data.get("selected_topics", [])

    if not topics:
        topics = ["education", "environment", "technology"]

    group_id = chat.id if chat.type in ("group", "supergroup") else None

    # Create user in Firebase
    firebase_service.create_user(
        telegram_id=user.id,
        name=user.first_name,
        username=user.username or "",
        group_id=group_id,
        target_band=band,
        topics=topics,
    )

    # Set up scheduler if in a group
    if group_id:
        from services.scheduler_service import setup_group_schedule
        setup_group_schedule(context.bot, group_id)

    topic_names = [name for tid, name in TOPIC_OPTIONS if tid in topics]

    await query.edit_message_text(
        f"\U0001f389 *Profile created!*\n\n"
        f"\U0001f3af Target Band: *{band}*\n"
        f"\U0001f4da Topics: _{', '.join(topic_names)}_\n"
        f"\u23f0 Daily vocab at: *08:00* (Vietnam time)\n\n"
        f"*Group:*\n"
        f"  /daily \u2014 Today's vocabulary\n"
        f"  /challenge \u2014 Daily challenge\n"
        f"  /leaderboard \u2014 Rankings\n"
        f"  /groupsettings \u2014 Group preferences\n\n"
        f"*DM me for:*\n"
        f"  /mydaily \u2014 Personal daily vocab\n"
        f"  /quiz \u2014 5-question quiz\n"
        f"  /review \u2014 Review weak words\n"
        f"  /word <word> \u2014 Look up a word\n"
        f"  /write <text> \u2014 Writing feedback\n"
        f"  /translate <text> \u2014 Translate EN\u2194VI\n"
        f"  /mywords \u2014 Your vocabulary\n"
        f"  /progress \u2014 Your stats\n"
        f"  /settings \u2014 Preferences\n\n"
        f"Let's start learning! \U0001f680",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def _handle_challenge_deeplink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route challenge deep-link to the DM challenge flow."""
    payload = context.args[0]  # "challenge_{group_id}_{date_str}"
    # Parse: "challenge_{group_id}_{date_str}"
    # group_id can be negative (e.g. -1001234567890)
    parts = payload.split("_", 1)  # ["challenge", "{group_id}_{date_str}"]
    if len(parts) != 2:
        await update.message.reply_text("Invalid challenge link.")
        return ConversationHandler.END

    remainder = parts[1]  # "{group_id}_{date_str}"
    # date_str is always YYYY-MM-DD (10 chars) at the end
    # group_id is everything before the last underscore + 10-char date
    last_underscore = remainder.rfind("_")
    if last_underscore == -1:
        await update.message.reply_text("Invalid challenge link.")
        return ConversationHandler.END

    try:
        group_id = int(remainder[:last_underscore])
        date_str = remainder[last_underscore + 1:]
    except (ValueError, IndexError):
        await update.message.reply_text("Invalid challenge link.")
        return ConversationHandler.END

    from bot.handlers.challenge import start_challenge_dm
    await start_challenge_dm(update, context, group_id, date_str)
    return ConversationHandler.END


async def _handle_link_deeplink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem a US-M12.2 ``link_<token>`` payload from `/start`.

    Three sub-cases (per ``firebase_service.redeem_link_token_bot``):
    - status='linked' — user new on Telegram side; row created from web
      profile + auth_uid stamped.
    - status='merged' — TG row pre-existed; merged web_xxx into it.
    - status='already_linked' — no-op.
    """
    user = update.effective_user
    if not user:
        return ConversationHandler.END
    payload = context.args[0]  # "link_<token>"
    token = payload[len("link_"):]
    if not token:
        await update.message.reply_text("Link không hợp lệ.")
        return ConversationHandler.END

    try:
        result = firebase_service.redeem_link_token_bot(token, user.id)
    except Exception as exc:  # noqa: BLE001 — surface the exception text
        logger.exception(
            "link redeem failed tg_user=%s token=%s exc_type=%s",
            user.id, token, type(exc).__name__,
        )
        # Surface the exception type to the user so they can paste it into
        # an issue without scrolling the bot's stderr. The full trace stays
        # in the structlog stream above for ops.
        await update.message.reply_text(
            "Không liên kết được lúc này, thử lại sau.\n"
            f"<i>Mã lỗi: {type(exc).__name__}</i>",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    status = result.get("status")
    if status in ("linked", "merged"):
        await update.message.reply_text(
            "✅ Đã liên kết tài khoản web với Telegram của bạn.\n"
            "Mọi tiến độ học giờ đồng bộ giữa 2 bên.",
        )
    elif status == "already_linked":
        await update.message.reply_text("Bạn đã liên kết rồi.")
    elif status == "expired":
        await update.message.reply_text(
            "Link đã hết hạn. Vào lại trang web để tạo link mới.",
        )
    elif status == "already_used":
        await update.message.reply_text(
            "Link đã được dùng rồi. Vào lại trang web để tạo link mới.",
        )
    elif status == "conflict":
        await update.message.reply_text(
            "Tài khoản Telegram này đã liên kết với một tài khoản web khác. "
            "Dùng /unlink trước nếu bạn muốn đổi.",
        )
    elif status == "telegram_user_missing":
        await update.message.reply_text(
            "Không tìm thấy tài khoản web tương ứng. Thử tạo link mới từ web.",
        )
    else:  # invalid / wrong_direction / unknown
        await update.message.reply_text(
            "Link không hợp lệ. Vào lại trang web để tạo link mới.",
        )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the onboarding conversation."""
    await update.message.reply_text("Setup cancelled. Use /start to try again.")
    return ConversationHandler.END


def get_start_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            BAND: [CallbackQueryHandler(band_selected, pattern=r"^band_")],
            TOPICS: [
                CallbackQueryHandler(topic_toggled, pattern=r"^topic_"),
                CallbackQueryHandler(topics_done, pattern=r"^topics_done$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    text = (
        "\U0001f4d6 IELTS Study Bot - Commands\n\n"
        "Group:\n"
        "/daily - Today's 10 IELTS words\n"
        "/audio <number> - Hear pronunciation\n"
        "/challenge - Daily challenge\n"
        "/leaderboard - Rankings\n"
        "/results - Challenge results\n"
        "/newdaily - Force new vocab\n"
        "/groupsettings - Group preferences\n\n"
        "DM (private chat):\n"
        "/mydaily - Personal daily vocab (your band)\n"
        "/quiz - 5-question quiz\n"
        "/review - Review weak words\n"
        "/word <word> - Look up a word\n"
        "/write <text> - Writing feedback\n"
        "/translate <text> - Translate EN/VI\n"
        "/mywords - Your vocabulary\n"
        "/progress - Your stats\n"
        "/usage - Today's AI quota\n"
        "/settings - Personal preferences\n"
        "/help - This message"
    )
    await update.message.reply_text(text)
