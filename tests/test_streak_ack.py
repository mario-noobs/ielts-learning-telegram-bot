"""Streak ack callback handler (US-#226).

Verifies the daily-vocab "Tôi đã đọc" button correctly ticks streak
for the clicker only and is idempotent within a single day. The
existing `update_streak` repo method is the authority on idempotency
(`delta_days == 0` → no-op via last_active gate); these tests focus
on the bot-handler wiring.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.vocabulary import streak_ack_callback


def _build_update(uid: int = 12345) -> tuple[MagicMock, AsyncMock]:
    """Construct a minimal Telegram Update with a CallbackQuery."""
    query = MagicMock()
    query.from_user = MagicMock(id=uid)
    query.answer = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    return update, query.answer


@pytest.mark.asyncio
async def test_streak_ack_ticks_streak_for_clicker_only():
    update, ack = _build_update(uid=42)
    user_doc = {"id": "42", "name": "Test", "streak": 0}
    refreshed = {**user_doc, "streak": 5}

    with patch(
        "bot.handlers.vocabulary.firebase_service.get_user",
        side_effect=[user_doc, refreshed],
    ), patch(
        "bot.handlers.vocabulary.firebase_service.update_streak",
    ) as upd:
        await streak_ack_callback(update, MagicMock())

    # update_streak called for the clicker (uid=42), not the whole group.
    upd.assert_called_once_with(42)
    # Ephemeral toast contains the refreshed streak number.
    ack.assert_called_once()
    args, kwargs = ack.call_args
    text = args[0] if args else kwargs.get("text", "")
    assert "5" in text


@pytest.mark.asyncio
async def test_streak_ack_no_op_when_user_not_registered():
    """Pre-/start user clicks ack → friendly nudge, no streak write."""
    update, ack = _build_update(uid=999)

    with patch(
        "bot.handlers.vocabulary.firebase_service.get_user",
        return_value=None,
    ), patch(
        "bot.handlers.vocabulary.firebase_service.update_streak",
    ) as upd:
        await streak_ack_callback(update, MagicMock())

    upd.assert_not_called()
    ack.assert_called_once()
    # The /start nudge is shown as alert.
    _, kwargs = ack.call_args
    assert kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_streak_ack_idempotent_via_last_active_gate():
    """Two clicks same day → second call is a no-op at the repo layer.

    The handler still calls `update_streak` twice — but the underlying
    repo treats `delta_days == 0` as a no-op so the user's streak
    doesn't double. This test asserts the handler doesn't try to
    short-circuit; the repo is the single source of truth on idempotency.
    """
    update, _ = _build_update(uid=7)
    user_doc = {"id": "7", "streak": 3}

    with patch(
        "bot.handlers.vocabulary.firebase_service.get_user",
        return_value=user_doc,
    ), patch(
        "bot.handlers.vocabulary.firebase_service.update_streak",
    ) as upd:
        await streak_ack_callback(update, MagicMock())
        await streak_ack_callback(update, MagicMock())

    # Both clicks dispatch to the repo; the repo handles dedup.
    assert upd.call_count == 2
    for call in upd.call_args_list:
        assert call.args == (7,)
