"""Daily Challenge results naming fallback chain (#228 follow-up).

Bug: results post showed "🥇 Unknown — 2/10" when a user clicked
challenge buttons in the group but never /start'd the bot. Fix
falls back to the Telegram display name captured at answer-time.
"""

from __future__ import annotations

from unittest.mock import patch

from services import challenge_service


def _challenge(participants: dict, display_names: dict | None = None,
               total_q: int = 10) -> dict:
    return {
        "participants": participants,
        "display_names": display_names or {},
        "questions": [{}] * total_q,
    }


def test_pg_profile_name_wins_over_telegram_display_name():
    """User has a /settings name → that wins over the Telegram first_name."""
    challenge = _challenge(
        participants={"100": 7},
        display_names={"100": "Telegram First"},
    )
    with patch.object(
        challenge_service.firebase_service, "get_user",
        return_value={"id": "100", "name": "Mario Bùi"},
    ):
        text = challenge_service._build_results_text(challenge, "2026-05-09")
    assert "Mario Bùi" in text
    assert "Telegram First" not in text


def test_telegram_display_name_used_when_no_pg_profile():
    """No /start = no PG row → fall back to display_names captured at answer-time."""
    challenge = _challenge(
        participants={"200": 5},
        display_names={"200": "Quân"},
    )
    with patch.object(
        challenge_service.firebase_service, "get_user", return_value=None,
    ):
        text = challenge_service._build_results_text(challenge, "2026-05-09")
    assert "Quân" in text
    assert "Unknown" not in text


def test_user_id_fallback_when_neither_source_has_a_name():
    """Worst case (legacy data, no display_names map) — show "User {uid}",
    never a literal "Unknown" string which gives no actionable signal."""
    challenge = _challenge(participants={"300": 2}, display_names={})
    with patch.object(
        challenge_service.firebase_service, "get_user", return_value=None,
    ):
        text = challenge_service._build_results_text(challenge, "2026-05-09")
    assert "User 300" in text
    assert "Unknown" not in text


def test_pg_profile_with_blank_name_falls_through_to_display_name():
    """PG returned a row but its `name` field is empty/whitespace —
    treat it as missing and fall through to the Telegram name."""
    challenge = _challenge(
        participants={"400": 3},
        display_names={"400": "Hà"},
    )
    with patch.object(
        challenge_service.firebase_service, "get_user",
        return_value={"id": "400", "name": "   "},
    ):
        text = challenge_service._build_results_text(challenge, "2026-05-09")
    assert "Hà" in text
