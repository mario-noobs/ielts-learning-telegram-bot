"""Bot ``/usage`` command — show today's AI quota summary (US-M13.5).

Vietnamese-first per CLAUDE.md (bot stays VN-first). Mirrors the web
``AiUsageWidget`` shape so a Telegram-only user can read remaining
quota without logging in to web.

Implementation note: the user dict from ``firebase_service.get_user`` is
the same shape ``api.permissions.enforce_ai_quota`` consumes (carries
``id``, ``plan``, ``quota_override``). We pass the same fields to
``quota_service.get_usage_snapshot`` so the bot's view of the cap and
counter stays in lock-step with the API enforcement path.

Help text for this command lives in ``bot/handlers/start.py::help_command``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from services import firebase_service
from services.admin import quota_service

logger = logging.getLogger(__name__)


# Display order + Vietnamese-friendly labels for the per-feature line.
# Feature keys match what ``enforce_ai_quota(feature)`` writes into
# ``ai_usage.feature`` (see api/routes/{words,quiz,writing,listening,
# reading}.py). Missing features render as 0.
_FEATURE_DISPLAY: list[tuple[str, str]] = [
    ("words", "Vocab"),
    ("quiz", "Quiz"),
    ("writing", "Writing"),
    ("listening", "Listening"),
    ("reading", "Reading"),
]

_PRICING_URL = "web.app/pricing"


def _ascii_bar(pct: int, width: int = 20) -> str:
    """Render a `[████░░░░] N%` style progress bar.

    ``pct`` is clamped to 0–100 for the fill calculation; the suffix
    shows the unclamped int we were given.
    """
    fill_pct = max(0, min(pct, 100))
    filled = round(fill_pct / 100 * width)
    return "[" + ("█" * filled) + ("░" * (width - filled)) + f"] {pct}%"


def _reset_relative(reset_at_iso: str) -> str:
    """Convert an ISO ``reset_at`` to ``Xh Ym`` relative to now (UTC).

    Floors to the minute. If the reset moment has already passed (clock
    skew or stale snapshot), reports ``0h 0m`` rather than negative.
    """
    reset_at = datetime.fromisoformat(reset_at_iso)
    delta = reset_at - datetime.now(timezone.utc)
    total_minutes = max(0, int(delta.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


def _format_snapshot(snap: dict) -> str:
    """Build the Vietnamese 4–5 line response from ``get_usage_snapshot``."""
    plan = snap["plan"]
    used = snap["used"]
    cap = snap["cap"]
    by_feature: dict[str, int] = snap["by_feature"]

    pct = round(used / cap * 100) if cap > 0 else 0

    feature_line = " · ".join(
        f"{label} {by_feature.get(key, 0)}" for key, label in _FEATURE_DISPLAY
    )

    lines = [
        f"Gói {plan} · {used}/{cap}",
        _ascii_bar(pct),
        feature_line,
        f"Đặt lại sau {_reset_relative(snap['reset_at'])}",
    ]
    if cap > 0 and used / cap >= 0.8:
        lines.append(f"Nâng cấp: {_PRICING_URL}")
    return "\n".join(lines)


async def usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ``/usage`` — DM-only personal quota summary."""
    message = update.message or update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not user:
        return

    if chat and chat.type != "private":
        await message.reply_text("Dùng lệnh /usage trong tin nhắn riêng với bot.")
        return

    user_data = firebase_service.get_user(user.id)
    if not user_data:
        await message.reply_text("Bạn chưa đăng ký. Dùng /start trước.")
        return

    try:
        snapshot = await asyncio.to_thread(
            quota_service.get_usage_snapshot,
            user_uid=str(user_data["id"]),
            plan=user_data.get("plan", "free"),
            quota_override=user_data.get("quota_override"),
        )
    except Exception:
        logger.exception("Failed to load usage snapshot for tg user %s", user.id)
        await message.reply_text("Không lấy được dữ liệu lúc này, thử lại sau.")
        return

    await message.reply_text(_format_snapshot(snapshot))
