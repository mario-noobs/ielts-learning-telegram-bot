"""Regression — existing user /start in a group rebinds their group_id.

Bug user hit: DM-registered user joined a group, ran /start there, but
the bot just echoed "Welcome back" and never updated their group_id.
The web /settings/groups page (US-#227) then never saw them as a member.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.start import start_command


class _Chat:
    def __init__(self, chat_id: int, chat_type: str):
        self.id = chat_id
        self.type = chat_type


def _make_update(uid: int, chat_id: int, chat_type: str) -> MagicMock:
    upd = MagicMock()
    upd.effective_user = MagicMock(id=uid, first_name="Test")
    upd.effective_chat = _Chat(chat_id, chat_type)
    upd.message = MagicMock()
    upd.message.reply_text = AsyncMock()
    return upd


def _ctx(args=None) -> MagicMock:
    ctx = MagicMock()
    ctx.args = args or []
    return ctx


@pytest.mark.asyncio
async def test_existing_user_starts_in_group_rebinds_group_id():
    """Existing DM-registered user /start in group X → group_id := X."""
    user_uid = 12345
    group_chat = -100999

    existing_user = {
        "id": str(user_uid), "name": "Test", "target_band": 7.0,
        "group_id": None,  # registered in DM, never bound to a group
        "total_words": 0, "streak": 0,
    }

    update = _make_update(user_uid, group_chat, "supergroup")
    ctx = _ctx()

    with patch(
        "bot.handlers.start.firebase_service.get_user",
        return_value=existing_user,
    ), patch(
        "bot.handlers.start.firebase_service.get_group_settings",
        return_value={"owner_telegram_id": 99999},  # group exists with another owner
    ), patch(
        "bot.handlers.start.firebase_service.update_user",
    ) as upd_user, patch(
        "bot.handlers.start.firebase_service.update_group_settings",
    ) as upd_group, patch(
        "bot.handlers.start.firebase_service.create_group",
    ) as create_group:
        await start_command(update, ctx)

    # group_id rebinds to the chat the user /start'd in
    upd_user.assert_called_once_with(user_uid, {"group_id": group_chat})
    # Group exists already and has an owner — don't touch it
    upd_group.assert_not_called()
    create_group.assert_not_called()
    # Confirmation message includes the "Added you to this group" line
    update.message.reply_text.assert_awaited_once()
    sent = update.message.reply_text.await_args.args[0]
    assert "Added you to this group" in sent


@pytest.mark.asyncio
async def test_existing_user_in_dm_no_group_rebind():
    """DM /start by existing user — no group_id write, no "added" message."""
    update = _make_update(uid=42, chat_id=42, chat_type="private")
    ctx = _ctx()

    with patch(
        "bot.handlers.start.firebase_service.get_user",
        return_value={"id": "42", "name": "Solo", "target_band": 7.0,
                       "group_id": None, "total_words": 0, "streak": 0},
    ), patch(
        "bot.handlers.start.firebase_service.update_user",
    ) as upd_user:
        await start_command(update, ctx)

    upd_user.assert_not_called()
    sent = update.message.reply_text.await_args.args[0]
    assert "Added you to this group" not in sent


@pytest.mark.asyncio
async def test_legacy_group_no_owner_gets_backfilled():
    """Group exists but owner_telegram_id is None — first /start backfills."""
    user_uid = 7
    group_chat = -100222

    update = _make_update(user_uid, group_chat, "group")
    ctx = _ctx()

    with patch(
        "bot.handlers.start.firebase_service.get_user",
        return_value={"id": str(user_uid), "name": "Anh", "target_band": 7.0,
                       "group_id": None, "total_words": 0, "streak": 0},
    ), patch(
        "bot.handlers.start.firebase_service.get_group_settings",
        return_value={},  # legacy: group exists but no owner field
    ), patch(
        "bot.handlers.start.firebase_service.update_user",
    ), patch(
        "bot.handlers.start.firebase_service.update_group_settings",
    ) as upd_group, patch(
        "bot.handlers.start.firebase_service.create_group",
    ) as create_group:
        await start_command(update, ctx)

    create_group.assert_not_called()
    upd_group.assert_called_once_with(
        group_chat, {"owner_telegram_id": user_uid},
    )
