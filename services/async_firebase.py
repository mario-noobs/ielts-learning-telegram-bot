"""Async wrappers around firebase_service for use in FastAPI route handlers.

Every public function from firebase_service is wrapped with
``asyncio.to_thread()`` so that the synchronous Firestore SDK calls
run in a thread-pool executor without blocking the event loop.

The Telegram bot continues to import ``firebase_service`` directly --
this module is only consumed by the FastAPI layer.
"""

import asyncio
from typing import Optional

from services import firebase_service

# ── User Operations ──────────────────────────────────────────────────

async def get_user(telegram_id: int) -> Optional[dict]:
    return await asyncio.to_thread(firebase_service.get_user, telegram_id)


async def create_user(
    telegram_id: int,
    name: str,
    username: str = "",
    group_id: int = None,
    target_band: float = 7.0,
    topics: list = None,
) -> dict:
    return await asyncio.to_thread(
        firebase_service.create_user,
        telegram_id, name,
        username=username,
        group_id=group_id,
        target_band=target_band,
        topics=topics,
    )


async def update_user(telegram_id: int, data: dict):
    return await asyncio.to_thread(firebase_service.update_user, telegram_id, data)


async def get_all_users_in_group(group_id: int) -> list[dict]:
    return await asyncio.to_thread(firebase_service.get_all_users_in_group, group_id)


async def get_all_users() -> list[dict]:
    return await asyncio.to_thread(firebase_service.get_all_users)


async def update_streak(telegram_id: int):
    return await asyncio.to_thread(firebase_service.update_streak, telegram_id)


# ── Vocabulary Operations ────────────────────────────────────────────

async def add_word_to_user(telegram_id: int, word_data: dict) -> str:
    return await asyncio.to_thread(
        firebase_service.add_word_to_user, telegram_id, word_data,
    )


async def get_user_vocabulary(telegram_id: int, limit: int = 50) -> list[dict]:
    return await asyncio.to_thread(
        firebase_service.get_user_vocabulary, telegram_id, limit,
    )


async def get_user_word_list(telegram_id: int) -> list[str]:
    return await asyncio.to_thread(firebase_service.get_user_word_list, telegram_id)


async def get_mastered_words(telegram_id: int) -> list[dict]:
    return await asyncio.to_thread(firebase_service.get_mastered_words, telegram_id)


async def get_due_words(telegram_id: int, limit: int = 10) -> list[dict]:
    return await asyncio.to_thread(
        firebase_service.get_due_words, telegram_id, limit,
    )


async def update_word_srs(telegram_id: int, word_id: str, data: dict):
    return await asyncio.to_thread(
        firebase_service.update_word_srs, telegram_id, word_id, data,
    )


async def get_word_by_id(telegram_id: int, word_id: str) -> Optional[dict]:
    return await asyncio.to_thread(
        firebase_service.get_word_by_id, telegram_id, word_id,
    )


# ── Quiz History ─────────────────────────────────────────────────────

async def save_quiz_result(telegram_id: int, quiz_data: dict):
    return await asyncio.to_thread(
        firebase_service.save_quiz_result, telegram_id, quiz_data,
    )


async def get_latest_quiz(telegram_id: int) -> Optional[dict]:
    return await asyncio.to_thread(firebase_service.get_latest_quiz, telegram_id)


async def get_quiz_stats(telegram_id: int) -> dict:
    return await asyncio.to_thread(firebase_service.get_quiz_stats, telegram_id)


# ── Writing History ──────────────────────────────────────────────────

async def save_writing(telegram_id: int, writing_data: dict):
    return await asyncio.to_thread(
        firebase_service.save_writing, telegram_id, writing_data,
    )


# ── Group Operations ─────────────────────────────────────────────────

async def get_group_settings(group_id: int) -> Optional[dict]:
    return await asyncio.to_thread(firebase_service.get_group_settings, group_id)


async def create_group(group_id: int, settings: dict = None):
    return await asyncio.to_thread(
        firebase_service.create_group, group_id, settings=settings,
    )


async def update_group_settings(group_id: int, data: dict):
    return await asyncio.to_thread(
        firebase_service.update_group_settings, group_id, data,
    )


async def get_all_groups() -> list[dict]:
    return await asyncio.to_thread(firebase_service.get_all_groups)


# ── Daily Words (Group) ─────────────────────────────────────────────

async def save_daily_words(group_id: int, date_str: str, words: list, topic: str):
    return await asyncio.to_thread(
        firebase_service.save_daily_words, group_id, date_str, words, topic,
    )


async def get_daily_words(group_id: int, date_str: str) -> Optional[dict]:
    return await asyncio.to_thread(
        firebase_service.get_daily_words, group_id, date_str,
    )


# ── User Daily Words (DM) ───────────────────────────────────────────

async def save_user_daily_words(
    telegram_id: int, date_str: str, words: list, topic: str,
):
    return await asyncio.to_thread(
        firebase_service.save_user_daily_words, telegram_id, date_str, words, topic,
    )


async def get_user_daily_words(telegram_id: int, date_str: str) -> Optional[dict]:
    return await asyncio.to_thread(
        firebase_service.get_user_daily_words, telegram_id, date_str,
    )


# ── Challenge (Group) ───────────────────────────────────────────────

async def save_challenge(
    group_id: int,
    date_str: str,
    questions: list,
    deadline_minutes: int = None,
):
    return await asyncio.to_thread(
        firebase_service.save_challenge,
        group_id, date_str, questions,
        deadline_minutes=deadline_minutes,
    )


async def get_challenge(group_id: int, date_str: str) -> Optional[dict]:
    return await asyncio.to_thread(
        firebase_service.get_challenge, group_id, date_str,
    )


async def update_challenge_score(
    group_id: int, date_str: str, user_id: int, score: int,
):
    return await asyncio.to_thread(
        firebase_service.update_challenge_score,
        group_id, date_str, user_id, score,
    )


# ── Challenge Answers ────────────────────────────────────────────────

async def save_challenge_answer(
    group_id: int, date_str: str, user_id: int, q_idx: int, is_correct: bool,
):
    return await asyncio.to_thread(
        firebase_service.save_challenge_answer,
        group_id, date_str, user_id, q_idx, is_correct,
    )


async def mark_challenge_answer_complete(
    group_id: int, date_str: str, user_id: int,
):
    return await asyncio.to_thread(
        firebase_service.mark_challenge_answer_complete,
        group_id, date_str, user_id,
    )


async def get_user_challenge_answers(
    group_id: int, date_str: str, user_id: int,
) -> Optional[dict]:
    return await asyncio.to_thread(
        firebase_service.get_user_challenge_answers,
        group_id, date_str, user_id,
    )


async def get_all_challenge_answers(group_id: int, date_str: str) -> list[dict]:
    return await asyncio.to_thread(
        firebase_service.get_all_challenge_answers, group_id, date_str,
    )


async def close_challenge_atomic(group_id: int, date_str: str) -> Optional[dict]:
    return await asyncio.to_thread(
        firebase_service.close_challenge_atomic, group_id, date_str,
    )


async def get_active_challenges() -> list[dict]:
    return await asyncio.to_thread(firebase_service.get_active_challenges)


# ── Enriched Word Cache ─────────────────────────────────────────────

async def get_enriched_word_doc(word: str) -> Optional[dict]:
    return await asyncio.to_thread(firebase_service.get_enriched_word_doc, word)


async def set_enriched_word_doc(word: str, data: dict):
    return await asyncio.to_thread(
        firebase_service.set_enriched_word_doc, word, data,
    )


async def update_enriched_word_example(word: str, band_tier: str, example: dict):
    return await asyncio.to_thread(
        firebase_service.update_enriched_word_example, word, band_tier, example,
    )


# ── Leaderboard ──────────────────────────────────────────────────────

async def get_leaderboard(group_id: int) -> list[dict]:
    return await asyncio.to_thread(firebase_service.get_leaderboard, group_id)
