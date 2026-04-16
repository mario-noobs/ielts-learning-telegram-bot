"""Tests for services/async_firebase.py.

Verifies that each async wrapper correctly delegates to the underlying
synchronous firebase_service function via asyncio.to_thread and that
arguments and return values pass through unchanged.
"""

import asyncio
from unittest.mock import patch

import pytest

from services import async_firebase

# ── Helpers ──────────────────────────────────────────────────────────

def _run(coro):
    """Run an async coroutine to completion (for non-pytest-asyncio setups)."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── User Operations ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_user_delegates_and_returns():
    fake_user = {"id": "123", "name": "Alice", "streak": 5}
    with patch("services.async_firebase.firebase_service.get_user", return_value=fake_user) as mock:
        result = await async_firebase.get_user(123)
    mock.assert_called_once_with(123)
    assert result == fake_user


@pytest.mark.asyncio
async def test_get_user_returns_none_when_missing():
    with patch("services.async_firebase.firebase_service.get_user", return_value=None) as mock:
        result = await async_firebase.get_user(999)
    mock.assert_called_once_with(999)
    assert result is None


@pytest.mark.asyncio
async def test_create_user_passes_all_kwargs():
    fake_user = {"id": "42", "name": "Bob"}
    with patch("services.async_firebase.firebase_service.create_user", return_value=fake_user) as mock:
        result = await async_firebase.create_user(
            42, "Bob", username="bob42", group_id=100, target_band=6.5, topics=["tech"],
        )
    mock.assert_called_once_with(
        42, "Bob",
        username="bob42", group_id=100, target_band=6.5, topics=["tech"],
    )
    assert result == fake_user


@pytest.mark.asyncio
async def test_update_user():
    with patch("services.async_firebase.firebase_service.update_user") as mock:
        await async_firebase.update_user(1, {"streak": 10})
    mock.assert_called_once_with(1, {"streak": 10})


@pytest.mark.asyncio
async def test_get_all_users_in_group():
    fake = [{"id": "1"}, {"id": "2"}]
    with patch("services.async_firebase.firebase_service.get_all_users_in_group", return_value=fake) as mock:
        result = await async_firebase.get_all_users_in_group(55)
    mock.assert_called_once_with(55)
    assert result == fake


@pytest.mark.asyncio
async def test_get_all_users():
    fake = [{"id": "1"}]
    with patch("services.async_firebase.firebase_service.get_all_users", return_value=fake) as mock:
        result = await async_firebase.get_all_users()
    mock.assert_called_once_with()
    assert result == fake


@pytest.mark.asyncio
async def test_update_streak():
    with patch("services.async_firebase.firebase_service.update_streak") as mock:
        await async_firebase.update_streak(7)
    mock.assert_called_once_with(7)


# ── Vocabulary Operations ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_word_to_user():
    with patch("services.async_firebase.firebase_service.add_word_to_user", return_value="word_abc") as mock:
        result = await async_firebase.add_word_to_user(1, {"word": "hello"})
    mock.assert_called_once_with(1, {"word": "hello"})
    assert result == "word_abc"


@pytest.mark.asyncio
async def test_get_user_vocabulary():
    fake = [{"id": "w1", "word": "cat"}]
    with patch("services.async_firebase.firebase_service.get_user_vocabulary", return_value=fake) as mock:
        result = await async_firebase.get_user_vocabulary(1, limit=20)
    mock.assert_called_once_with(1, 20)
    assert result == fake


@pytest.mark.asyncio
async def test_get_user_word_list():
    with patch("services.async_firebase.firebase_service.get_user_word_list", return_value=["cat", "dog"]) as mock:
        result = await async_firebase.get_user_word_list(1)
    mock.assert_called_once_with(1)
    assert result == ["cat", "dog"]


@pytest.mark.asyncio
async def test_get_mastered_words():
    with patch("services.async_firebase.firebase_service.get_mastered_words", return_value=[]) as mock:
        result = await async_firebase.get_mastered_words(1)
    mock.assert_called_once_with(1)
    assert result == []


@pytest.mark.asyncio
async def test_get_due_words():
    fake = [{"id": "w1"}]
    with patch("services.async_firebase.firebase_service.get_due_words", return_value=fake) as mock:
        result = await async_firebase.get_due_words(1, limit=5)
    mock.assert_called_once_with(1, 5)
    assert result == fake


@pytest.mark.asyncio
async def test_update_word_srs():
    with patch("services.async_firebase.firebase_service.update_word_srs") as mock:
        await async_firebase.update_word_srs(1, "w1", {"srs_interval": 3})
    mock.assert_called_once_with(1, "w1", {"srs_interval": 3})


@pytest.mark.asyncio
async def test_get_word_by_id():
    fake = {"id": "w1", "word": "test"}
    with patch("services.async_firebase.firebase_service.get_word_by_id", return_value=fake) as mock:
        result = await async_firebase.get_word_by_id(1, "w1")
    mock.assert_called_once_with(1, "w1")
    assert result == fake


# ── Quiz History ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_quiz_result():
    with patch("services.async_firebase.firebase_service.save_quiz_result") as mock:
        await async_firebase.save_quiz_result(1, {"score": 5})
    mock.assert_called_once_with(1, {"score": 5})


@pytest.mark.asyncio
async def test_get_latest_quiz():
    fake = {"id": "q1", "score": 8}
    with patch("services.async_firebase.firebase_service.get_latest_quiz", return_value=fake) as mock:
        result = await async_firebase.get_latest_quiz(1)
    mock.assert_called_once_with(1)
    assert result == fake


@pytest.mark.asyncio
async def test_get_quiz_stats():
    fake = {"total": 10, "correct": 8, "accuracy": 80.0}
    with patch("services.async_firebase.firebase_service.get_quiz_stats", return_value=fake) as mock:
        result = await async_firebase.get_quiz_stats(1)
    mock.assert_called_once_with(1)
    assert result == fake


# ── Writing History ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_writing():
    with patch("services.async_firebase.firebase_service.save_writing") as mock:
        await async_firebase.save_writing(1, {"text": "essay"})
    mock.assert_called_once_with(1, {"text": "essay"})


# ── Group Operations ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_group_settings():
    fake = {"id": "10", "daily_time": "08:00"}
    with patch("services.async_firebase.firebase_service.get_group_settings", return_value=fake) as mock:
        result = await async_firebase.get_group_settings(10)
    mock.assert_called_once_with(10)
    assert result == fake


@pytest.mark.asyncio
async def test_create_group():
    with patch("services.async_firebase.firebase_service.create_group") as mock:
        await async_firebase.create_group(10, settings={"daily_time": "09:00"})
    mock.assert_called_once_with(10, settings={"daily_time": "09:00"})


@pytest.mark.asyncio
async def test_update_group_settings():
    with patch("services.async_firebase.firebase_service.update_group_settings") as mock:
        await async_firebase.update_group_settings(10, {"daily_time": "10:00"})
    mock.assert_called_once_with(10, {"daily_time": "10:00"})


@pytest.mark.asyncio
async def test_get_all_groups():
    fake = [{"id": "1"}]
    with patch("services.async_firebase.firebase_service.get_all_groups", return_value=fake) as mock:
        result = await async_firebase.get_all_groups()
    mock.assert_called_once_with()
    assert result == fake


# ── Daily Words (Group) ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_daily_words():
    with patch("services.async_firebase.firebase_service.save_daily_words") as mock:
        await async_firebase.save_daily_words(10, "2026-04-16", ["cat"], "animals")
    mock.assert_called_once_with(10, "2026-04-16", ["cat"], "animals")


@pytest.mark.asyncio
async def test_get_daily_words():
    fake = {"words": ["cat"], "topic": "animals"}
    with patch("services.async_firebase.firebase_service.get_daily_words", return_value=fake) as mock:
        result = await async_firebase.get_daily_words(10, "2026-04-16")
    mock.assert_called_once_with(10, "2026-04-16")
    assert result == fake


# ── User Daily Words (DM) ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_user_daily_words():
    with patch("services.async_firebase.firebase_service.save_user_daily_words") as mock:
        await async_firebase.save_user_daily_words(1, "2026-04-16", ["dog"], "pets")
    mock.assert_called_once_with(1, "2026-04-16", ["dog"], "pets")


@pytest.mark.asyncio
async def test_get_user_daily_words():
    fake = {"words": ["dog"], "topic": "pets"}
    with patch("services.async_firebase.firebase_service.get_user_daily_words", return_value=fake) as mock:
        result = await async_firebase.get_user_daily_words(1, "2026-04-16")
    mock.assert_called_once_with(1, "2026-04-16")
    assert result == fake


# ── Challenge (Group) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_challenge():
    with patch("services.async_firebase.firebase_service.save_challenge") as mock:
        await async_firebase.save_challenge(10, "2026-04-16", [{"q": "?"}], deadline_minutes=30)
    mock.assert_called_once_with(10, "2026-04-16", [{"q": "?"}], deadline_minutes=30)


@pytest.mark.asyncio
async def test_get_challenge():
    fake = {"id": "2026-04-16", "status": "active"}
    with patch("services.async_firebase.firebase_service.get_challenge", return_value=fake) as mock:
        result = await async_firebase.get_challenge(10, "2026-04-16")
    mock.assert_called_once_with(10, "2026-04-16")
    assert result == fake


@pytest.mark.asyncio
async def test_update_challenge_score():
    with patch("services.async_firebase.firebase_service.update_challenge_score") as mock:
        await async_firebase.update_challenge_score(10, "2026-04-16", 42, 5)
    mock.assert_called_once_with(10, "2026-04-16", 42, 5)


# ── Challenge Answers ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_challenge_answer():
    with patch("services.async_firebase.firebase_service.save_challenge_answer") as mock:
        await async_firebase.save_challenge_answer(10, "2026-04-16", 42, 0, True)
    mock.assert_called_once_with(10, "2026-04-16", 42, 0, True)


@pytest.mark.asyncio
async def test_mark_challenge_answer_complete():
    with patch("services.async_firebase.firebase_service.mark_challenge_answer_complete") as mock:
        await async_firebase.mark_challenge_answer_complete(10, "2026-04-16", 42)
    mock.assert_called_once_with(10, "2026-04-16", 42)


@pytest.mark.asyncio
async def test_get_user_challenge_answers():
    fake = {"id": "42", "responses": {"0": True}}
    with patch("services.async_firebase.firebase_service.get_user_challenge_answers", return_value=fake) as mock:
        result = await async_firebase.get_user_challenge_answers(10, "2026-04-16", 42)
    mock.assert_called_once_with(10, "2026-04-16", 42)
    assert result == fake


@pytest.mark.asyncio
async def test_get_all_challenge_answers():
    fake = [{"id": "42", "responses": {}}]
    with patch("services.async_firebase.firebase_service.get_all_challenge_answers", return_value=fake) as mock:
        result = await async_firebase.get_all_challenge_answers(10, "2026-04-16")
    mock.assert_called_once_with(10, "2026-04-16")
    assert result == fake


@pytest.mark.asyncio
async def test_close_challenge_atomic():
    fake = {"id": "2026-04-16", "status": "closed", "participants": {"42": 3}}
    with patch("services.async_firebase.firebase_service.close_challenge_atomic", return_value=fake) as mock:
        result = await async_firebase.close_challenge_atomic(10, "2026-04-16")
    mock.assert_called_once_with(10, "2026-04-16")
    assert result == fake


@pytest.mark.asyncio
async def test_get_active_challenges():
    fake = [{"group_id": "10", "date_str": "2026-04-16"}]
    with patch("services.async_firebase.firebase_service.get_active_challenges", return_value=fake) as mock:
        result = await async_firebase.get_active_challenges()
    mock.assert_called_once_with()
    assert result == fake


# ── Enriched Word Cache ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_enriched_word_doc():
    fake = {"word": "resilient", "phonetics": "/rI'zIlIent/"}
    with patch("services.async_firebase.firebase_service.get_enriched_word_doc", return_value=fake) as mock:
        result = await async_firebase.get_enriched_word_doc("resilient")
    mock.assert_called_once_with("resilient")
    assert result == fake


@pytest.mark.asyncio
async def test_set_enriched_word_doc():
    with patch("services.async_firebase.firebase_service.set_enriched_word_doc") as mock:
        await async_firebase.set_enriched_word_doc("resilient", {"phonetics": "x"})
    mock.assert_called_once_with("resilient", {"phonetics": "x"})


@pytest.mark.asyncio
async def test_update_enriched_word_example():
    example = {"sentence": "She is resilient."}
    with patch("services.async_firebase.firebase_service.update_enriched_word_example") as mock:
        await async_firebase.update_enriched_word_example("resilient", "B2", example)
    mock.assert_called_once_with("resilient", "B2", example)


# ── Leaderboard ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_leaderboard():
    fake = [{"id": "1", "total_words": 50}]
    with patch("services.async_firebase.firebase_service.get_leaderboard", return_value=fake) as mock:
        result = await async_firebase.get_leaderboard(10)
    mock.assert_called_once_with(10)
    assert result == fake
