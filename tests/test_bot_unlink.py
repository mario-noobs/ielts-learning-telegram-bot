"""US-M12.1 AC12 — bot ``/unlink`` command coverage."""

from __future__ import annotations

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
        self.effective_chat = _FakeChat(type=chat_type, id=-100 if chat_type != "private" else user_id)
        self.effective_user = _FakeUser(id=user_id, first_name="U", username="u")


@pytest.mark.asyncio
async def test_unlink_in_dm_real_unlink_replies_confirmation():
    from bot.handlers.unlink import unlink_command

    update = _FakeUpdate(chat_type="private", user_id=42)
    with patch(
        "bot.handlers.unlink.firebase_service.unlink_telegram",
        return_value=True,
    ):
        await unlink_command(update, context=None)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.await_args.args[0]
    assert "Đã huỷ liên kết" in text


@pytest.mark.asyncio
async def test_unlink_in_dm_no_op_replies_chua_lien_ket():
    from bot.handlers.unlink import unlink_command

    update = _FakeUpdate(chat_type="private", user_id=42)
    with patch(
        "bot.handlers.unlink.firebase_service.unlink_telegram",
        return_value=False,
    ):
        await unlink_command(update, context=None)

    text = update.message.reply_text.await_args.args[0]
    assert "chưa liên kết" in text


@pytest.mark.asyncio
async def test_unlink_outside_dm_redirects_to_dm():
    from bot.handlers.unlink import unlink_command

    update = _FakeUpdate(chat_type="group", user_id=42)
    with patch(
        "bot.handlers.unlink.firebase_service.unlink_telegram",
    ) as m_unlink:
        await unlink_command(update, context=None)

    text = update.message.reply_text.await_args.args[0]
    assert "tin nhắn riêng" in text
    m_unlink.assert_not_called()
