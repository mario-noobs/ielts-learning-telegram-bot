import asyncio
import logging
import random
from datetime import datetime, timezone

from services import ai_service, firebase_service
from services.ai_service import RateLimitError

import config

logger = logging.getLogger(__name__)


async def create_daily_challenge(group_id: int) -> tuple[list, str]:
    """Generate a daily challenge for the group with retry on 429.

    Retries up to 2 times with 5s doubling backoff on RateLimitError.
    """
    group = firebase_service.get_group_settings(group_id)
    band = group.get("default_band", 7.0) if group else 7.0
    topics = group.get("topics", ["education"]) if group else ["education"]

    topic = random.choice(topics)

    # D3: retry with 5s doubling backoff, max 2 retries
    last_err = None
    for attempt in range(3):
        try:
            questions = await ai_service.generate_challenge(
                count=config.CHALLENGE_QUESTION_COUNT,
                band=band,
                topic=topic
            )
            break
        except RateLimitError as e:
            last_err = e
            if attempt < 2:
                delay = 5 * (2 ** attempt)  # 5s, 10s
                logger.warning(
                    f"Challenge generation 429 (attempt {attempt + 1}/3), "
                    f"retrying in {delay}s"
                )
                await asyncio.sleep(delay)
            else:
                raise
        except Exception:
            raise
    else:
        raise last_err

    date_str = config.local_date_str()
    firebase_service.save_challenge(group_id, date_str, questions)

    return questions, date_str


def format_challenge_post(date_str: str, bot_username: str, group_id: int,
                          topic: str = None, band: float = None) -> tuple[str, object]:
    """Build the group announcement message with a deep-link button.

    Returns (text, reply_markup) tuple.
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    topic_line = f" on {topic}" if topic else ""
    band_line = f" (Band {band})" if band else ""

    text = (
        f"\u26a1 *Daily IELTS Challenge* \u2014 {date_str}\n\n"
        f"5 questions{topic_line}{band_line}\n"
        f"\u23f0 You have {config.CHALLENGE_DEADLINE_MINUTES} minutes!\n\n"
        f"Tap the button below to start answering in our DM.\n"
        f"Finish all 5 to maximize your score!"
    )

    deep_link_url = f"https://t.me/{bot_username}?start=challenge_{group_id}_{date_str}"
    keyboard = [[InlineKeyboardButton(
        "\U0001f680 Start Challenge",
        url=deep_link_url
    )]]

    return text, InlineKeyboardMarkup(keyboard)


def is_challenge_expired(challenge: dict) -> bool:
    """Check if a challenge has passed its deadline."""
    expires_at = challenge.get("expires_at")
    if not expires_at:
        return False
    now = datetime.now(timezone.utc)
    if hasattr(expires_at, 'timestamp'):
        return now > expires_at
    return False


def close_and_score(group_id: int, date_str: str) -> dict:
    """Close a challenge atomically and return results.

    Shared function used by both the expiry job and /results handler.
    Returns a dict with 'participants', 'questions', 'status', or None.
    """
    return firebase_service.close_challenge_atomic(group_id, date_str)


def format_challenge_results(group_id: int, date_str: str) -> str:
    """Format challenge results with rankings."""
    challenge = firebase_service.get_challenge(group_id, date_str)
    if not challenge:
        return "No challenge found for today."

    # If still active and not expired, tell user to wait
    if challenge.get("status") != "closed" and not is_challenge_expired(challenge):
        expires_at = challenge.get("expires_at")
        if expires_at and hasattr(expires_at, 'timestamp'):
            now = datetime.now(timezone.utc)
            remaining = int((expires_at - now).total_seconds() / 60)
            return (
                f"\u26a1 Challenge still active! "
                f"{remaining} minutes remaining.\n\n"
                f"Use the deep-link button in the group to participate!"
            )
        return "\u26a1 Challenge still active!"

    # If expired but not closed, close it now
    if challenge.get("status") != "closed":
        result = close_and_score(group_id, date_str)
        if result:
            challenge = result

    return _build_results_text(challenge, date_str)


def _build_results_text(challenge: dict, date_str: str) -> str:
    """Build the formatted results text from a closed challenge."""
    participants = challenge.get("participants", {})
    total_q = len(challenge.get("questions", []))

    if not participants:
        return "\U0001f614 No one participated in today's challenge."

    # Sort by score descending
    sorted_p = sorted(participants.items(), key=lambda x: x[1], reverse=True)

    lines = [
        f"\U0001f3c6 *Daily Challenge Results* \u2014 {date_str}\n"
    ]

    medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
    for i, (user_id, score) in enumerate(sorted_p):
        user = firebase_service.get_user(int(user_id))
        name = user.get("name", "Unknown") if user else "Unknown"
        medal = medals[i] if i < 3 else f"  {i + 1}."
        lines.append(f"{medal} *{name}* \u2014 {score}/{total_q}")

    return "\n".join(lines)
