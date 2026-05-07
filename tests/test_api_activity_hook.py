"""Tests for the once-per-UTC-day activity hook in ``api.auth`` (US-M11.5)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from api import auth as auth_module


@pytest.mark.asyncio
async def test_touch_last_active_writes_when_date_flips() -> None:
    user = {"id": "u-1", "last_active_date": "2025-01-01"}
    with patch("api.auth.firebase_service.update_user") as upd:
        await auth_module._touch_last_active(user)
    assert upd.called
    today = datetime.now(timezone.utc).date().isoformat()
    assert user["last_active_date"] == today


@pytest.mark.asyncio
async def test_touch_last_active_skips_when_already_today() -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    user = {"id": "u-1", "last_active_date": today}
    with patch("api.auth.firebase_service.update_user") as upd:
        await auth_module._touch_last_active(user)
    assert not upd.called


@pytest.mark.asyncio
async def test_touch_last_active_writes_when_field_missing() -> None:
    user = {"id": "u-1"}
    with patch("api.auth.firebase_service.update_user") as upd:
        await auth_module._touch_last_active(user)
    assert upd.called


@pytest.mark.asyncio
async def test_touch_last_active_swallows_errors() -> None:
    """A flaky Firestore write must not break the auth path."""
    user = {"id": "u-1", "last_active_date": "2025-01-01"}
    with patch("api.auth.firebase_service.update_user",
               side_effect=RuntimeError("flaky")):
        # Should not raise.
        await auth_module._touch_last_active(user)
    # The user dict is *not* updated when the write fails — the mutation
    # is gated on a successful round-trip.
    assert user["last_active_date"] == "2025-01-01"
