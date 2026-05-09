import json
import logging
import random

from services import ai_service, firebase_service

logger = logging.getLogger(__name__)

# US-#226 — topic rotation. Picking a topic, we exclude the last
# RECENT_TOPICS_AVOID entries from the candidate pool. Stored as a
# bounded FIFO list on the group / user doc up to RECENT_TOPICS_KEEP.
RECENT_TOPICS_AVOID = 3
RECENT_TOPICS_KEEP = 5


def _load_topic_map() -> dict[str, str]:
    """topic_id → display name. Empty dict if the file is missing."""
    try:
        with open("data/ielts_topics.json", "r") as f:
            topic_data = json.load(f)
        return {t["id"]: t["name"] for t in topic_data["topics"]}
    except Exception:
        return {}


def _pick_topic_avoiding_recent(
    topics: list[str], recent_topics: list[str] | None,
) -> str:
    """Pick a topic id that wasn't used in the last N daily generations.

    Falls back to the full topic list when every candidate has been
    used recently — e.g. group has 3 topics and recent_topics ⊇ all 3.
    Always returns a topic id; raises ValueError only if `topics` is
    empty (caller bug).
    """
    if not topics:
        raise ValueError("topics list must be non-empty")
    avoid = set((recent_topics or [])[-RECENT_TOPICS_AVOID:])
    candidates = [t for t in topics if t not in avoid]
    if not candidates:
        candidates = topics
    return random.choice(candidates)


def _push_recent_topic(recent: list[str] | None, topic_id: str) -> list[str]:
    """Append topic_id to the FIFO list, capped at RECENT_TOPICS_KEEP."""
    out = list(recent or [])
    out.append(topic_id)
    return out[-RECENT_TOPICS_KEEP:]


def _filter_dupes_lc(words: list[dict], existing_lc: set[str]) -> list[dict]:
    """Drop AI-returned words that already exist in the user's vocab.

    Compare lowercase + stripped — Llama and Gemini both occasionally
    casefold "Ubiquitous" → "ubiquitous" or pad with whitespace.
    """
    out: list[dict] = []
    seen_in_batch: set[str] = set()
    for w in words:
        key = (w.get("word") or "").strip().lower()
        if not key or key in existing_lc or key in seen_in_batch:
            continue
        seen_in_batch.add(key)
        out.append(w)
    return out


async def _generate_with_dedup(
    *, count: int, band: float, topic: str, existing_lc: set[str],
    fallback_topic_id: str | None = None,
) -> list[dict]:
    """Call the AI, filter dupes, top up once if short.

    Pulled into a helper so group + personal flows share the dedup
    logic. The AI prompt receives the FULL exclude list (no `[:100]`
    cap) — Phase 1 prompt sizes haven't been an issue at our band.
    If we ever hit a token-budget ceiling we'll chunk; not yet.
    """
    primary = await ai_service.generate_vocabulary(
        count=count, band=band, topic=topic,
        exclude_words=list(existing_lc),
    )
    filtered = _filter_dupes_lc(primary, existing_lc)
    if len(filtered) >= count:
        return filtered[:count]

    # Top up: ask the AI for the missing slots, with everything we've
    # already accepted added to the exclude list. One retry only — we
    # don't want a runaway loop if the AI keeps regenerating dupes.
    needed = count - len(filtered)
    accepted_keys = {(w.get("word") or "").strip().lower() for w in filtered}
    extended_exclude = existing_lc | accepted_keys
    try:
        topup = await ai_service.generate_vocabulary(
            count=needed, band=band,
            topic=fallback_topic_id or topic,
            exclude_words=list(extended_exclude),
        )
        filtered.extend(_filter_dupes_lc(topup, extended_exclude))
    except Exception as exc:  # noqa: BLE001 — top-up best-effort
        logger.warning("Vocab top-up failed: %s — returning %d/%d words",
                       exc, len(filtered), count)
    # If we still come up short, return whatever we have rather than
    # blocking the user — better N-1 fresh words than a hard error.
    return filtered[:count]


async def generate_daily_words(group_id: int, count: int = 10,
                                band: float = 7.0,
                                topic: str = None) -> tuple[list, str]:
    """Generate daily vocabulary words for a group.

    Picks a topic from group settings using the avoid-last-N rotation
    (US-#226 bug 3). Excludes the FULL list of words already learned by
    group members (was capped at 100 — bug 2). Top-ups via one retry
    if the AI returns dupes after dedup.
    """
    group = firebase_service.get_group_settings(group_id)
    if not group:
        topics = ["education", "environment", "technology"]
    else:
        topics = group.get("topics", ["education", "environment", "technology"])
        if not band:
            band = group.get("default_band", 7.0)

    topic_map = _load_topic_map()
    topic_id: str | None = None
    if not topic:
        topic_id = _pick_topic_avoiding_recent(
            topics, (group or {}).get("recent_topics"),
        )
        topic = topic_map.get(topic_id, topic_id)

    # Collect existing words from all group users — full list, no cap.
    users = firebase_service.get_all_users_in_group(group_id)
    existing_lc: set[str] = set()
    for user in users:
        words = firebase_service.get_user_word_list(int(user["id"]))
        existing_lc.update(w.lower() for w in words)

    fresh = await _generate_with_dedup(
        count=count, band=band, topic=topic, existing_lc=existing_lc,
    )

    # Persist topic rotation state. Skip when the caller forced a
    # specific topic — the rotation only tracks router-selected ones.
    if topic_id is not None:
        recent = _push_recent_topic((group or {}).get("recent_topics"), topic_id)
        try:
            firebase_service.update_group_settings(
                group_id, {"recent_topics": recent},
            )
        except Exception:  # noqa: BLE001 — non-critical
            logger.exception("Failed to persist group recent_topics")

    return fresh, topic


async def generate_personal_daily_words(telegram_id: int, count: int = 10,
                                         band: float = 7.0,
                                         topics: list = None) -> tuple[list, str]:
    """Generate personal daily words for /mydaily DM.

    Same dedup + topic rotation as the group flow, but the recent-
    topics state lives on the user doc (`recent_personal_topics`) so
    /mydaily and /daily don't fight over the same FIFO.
    """
    if not topics:
        topics = ["education", "environment", "technology"]

    user = firebase_service.get_user(telegram_id) or {}
    recent = user.get("recent_personal_topics") or []
    topic_id = _pick_topic_avoiding_recent(topics, recent)
    topic = _load_topic_map().get(topic_id, topic_id)

    existing_words = firebase_service.get_user_word_list(telegram_id)
    existing_lc = set(w.lower() for w in existing_words)

    fresh = await _generate_with_dedup(
        count=count, band=band, topic=topic, existing_lc=existing_lc,
    )

    next_recent = _push_recent_topic(recent, topic_id)
    try:
        firebase_service.update_user(
            telegram_id, {"recent_personal_topics": next_recent},
        )
    except Exception:  # noqa: BLE001 — non-critical
        logger.exception("Failed to persist user recent_personal_topics")

    return fresh, topic


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
