import json
import logging
import math
import random
import re
import unicodedata

from services import ai_service, firebase_service

logger = logging.getLogger(__name__)

VOCAB_BATCH_SIZE = 5  # max words per AI prompt — keeps output tokens ≤ ~3500
PRIVATE_CONTEXT_LIMIT = 10
PRIVATE_TOPIC_LIMIT = 3

# US-#226 — topic rotation. Picking a topic, we exclude the last
# RECENT_TOPICS_AVOID entries from the candidate pool. Stored as a
# bounded FIFO list on the group / user doc up to RECENT_TOPICS_KEEP.
RECENT_TOPICS_AVOID = 3
RECENT_TOPICS_KEEP = 5
MASTER_WORD_STATUSES = ("active", "candidate")
_PUNCT_RE = re.compile(r"[^\w\s-]", re.UNICODE)


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
        key = _normalize_word_key(w.get("word") or "")
        if not key or key in existing_lc or key in seen_in_batch:
            continue
        seen_in_batch.add(key)
        out.append(w)
    return out


def _normalize_word_key(word: str) -> str:
    if not word:
        return ""
    normalized = unicodedata.normalize("NFC", word).lower().strip()
    normalized = _PUNCT_RE.sub("", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _unique_word_context(
    *groups: list[str] | None,
    limit: int = PRIVATE_CONTEXT_LIMIT,
) -> list[str]:
    context: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for word in group or []:
            clean = str(word or "").strip()
            key = _normalize_word_key(clean)
            if not key or key in seen:
                continue
            seen.add(key)
            context.append(clean)
            if len(context) >= limit:
                return context
    return context


def _weighted_topics_with_private_context(
    topics: list[str], topic_counts: dict[str, int],
) -> list[str]:
    private_topics = [
        topic
        for topic, _count in sorted(
            topic_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if topic
    ][:PRIVATE_TOPIC_LIMIT]
    if not private_topics:
        return topics

    weighted: list[str] = []
    for topic in private_topics:
        weighted.extend([topic, topic])
    weighted.extend(topic for topic in topics if topic not in private_topics)
    return weighted


def _private_daily_context(telegram_id: int) -> tuple[list[str], dict[str, int]]:
    recent_words: list[str] = []
    topic_counts: dict[str, int] = {}
    try:
        topic_counts = firebase_service.count_words_by_topic(telegram_id)
    except Exception:  # noqa: BLE001 — context should never block daily generation
        logger.exception("Failed to load private vocab topic context")

    try:
        recent_docs = firebase_service.get_user_vocabulary_page(
            telegram_id,
            PRIVATE_CONTEXT_LIMIT,
            None,
            None,
            None,
            3,
        )
        recent_words = [doc.get("word", "") for doc in recent_docs]
    except Exception:  # noqa: BLE001 — context should never block daily generation
        logger.exception("Failed to load recent private vocab context")

    return _unique_word_context(recent_words), topic_counts


def _target_master_difficulty(band: float) -> int:
    if band >= 7.0:
        return 5
    if band >= 6.0:
        return 4
    return 3


def _select_master_words(
    *, count: int, topic: str, band: float, existing_lc: set[str],
) -> list[dict]:
    """Select reproducible public-source words before falling back to AI.

    The table may not exist in older local/prod environments during rollout;
    in that case we log and return an empty list so existing AI generation
    keeps working.
    """
    if count <= 0:
        return []
    try:
        from sqlalchemy import func, or_, select
        from sqlalchemy.exc import SQLAlchemyError

        from services.db import get_sync_session
        from services.db.models import Topic, VocabularyMaster
    except Exception as exc:  # noqa: BLE001
        logger.warning("vocab master unavailable: %s", exc)
        return []

    normalized_existing = {_normalize_word_key(w) for w in existing_lc if w}
    normalized_existing.discard("")
    target_difficulty = _target_master_difficulty(band)
    selected: list[dict] = []
    selected_keys: set[str] = set()

    def run_query(topic_id: int | None, limit: int) -> list:
        conditions = [
            VocabularyMaster.status.in_(MASTER_WORD_STATUSES),
            VocabularyMaster.normalized_word.notin_(normalized_existing | selected_keys),
        ]
        if topic_id is not None:
            conditions.append(VocabularyMaster.topic_id == topic_id)
        stmt = (
            select(VocabularyMaster)
            .where(*conditions)
            .order_by(
                func.abs(func.coalesce(VocabularyMaster.difficulty, target_difficulty) - target_difficulty),
                func.random(),
            )
            .limit(limit)
        )
        with get_sync_session() as session:
            return list(session.execute(stmt).scalars().all())

    try:
        with get_sync_session() as session:
            topic_row = session.execute(
                select(Topic.id).where(
                    or_(
                        func.lower(Topic.slug) == topic.strip().lower(),
                        func.lower(Topic.name_en) == topic.strip().lower(),
                    )
                )
            ).scalar_one_or_none()

        for row in run_query(topic_row, count):
            selected_keys.add(row.normalized_word)
            selected.append(_master_row_to_word(row))
        if len(selected) < count:
            for row in run_query(None, count - len(selected)):
                selected_keys.add(row.normalized_word)
                selected.append(_master_row_to_word(row))
    except SQLAlchemyError as exc:
        logger.warning("vocab master selection failed: %s", exc)
        return []

    return selected[:count]


def _master_row_to_word(row) -> dict:
    return {
        "word": row.word,
        "definition_en": row.definition_en,
        "definition_vi": row.definition_vi or "",
        "ipa": row.ipa or "",
        "part_of_speech": row.part_of_speech or "",
        "example_en": row.example_en,
        "example_vi": row.example_vi or "",
        "synonyms": row.synonyms or [],
        "source": row.source,
    }


async def _generate_with_dedup(
    *, count: int, band: float, topic: str, existing_lc: set[str],
    fallback_topic_id: str | None = None,  # kept for compat; unused
    context_words: list[str] | None = None,
    plan: str | None = None,
) -> list[dict]:
    """Generate words in VOCAB_BATCH_SIZE chunks, each with the growing
    exclude list, so the AI never repeats earlier words and output-token
    limits are never hit.
    """
    emitted_lc: set[str] = set(existing_lc)
    all_words: list[dict] = []

    context_topic = topic
    if context_words and len(context_words) >= 3:
        joined = ", ".join(context_words[:10])
        context_topic = f"{topic} [CONTEXT: The learner is interested in words related to: {joined}. Prefer semantically related words.]"

    max_batches = math.ceil(count / VOCAB_BATCH_SIZE) + 3
    empty_batches = 0
    for _ in range(max_batches):
        remaining = count - len(all_words)
        if remaining <= 0:
            break
        bs = min(VOCAB_BATCH_SIZE, remaining)
        try:
            batch = await ai_service.generate_vocabulary(
                count=bs, band=band, topic=context_topic,
                exclude_words=list(emitted_lc),
                plan=plan,
            )
        except Exception as exc:
            logger.warning("Vocab batch failed: %s — returning %d/%d words",
                           exc, len(all_words), count)
            break

        fresh = _filter_dupes_lc(batch, emitted_lc)
        dropped = len(batch or []) - len(fresh)
        if dropped:
            logger.info(
                "daily_vocab_duplicate_candidates_filtered",
                extra={"topic": topic, "dropped": dropped},
            )
        if not fresh:
            empty_batches += 1
            if empty_batches >= 2:
                break
            continue
        empty_batches = 0
        for w in fresh:
            key = _normalize_word_key(w.get("word") or "")
            if key:
                emitted_lc.add(key)
        all_words.extend(fresh)

    return all_words[:count]


async def _generate_with_master_first(
    *, count: int, band: float, topic: str, existing_lc: set[str],
    context_words: list[str] | None = None, plan: str | None = None,
) -> list[dict]:
    master_words = _select_master_words(
        count=count, topic=topic, band=band, existing_lc=existing_lc,
    )
    if len(master_words) >= count:
        logger.info(
            "daily_vocab_generation_source_mix",
            extra={"topic": topic, "source_master": count, "source_ai": 0},
        )
        return master_words[:count]

    emitted_lc = set(existing_lc)
    emitted_lc.update(_normalize_word_key(w.get("word", "")) for w in master_words)
    fallback = await _generate_with_dedup(
        count=count - len(master_words),
        band=band,
        topic=topic,
        existing_lc=emitted_lc,
        context_words=context_words,
        plan=plan,
    )
    logger.info(
        "daily_vocab_generation_source_mix",
        extra={
            "topic": topic,
            "source_master": len(master_words),
            "source_ai": len(fallback),
        },
    )
    return (master_words + fallback)[:count]


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
        existing_lc.update(_normalize_word_key(w) for w in words)

    fresh = await _generate_with_master_first(
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
                                         topics: list = None,
                                         context_words: list[str] | None = None) -> tuple[list, str]:
    """Generate personal daily words for /mydaily DM.

    Same dedup + topic rotation as the group flow, but the recent-
    topics state lives on the user doc (`recent_personal_topics`) so
    /mydaily and /daily don't fight over the same FIFO.
    """
    if not topics:
        topics = ["education", "environment", "technology"]

    user = firebase_service.get_user(telegram_id) or {}
    recent = user.get("recent_personal_topics") or []
    private_context_words, topic_counts = _private_daily_context(telegram_id)
    topics = _weighted_topics_with_private_context(topics, topic_counts)
    topic_id = _pick_topic_avoiding_recent(topics, recent)
    topic = _load_topic_map().get(topic_id, topic_id)

    existing_words = firebase_service.get_user_word_list(telegram_id)
    existing_lc = {_normalize_word_key(w) for w in existing_words}
    merged_context = _unique_word_context(context_words, private_context_words)

    fresh = await _generate_with_master_first(
        count=count, band=band, topic=topic, existing_lc=existing_lc,
        context_words=merged_context,
    )
    logger.info(
        "personal_daily_vocab_generated",
        extra={
            "user_id": telegram_id,
            "topic": topic,
            "requested_count": count,
            "generated_count": len(fresh),
            "existing_count": len(existing_lc),
            "context_count": len(merged_context),
            "private_topic_count": len(topic_counts),
        },
    )

    next_recent = _push_recent_topic(recent, topic_id)
    try:
        firebase_service.update_user(
            telegram_id, {"recent_personal_topics": next_recent},
        )
    except Exception:  # noqa: BLE001 — non-critical
        logger.exception("Failed to persist user recent_personal_topics")

    return fresh, topic


async def generate_extra_daily_words(
    telegram_id: int,
    count: int = 5,
    band: float = 7.0,
    topic: str = "education",
    context_words: list[str] | None = None,
) -> list[dict]:
    """Generate extra words for today's personal daily set.

    Uses the same master-bank-first selector as default daily generation,
    but keeps the caller's current topic and does not rotate recent topics.
    """
    existing_words = firebase_service.get_user_word_list(telegram_id)
    existing_lc = {_normalize_word_key(w) for w in existing_words}
    private_context_words, _topic_counts = _private_daily_context(telegram_id)
    merged_context = _unique_word_context(context_words, private_context_words)
    return await _generate_with_master_first(
        count=count,
        band=band,
        topic=topic,
        existing_lc=existing_lc,
        context_words=merged_context,
    )


async def generate_import_candidates(
    *,
    mode: str,
    input_text: str,
    count: int,
    band: float,
    exclude_words: list[str] | None = None,
    plan: str | None = None,
) -> list[dict]:
    """Generate unsaved candidate words for topic/text import."""
    if mode == "topic":
        return await ai_service.generate_vocabulary(
            count=count,
            band=band,
            topic=input_text,
            exclude_words=exclude_words or [],
            plan=plan,
        )

    exclude_clause = ""
    if exclude_words:
        exclude_clause = (
            "Do NOT include these already-saved words: "
            f"{', '.join(exclude_words[:100])}."
        )
    prompt = f"""Extract {count} IELTS-relevant vocabulary items from this English text for a Band {band} learner.

{exclude_clause}

Rules:
- Prefer important academic, topic-specific, or collocation-friendly words and short phrases.
- Do not invent words that are unrelated to the text.
- Every word must be unique.
- definition_en: max 15 words.
- definition_vi and example_vi are required Vietnamese translations.
- example_en must be a short sentence using the word naturally.
- Return JSON only.

Text:
\"\"\"{input_text}\"\"\"

Return ONLY this JSON format:
[
  {{
    "word": "resilience",
    "ipa": "/rɪˈzɪliəns/",
    "part_of_speech": "noun",
    "definition_en": "ability to recover after difficulty",
    "definition_vi": "khả năng phục hồi sau khó khăn",
    "example_en": "Urban resilience is vital during climate emergencies.",
    "example_vi": "Khả năng phục hồi đô thị rất quan trọng trong khủng hoảng khí hậu.",
    "ielts_tip": "Use it in essays about cities, health, or climate."
  }}
]"""
    result = await ai_service.generate_json(prompt, plan=plan, quality="cheap")
    return result if isinstance(result, list) else []


async def stream_personal_daily_words(
    telegram_id: int,
    count: int = 10,
    band: float = 7.0,
    topics: list | None = None,
    plan: str | None = None,
    context_words: list[str] | None = None,
):
    """Async generator: yields SSE event dicts for /vocabulary/daily/stream.

    Splits the request into VOCAB_BATCH_SIZE-word batches run sequentially.
    Each batch receives the growing exclude list so the AI never repeats words
    from earlier batches. The API route persists each yielded word before it
    is sent to the client.

    Event shapes:
      {"type": "start", "count": N, "topic": "...", "date": "YYYY-MM-DD"}
      {"type": "word",  "word": {word fields + word_id}}
      {"type": "done"}
    """
    import config as _config

    if not topics:
        topics = ["education", "environment", "technology"]

    user = firebase_service.get_user(telegram_id) or {}
    recent = user.get("recent_personal_topics") or []
    private_context_words, topic_counts = _private_daily_context(telegram_id)
    topics = _weighted_topics_with_private_context(topics, topic_counts)
    topic_id = _pick_topic_avoiding_recent(topics, recent)
    topic = _load_topic_map().get(topic_id, topic_id)

    existing_words = firebase_service.get_user_word_list(telegram_id)
    existing_lc: set[str] = {_normalize_word_key(w) for w in existing_words}
    merged_context = _unique_word_context(context_words, private_context_words)

    date_str = _config.local_date_str()
    yield {"type": "start", "count": count, "topic": topic, "date": date_str}

    emitted_lc = set(existing_lc)
    emitted_count = 0
    master_count = 0
    ai_count = 0

    master_words = _select_master_words(
        count=count,
        topic=topic,
        band=band,
        existing_lc=emitted_lc,
    )
    for word in _filter_dupes_lc(master_words, emitted_lc):
        if emitted_count >= count:
            break
        key = _normalize_word_key(word.get("word") or "")
        if not key:
            continue
        emitted_lc.add(key)
        emitted_count += 1
        master_count += 1
        yield {"type": "word", "word": word}

    context_topic = topic
    if merged_context and len(merged_context) >= 3:
        joined = ", ".join(merged_context[:10])
        context_topic = f"{topic} [CONTEXT: The learner is interested in words related to: {joined}. Prefer semantically related words.]"

    max_batches = math.ceil(max(0, count - emitted_count) / VOCAB_BATCH_SIZE) + 3
    empty_batches = 0
    for _ in range(max_batches):
        remaining = count - emitted_count
        if remaining <= 0:
            break
        batch_size = min(VOCAB_BATCH_SIZE, remaining)
        try:
            batch = await ai_service.generate_vocabulary(
                count=batch_size,
                band=band,
                topic=context_topic,
                exclude_words=list(emitted_lc),
                plan=plan,
            )
        except Exception as exc:
            logger.warning(
                "Vocab stream batch failed: %s — returning %d/%d words",
                exc,
                emitted_count,
                count,
            )
            break

        fresh = _filter_dupes_lc(batch, emitted_lc)
        dropped = len(batch or []) - len(fresh)
        if dropped:
            logger.info(
                "daily_vocab_duplicate_candidates_filtered",
                extra={"topic": topic, "dropped": dropped},
            )
        if not fresh:
            empty_batches += 1
            if empty_batches >= 2:
                break
            continue

        empty_batches = 0
        for word in fresh:
            if emitted_count >= count:
                break
            key = _normalize_word_key(word.get("word") or "")
            if not key:
                continue
            emitted_lc.add(key)
            emitted_count += 1
            ai_count += 1
            yield {"type": "word", "word": word}

    logger.info(
        "daily_vocab_generation_source_mix",
        extra={"topic": topic, "source_master": master_count, "source_ai": ai_count},
    )

    next_recent = _push_recent_topic(recent, topic_id)
    try:
        firebase_service.update_user(telegram_id, {"recent_personal_topics": next_recent})
    except Exception:
        logger.exception("Failed to persist user recent_personal_topics")

    yield {"type": "done"}


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
