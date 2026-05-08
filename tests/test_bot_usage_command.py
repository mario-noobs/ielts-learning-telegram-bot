"""US-M13.5 — bot ``/usage`` command coverage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


class _FakeChat(SimpleNamespace):
    pass


class _FakeUser(SimpleNamespace):
    pass


class _FakeMessage:
    def __init__(self) -> None:
        self.reply_text = AsyncMock()


class _FakeUpdate:
    def __init__(self, *, chat_type: str = "private", user_id: int = 100) -> None:
        self.message = _FakeMessage()
        self.effective_message = self.message
        self.effective_chat = _FakeChat(
            type=chat_type,
            id=-100 if chat_type != "private" else user_id,
        )
        self.effective_user = _FakeUser(id=user_id, first_name="U", username="u")


def _reset_at_iso(hours_ahead: int = 5) -> str:
    """Build an ISO `reset_at` ``hours_ahead`` from now (UTC)."""
    return (
        datetime.now(timezone.utc).replace(microsecond=0)
        + timedelta(hours=hours_ahead)
    ).isoformat()


@pytest.mark.asyncio
async def test_usage_in_dm_formats_summary_under_threshold():
    """Below 80%: 4-line response, no upgrade nudge."""
    from bot.handlers import usage as usage_handler

    update = _FakeUpdate(chat_type="private", user_id=42)

    fake_user = {"id": "42", "plan": "free", "quota_override": None}
    fake_snap = {
        "plan": "free",
        "used": 5,
        "cap": 10,
        "by_feature": {"words": 2, "quiz": 2, "writing": 1},
        "reset_at": _reset_at_iso(hours_ahead=4),
    }

    with patch(
        "bot.handlers.usage.firebase_service.get_user",
        return_value=fake_user,
    ), patch(
        "bot.handlers.usage.quota_service.get_usage_snapshot",
        return_value=fake_snap,
    ):
        await usage_handler.usage_command(update, context=None)

    text = update.message.reply_text.await_args.args[0]
    lines = text.split("\n")
    # Line 1: plan + used/cap
    assert lines[0] == "Gói free · 5/10"
    # Line 2: ASCII bar @ 50%
    assert lines[1].startswith("[") and lines[1].endswith("] 50%")
    assert lines[1].count("█") == 10 and lines[1].count("░") == 10
    # Line 3: per-feature breakdown in fixed order
    assert lines[2] == "Vocab 2 · Quiz 2 · Writing 1 · Listening 0 · Reading 0"
    # Line 4: relative reset
    assert lines[3].startswith("Đặt lại sau ")
    # No upgrade nudge below threshold
    assert "Nâng cấp" not in text
    assert len(lines) == 4


@pytest.mark.asyncio
async def test_usage_in_dm_appends_upgrade_nudge_at_or_above_80pct():
    """At 80% (8/10) the upgrade line is appended; at 70% it isn't."""
    from bot.handlers import usage as usage_handler

    fake_user = {"id": "42", "plan": "free", "quota_override": None}

    # ── below threshold (7/10 = 70%) ────────────────────────────
    update_below = _FakeUpdate(chat_type="private", user_id=42)
    snap_below = {
        "plan": "free", "used": 7, "cap": 10,
        "by_feature": {"quiz": 7},
        "reset_at": _reset_at_iso(hours_ahead=3),
    }
    with patch(
        "bot.handlers.usage.firebase_service.get_user",
        return_value=fake_user,
    ), patch(
        "bot.handlers.usage.quota_service.get_usage_snapshot",
        return_value=snap_below,
    ):
        await usage_handler.usage_command(update_below, context=None)
    text_below = update_below.message.reply_text.await_args.args[0]
    assert "Nâng cấp" not in text_below

    # ── at threshold (8/10 = 80%) ──────────────────────────────
    update_at = _FakeUpdate(chat_type="private", user_id=42)
    snap_at = {
        "plan": "free", "used": 8, "cap": 10,
        "by_feature": {"quiz": 8},
        "reset_at": _reset_at_iso(hours_ahead=3),
    }
    with patch(
        "bot.handlers.usage.firebase_service.get_user",
        return_value=fake_user,
    ), patch(
        "bot.handlers.usage.quota_service.get_usage_snapshot",
        return_value=snap_at,
    ):
        await usage_handler.usage_command(update_at, context=None)
    text_at = update_at.message.reply_text.await_args.args[0]
    assert "Nâng cấp: web.app/pricing" in text_at
