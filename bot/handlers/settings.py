import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services import firebase_service
from services.scheduler_service import setup_group_schedule

logger = logging.getLogger(__name__)

TOPIC_OPTIONS = [
    ("education", "Education"), ("environment", "Environment"),
    ("technology", "Technology"), ("health", "Health"),
    ("society", "Society"), ("economy", "Economy"),
    ("government", "Government"), ("media", "Media"),
    ("science", "Science"), ("travel", "Travel"),
    ("food", "Food"), ("arts", "Arts"),
]


async def settings_command(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings — change preferences (DM only)."""
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        await update.message.reply_text(
            "DM me to change your settings! \U0001f4ac"
        )
        return

    user_data = firebase_service.get_user(user.id)
    if not user_data:
        await update.message.reply_text("Please /start in the group first!")
        return

    current_band = user_data.get("target_band", 7.0)
    current_topics = user_data.get("topics", [])
    current_time = user_data.get("daily_time", "08:00")

    topic_names = [n for tid, n in TOPIC_OPTIONS if tid in current_topics]

    keyboard = [
        [InlineKeyboardButton(
            "\U0001f3af Change Target Band",
            callback_data="settings_band"
        )],
        [InlineKeyboardButton(
            "\U0001f4da Change Topics",
            callback_data="settings_topics"
        )],
        [InlineKeyboardButton(
            "\u23f0 Change Daily Time",
            callback_data="settings_time"
        )],
    ]

    await update.message.reply_text(
        f"\u2699\ufe0f *Settings*\n\n"
        f"\U0001f3af Target Band: *{current_band}*\n"
        f"\U0001f4da Topics: _{', '.join(topic_names)}_\n"
        f"\u23f0 Daily Time: *{current_time}*\n\n"
        f"What would you like to change?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def settings_callback(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Handle settings menu buttons."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if query.data == "settings_band":
        keyboard = [
            [InlineKeyboardButton("5.5", callback_data="setband_5.5"),
             InlineKeyboardButton("6.0", callback_data="setband_6.0")],
            [InlineKeyboardButton("6.5", callback_data="setband_6.5"),
             InlineKeyboardButton("7.0", callback_data="setband_7.0")],
            [InlineKeyboardButton("7.5", callback_data="setband_7.5"),
             InlineKeyboardButton("8.0+", callback_data="setband_8.0")],
        ]
        await query.edit_message_text(
            "Select your new target band:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "settings_topics":
        user_data = firebase_service.get_user(user.id)
        selected = user_data.get("topics", []) if user_data else []
        context.user_data["settings_topics"] = list(selected)

        keyboard = []
        row = []
        for tid, tname in TOPIC_OPTIONS:
            check = "\u2705 " if tid in selected else ""
            row.append(InlineKeyboardButton(
                f"{check}{tname}", callback_data=f"settopic_{tid}"
            ))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(
            "\u2705 Save", callback_data="settopics_save"
        )])

        await query.edit_message_text(
            "Toggle topics (tap to select/deselect):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "settings_time":
        keyboard = [
            [InlineKeyboardButton("06:00", callback_data="settime_06:00"),
             InlineKeyboardButton("07:00", callback_data="settime_07:00"),
             InlineKeyboardButton("08:00", callback_data="settime_08:00")],
            [InlineKeyboardButton("09:00", callback_data="settime_09:00"),
             InlineKeyboardButton("12:00", callback_data="settime_12:00"),
             InlineKeyboardButton("18:00", callback_data="settime_18:00")],
            [InlineKeyboardButton("20:00", callback_data="settime_20:00"),
             InlineKeyboardButton("21:00", callback_data="settime_21:00"),
             InlineKeyboardButton("22:00", callback_data="settime_22:00")],
        ]
        await query.edit_message_text(
            "Select your preferred daily vocabulary time (Vietnam time):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def set_band_callback(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Handle band change."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    band = float(query.data.replace("setband_", ""))
    firebase_service.update_user(user.id, {"target_band": band})

    await query.edit_message_text(
        f"\u2705 Target band updated to *{band}*!",
        parse_mode="Markdown"
    )


async def set_topic_toggle(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    """Handle topic toggle in settings."""
    query = update.callback_query
    await query.answer()

    topic_id = query.data.replace("settopic_", "")
    selected = context.user_data.get("settings_topics", [])

    if topic_id in selected:
        selected.remove(topic_id)
    else:
        selected.append(topic_id)
    context.user_data["settings_topics"] = selected

    # Rebuild keyboard
    keyboard = []
    row = []
    for tid, tname in TOPIC_OPTIONS:
        check = "\u2705 " if tid in selected else ""
        row.append(InlineKeyboardButton(
            f"{check}{tname}", callback_data=f"settopic_{tid}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(
        f"\u2705 Save ({len(selected)} selected)",
        callback_data="settopics_save"
    )])

    await query.edit_message_text(
        "Toggle topics (tap to select/deselect):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def save_topics_callback(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    """Save selected topics."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    topics = context.user_data.get("settings_topics", [])
    if not topics:
        topics = ["education", "environment", "technology"]

    firebase_service.update_user(user.id, {"topics": topics})
    topic_names = [n for tid, n in TOPIC_OPTIONS if tid in topics]

    await query.edit_message_text(
        f"\u2705 Topics updated: _{', '.join(topic_names)}_",
        parse_mode="Markdown"
    )


async def set_time_callback(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Handle daily time change."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    time = query.data.replace("settime_", "")
    firebase_service.update_user(user.id, {"daily_time": time})

    # Update scheduler if user has a group
    user_data = firebase_service.get_user(user.id)
    group_id = user_data.get("group_id") if user_data else None
    if group_id:
        setup_group_schedule(context.bot, group_id, time)

    await query.edit_message_text(
        f"\u2705 Daily vocabulary time updated to *{time}* (Vietnam time)!",
        parse_mode="Markdown"
    )


# ─── Group Settings (shared for /daily, /challenge) ───────────

async def groupsettings_command(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    """Handle /groupsettings — change shared group preferences."""
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use this in the group chat.")
        return

    group = firebase_service.get_group_settings(chat.id)
    if not group:
        firebase_service.create_group(chat.id)
        group = firebase_service.get_group_settings(chat.id)

    band = group.get("default_band", 7.0)
    topics = group.get("topics", [])
    daily_time = group.get("daily_time", "08:00")
    topic_names = [n for tid, n in TOPIC_OPTIONS if tid in topics]

    keyboard = [
        [InlineKeyboardButton(
            "Change Band", callback_data="gsettings_band"
        )],
        [InlineKeyboardButton(
            "Change Topics", callback_data="gsettings_topics"
        )],
        [InlineKeyboardButton(
            "Change Daily Time", callback_data="gsettings_time"
        )],
    ]

    await update.message.reply_text(
        f"Group Settings (shared for /daily & /challenge)\n\n"
        f"Band: {band}\n"
        f"Topics: {', '.join(topic_names) or 'default'}\n"
        f"Daily Time: {daily_time}\n\n"
        f"What to change?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def gsettings_callback(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Handle group settings menu buttons."""
    query = update.callback_query
    await query.answer()
    chat = update.effective_chat

    if query.data == "gsettings_band":
        keyboard = [
            [InlineKeyboardButton("5.5", callback_data="gsetband_5.5"),
             InlineKeyboardButton("6.0", callback_data="gsetband_6.0")],
            [InlineKeyboardButton("6.5", callback_data="gsetband_6.5"),
             InlineKeyboardButton("7.0", callback_data="gsetband_7.0")],
            [InlineKeyboardButton("7.5", callback_data="gsetband_7.5"),
             InlineKeyboardButton("8.0+", callback_data="gsetband_8.0")],
        ]
        await query.edit_message_text(
            "Select group target band:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "gsettings_topics":
        group = firebase_service.get_group_settings(chat.id)
        selected = group.get("topics", []) if group else []
        context.chat_data["gsettings_topics"] = list(selected)

        keyboard = []
        row = []
        for tid, tname in TOPIC_OPTIONS:
            check = "\u2705 " if tid in selected else ""
            row.append(InlineKeyboardButton(
                f"{check}{tname}", callback_data=f"gsettopic_{tid}"
            ))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(
            "\u2705 Save", callback_data="gsettopics_save"
        )])

        await query.edit_message_text(
            "Toggle group topics:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "gsettings_time":
        keyboard = [
            [InlineKeyboardButton("06:00", callback_data="gsettime_06:00"),
             InlineKeyboardButton("07:00", callback_data="gsettime_07:00"),
             InlineKeyboardButton("08:00", callback_data="gsettime_08:00")],
            [InlineKeyboardButton("09:00", callback_data="gsettime_09:00"),
             InlineKeyboardButton("12:00", callback_data="gsettime_12:00"),
             InlineKeyboardButton("18:00", callback_data="gsettime_18:00")],
            [InlineKeyboardButton("20:00", callback_data="gsettime_20:00"),
             InlineKeyboardButton("21:00", callback_data="gsettime_21:00"),
             InlineKeyboardButton("22:00", callback_data="gsettime_22:00")],
        ]
        await query.edit_message_text(
            "Select daily vocab time (Vietnam time):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def gset_band_callback(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Handle group band change."""
    query = update.callback_query
    await query.answer()
    chat = update.effective_chat

    band = float(query.data.replace("gsetband_", ""))
    firebase_service.update_group_settings(chat.id, {"default_band": band})

    await query.edit_message_text(f"\u2705 Group band updated to {band}!")


async def gset_topic_toggle(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Handle group topic toggle."""
    query = update.callback_query
    await query.answer()

    topic_id = query.data.replace("gsettopic_", "")
    selected = context.chat_data.get("gsettings_topics", [])

    if topic_id in selected:
        selected.remove(topic_id)
    else:
        selected.append(topic_id)
    context.chat_data["gsettings_topics"] = selected

    keyboard = []
    row = []
    for tid, tname in TOPIC_OPTIONS:
        check = "\u2705 " if tid in selected else ""
        row.append(InlineKeyboardButton(
            f"{check}{tname}", callback_data=f"gsettopic_{tid}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(
        f"\u2705 Save ({len(selected)} selected)",
        callback_data="gsettopics_save"
    )])

    await query.edit_message_text(
        "Toggle group topics:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def gsave_topics_callback(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
    """Save group topics."""
    query = update.callback_query
    await query.answer()
    chat = update.effective_chat

    topics = context.chat_data.get("gsettings_topics", [])
    if not topics:
        topics = ["education", "environment", "technology"]

    firebase_service.update_group_settings(chat.id, {"topics": topics})
    topic_names = [n for tid, n in TOPIC_OPTIONS if tid in topics]

    await query.edit_message_text(
        f"\u2705 Group topics updated: {', '.join(topic_names)}"
    )


async def gset_time_callback(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Handle group daily time change."""
    query = update.callback_query
    await query.answer()
    chat = update.effective_chat

    time = query.data.replace("gsettime_", "")
    firebase_service.update_group_settings(chat.id, {"daily_time": time})
    setup_group_schedule(context.bot, chat.id, time)

    await query.edit_message_text(
        f"\u2705 Daily vocab time updated to {time} (Vietnam time)!"
    )
