"""US-M12.2 AC8 — bot ``/start link_<token>`` redeem flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


class _FakeMessage:
    def __init__(self) -> None:
        self.reply_text = AsyncMock()


class _FakeUpdate:
    def __init__(self, telegram_id: int = 4242, chat_type: str = "private") -> None:
        self.message = _FakeMessage()
        self.effective_message = self.message
        self.effective_chat = SimpleNamespace(id=telegram_id, type=chat_type)
        self.effective_user = SimpleNamespace(
            id=telegram_id, first_name="U", username="u",
        )


class _FakeContext:
    def __init__(self, args=None) -> None:
        self.args = args or []
        self.user_data = {}


@pytest.mark.asyncio
async def test_start_with_link_payload_calls_redeem_and_replies_success():
    from bot.handlers.start import start_command

    update = _FakeUpdate(telegram_id=4242)
    context = _FakeContext(args=["link_xyzTOKEN123"])

    redeem_result = {"status": "linked", "telegram_id": 4242}
    with patch(
        "bot.handlers.start.firebase_service.redeem_link_token_bot",
        return_value=redeem_result,
    ) as m_redeem:
        await start_command(update, context)

    m_redeem.assert_called_once_with("xyzTOKEN123", 4242)
    text = update.message.reply_text.await_args.args[0]
    assert "Đã liên kết" in text


@pytest.mark.asyncio
async def test_start_with_link_payload_already_linked_replies_dac_lien_ket():
    from bot.handlers.start import start_command

    update = _FakeUpdate(telegram_id=4242)
    context = _FakeContext(args=["link_TOKEN"])

    with patch(
        "bot.handlers.start.firebase_service.redeem_link_token_bot",
        return_value={"status": "already_linked"},
    ):
        await start_command(update, context)

    text = update.message.reply_text.await_args.args[0]
    assert "đã liên kết" in text.lower()


@pytest.mark.asyncio
async def test_start_with_link_payload_expired_token_replies_het_han():
    from bot.handlers.start import start_command

    update = _FakeUpdate(telegram_id=4242)
    context = _FakeContext(args=["link_TOKEN"])

    with patch(
        "bot.handlers.start.firebase_service.redeem_link_token_bot",
        return_value={"status": "expired"},
    ):
        await start_command(update, context)

    text = update.message.reply_text.await_args.args[0]
    assert "hết hạn" in text


@pytest.mark.asyncio
async def test_start_with_link_payload_invalid_token_replies_invalid():
    from bot.handlers.start import start_command

    update = _FakeUpdate(telegram_id=4242)
    context = _FakeContext(args=["link_BAD"])

    with patch(
        "bot.handlers.start.firebase_service.redeem_link_token_bot",
        return_value={"status": "invalid"},
    ):
        await start_command(update, context)

    text = update.message.reply_text.await_args.args[0]
    assert "không hợp lệ" in text.lower()


@pytest.mark.asyncio
async def test_start_with_link_payload_short_circuits_onboarding():
    """Once the link token is detected, the regular onboarding path is
    skipped — `firebase_service.get_user` should NOT be hit."""
    from bot.handlers.start import start_command

    update = _FakeUpdate(telegram_id=4242)
    context = _FakeContext(args=["link_TOKEN"])

    with patch(
        "bot.handlers.start.firebase_service.redeem_link_token_bot",
        return_value={"status": "linked", "telegram_id": 4242},
    ), patch(
        "bot.handlers.start.firebase_service.get_user",
    ) as m_get_user:
        await start_command(update, context)

    m_get_user.assert_not_called()
