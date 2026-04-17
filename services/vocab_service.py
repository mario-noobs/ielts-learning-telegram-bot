import json
import logging
import random

from services import ai_service, firebase_service

logger = logging.getLogger(__name__)


async def generate_daily_words(group_id: int, count: int = 10,
                                band: float = 7.0,
                                topic: str = None) -> list[dict]:
    """Generate daily vocabulary words for a group.

    Picks a random topic from group settings if none specified.
    Excludes words already learned by group members.
    """
    # Get group settings for topic list
    group = firebase_service.get_group_settings(group_id)
    if not group:
        topics = ["education", "environment", "technology"]
    else:
        topics = group.get("topics", ["education", "environment", "technology"])
        if not band:
            band = group.get("default_band", 7.0)

    if not topic:
        # Load topic data for display name
        try:
            with open("data/ielts_topics.json", "r") as f:
                topic_data = json.load(f)
            topic_map = {t["id"]: t["name"] for t in topic_data["topics"]}
        except Exception:
            topic_map = {}
        topic_id = random.choice(topics)
        topic = topic_map.get(topic_id, topic_id)

    # Collect existing words from all group users to avoid duplicates
    users = firebase_service.get_all_users_in_group(group_id)
    existing = set()
    for user in users:
        words = firebase_service.get_user_word_list(int(user["id"]))
        existing.update(w.lower() for w in words)

    # Generate via AI
    words = await ai_service.generate_vocabulary(
        count=count, band=band, topic=topic,
        exclude_words=list(existing)[:100]
    )

    return words, topic


async def generate_personal_daily_words(telegram_id: int, count: int = 10,
                                         band: float = 7.0,
                                         topics: list = None) -> tuple[list, str]:
    """Generate personal daily words for a user's DM, using their own settings."""
    if not topics:
        topics = ["education", "environment", "technology"]

    # Load topic display name
    try:
        with open("data/ielts_topics.json", "r") as f:
            topic_data = json.load(f)
        topic_map = {t["id"]: t["name"] for t in topic_data["topics"]}
    except Exception:
        topic_map = {}
    topic_id = random.choice(topics)
    topic = topic_map.get(topic_id, topic_id)

    # Exclude words already in user's vocabulary
    existing_words = firebase_service.get_user_word_list(telegram_id)
    existing = set(w.lower() for w in existing_words)

    # Generate via AI
    words = await ai_service.generate_vocabulary(
        count=count, band=band, topic=topic,
        exclude_words=list(existing)[:100]
    )
    return words, topic


def _build_word_doc(word_data: dict, topic: str) -> dict:
    """Build a word document from AI-generated data."""
    return {
        "word": word_data.get("word", ""),
        "definition": word_data.get("definition_en", word_data.get("definition", "")),
        "definition_vi": word_data.get("definition_vi", ""),
        "ipa": word_data.get("ipa", ""),
        "part_of_speech": word_data.get("part_of_speech", ""),
        "example_en": word_data.get("example_en", word_data.get("example", "")),
        "example_vi": word_data.get("example_vi", ""),
        "topic": topic,
    }


async def save_daily_words_for_group(group_id: int, words: list,
                                      topic: str, date_str: str,
                                      caller_id: int = None):
    """Save daily words to group and add to each user's vocabulary."""
    # Save to group
    firebase_service.save_daily_words(group_id, date_str, words, topic)

    # Add words to each user in the group
    users = firebase_service.get_all_users_in_group(group_id)
    saved_user_ids = set()

    for user in users:
        user_id = int(user["id"])
        saved_user_ids.add(user_id)
        existing_vocab = set(
            w.lower() for w in firebase_service.get_user_word_list(user_id)
        )
        for word_data in words:
            if word_data.get("word", "").lower() not in existing_vocab:
                firebase_service.add_word_to_user(
                    user_id, _build_word_doc(word_data, topic)
                )

    # Always save to the caller even if group query missed them
    if caller_id and caller_id not in saved_user_ids:
        logger.warning(f"User {caller_id} not found in group {group_id} query, saving directly")
        firebase_service.update_user(caller_id, {"group_id": group_id})
        existing_vocab = set(
            w.lower() for w in firebase_service.get_user_word_list(caller_id)
        )
        for word_data in words:
            if word_data.get("word", "").lower() not in existing_vocab:
                firebase_service.add_word_to_user(
                    caller_id, _build_word_doc(word_data, topic)
                )


def format_daily_words(words: list, topic: str) -> list[str]:
    """Format daily vocabulary for display in Telegram.

    Format per word:
    1. Word /IPA/ (pos) ✨
    🇬🇧 EN: definition
    🇻🇳 VI: Vietnamese definition
    📌 Example:
    sentence
    → Vietnamese sentence

    Returns a list of message strings, each under 4096 chars.
    """
    header = f"\U0001f4da Daily IELTS Vocabulary - {topic}\n\n"
    footer = "\n\U0001f3a7 /audio <number> to hear pronunciation"

    messages = []
    current = header

    for i, w in enumerate(words, 1):
        word = w.get("word", "?")
        ipa = w.get("ipa", "")
        pos = w.get("part_of_speech", "")
        def_en = w.get("definition_en", w.get("definition", ""))
        def_vi = w.get("definition_vi", "")
        ex_en = w.get("example_en", w.get("example", ""))
        ex_vi = w.get("example_vi", "")

        entry = f"{i}. {word} {ipa} ({pos}) \u2728\n\n"
        entry += f"\U0001f1ec\U0001f1e7 EN: {def_en}\n"
        entry += f"\U0001f1fb\U0001f1f3 VI: {def_vi}\n" if def_vi else ""
        entry += "\n\U0001f4cc Example:\n"
        entry += f"{ex_en}\n" if ex_en else ""
        entry += f"\u2192 {ex_vi}\n" if ex_vi else ""
        entry += "\n"

        if len(current) + len(entry) > 3800:
            messages.append(current)
            current = entry
        else:
            current += entry

    current += footer
    messages.append(current)

    return messages
