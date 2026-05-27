import asyncio
import json
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from api.auth import get_current_user
from api.errors import ApiError, ERR
from api.models.vocabulary import (
    AddWordRequest,
    DailyExtraRequest,
    DailyGenerateRequest,
    DailyHistoryEntry,
    DailyHistoryResponse,
    DailyWord,
    DailyWordsResponse,
    VocabularyWord,
    WordListResponse,
)
from services import firebase_service, vocab_service, word_service
from services.srs_service import get_word_strength

router = APIRouter(prefix="/api/v1/vocabulary", tags=["vocabulary"])
logger = logging.getLogger(__name__)
EXTRA_DAILY_WORD_LIMIT = 5
EXTRA_DAILY_SOURCE = "extra"
VOCAB_SOURCE_BY_ID = {
    1: "daily",
    2: "quiz",
    3: "manual",
    4: "reading",
}
VOCAB_SOURCE_ID_BY_NAME = {name: source_id for source_id, name in VOCAB_SOURCE_BY_ID.items()}


def _vocab_source_label(raw: object) -> str:
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        return normalized if normalized in VOCAB_SOURCE_ID_BY_NAME else "daily"
    try:
        return VOCAB_SOURCE_BY_ID.get(int(raw or 1), "daily")
    except (TypeError, ValueError):
        return "daily"


def _parse_vocab_source_filter(source: str | None) -> int | None:
    if not source:
        return None
    normalized = source.strip().lower()
    if not normalized or normalized == "all":
        return None
    source_id = VOCAB_SOURCE_ID_BY_NAME.get(normalized)
    if source_id is None:
        raise ApiError(
            ERR.validation,
            field="source",
            allowed_sources=list(VOCAB_SOURCE_ID_BY_NAME),
        )
    return source_id


def _user_timezone(user: dict) -> str:
    tz_name = (user.get("timezone") or config.DEFAULT_TIMEZONE).strip()
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return config.DEFAULT_TIMEZONE
    return tz_name


def _local_date_str(tz_name: str) -> str:
    return datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")


def _next_reset_at(tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    return datetime.combine(today + timedelta(days=1), time.min, tzinfo=tz)


def _is_daily_word_reviewed(saved: dict) -> bool:
    return (
        int(saved.get("srs_reps") or 0) > 0
        or int(saved.get("times_correct") or 0) > 0
        or int(saved.get("times_incorrect") or 0) > 0
    )


def _to_vocab_word(doc: dict) -> VocabularyWord:
    return VocabularyWord(
        id=doc["id"],
        word=doc.get("word", ""),
        definition=doc.get("definition", ""),
        definition_vi=doc.get("definition_vi", ""),
        ipa=doc.get("ipa", ""),
        part_of_speech=doc.get("part_of_speech", ""),
        topic=doc.get("topic", ""),
        example_en=doc.get("example_en", ""),
        example_vi=doc.get("example_vi", ""),
        source=_vocab_source_label(doc.get("source")),
        srs_interval=doc.get("srs_interval", 0),
        srs_ease=doc.get("srs_ease", 2.5),
        srs_reps=doc.get("srs_reps", 0),
        srs_next_review=doc.get("srs_next_review"),
        times_correct=doc.get("times_correct", 0),
        times_incorrect=doc.get("times_incorrect", 0),
        strength=get_word_strength(doc),
        is_favourite=doc.get("is_favourite", False),
        added_at=doc.get("added_at"),
    )


def _to_daily_word(doc: dict) -> DailyWord:
    return DailyWord(
        word=doc.get("word", ""),
        word_id=doc.get("word_id", ""),
        daily_source=doc.get("daily_source", "daily"),
        reviewed=bool(doc.get("reviewed", False)),
        is_favourite=doc.get("is_favourite", False),
        strength=doc.get("strength", "New"),
        definition_en=doc.get("definition_en", doc.get("definition", "")),
        definition_vi=doc.get("definition_vi", ""),
        ipa=doc.get("ipa", ""),
        part_of_speech=doc.get("part_of_speech", ""),
        example_en=doc.get("example_en", doc.get("example", "")),
        example_vi=doc.get("example_vi", ""),
    )


def _persist_daily_to_deck(user_id: int, words: list[dict], topic: str) -> None:
    """Add each daily word to the user's vocab deck (idempotent via
    add_word_if_not_exists). Stamps word_id into the daily payload so
    downstream clients can target the word for quizzes/reviews.
    """
    for w in words:
        doc = {
            "word": w.get("word", ""),
            "definition": w.get("definition_en", w.get("definition", "")),
            "definition_vi": w.get("definition_vi", ""),
            "ipa": w.get("ipa", ""),
            "part_of_speech": w.get("part_of_speech", ""),
            "topic": topic,
            "example_en": w.get("example_en", w.get("example", "")),
            "example_vi": w.get("example_vi", ""),
        }
        if not doc["word"]:
            continue
        word_id, _ = firebase_service.add_word_if_not_exists(user_id, doc)
        w["word_id"] = word_id
        saved = firebase_service.get_word_by_id(user_id, word_id) or {}
        w["is_favourite"] = saved.get("is_favourite", False)
        w["strength"] = get_word_strength(saved)
        w["reviewed"] = _is_daily_word_reviewed(saved)


def _refresh_daily_word_status(user_id: int, words: list[dict]) -> list[dict]:
    refreshed = []
    for w in words:
        item = dict(w)
        word_id = item.get("word_id")
        if word_id:
            saved = firebase_service.get_word_by_id(user_id, word_id) or {}
            if saved:
                item["is_favourite"] = saved.get(
                    "is_favourite", item.get("is_favourite", False),
                )
                item["strength"] = get_word_strength(saved)
                item["reviewed"] = _is_daily_word_reviewed(saved)
        refreshed.append(item)
    return refreshed


def _reviewed_count(words: list[dict]) -> int:
    return sum(1 for w in words if w.get("reviewed"))


def _extra_used(words: list[dict]) -> int:
    return sum(1 for w in words if w.get("daily_source") == EXTRA_DAILY_SOURCE)


def _daily_response(
    date_str: str,
    topic: str,
    words: list[dict],
    timezone_name: str,
    generated_at: datetime | None = None,
) -> DailyWordsResponse:
    return DailyWordsResponse(
        date=date_str,
        topic=topic,
        words=[_to_daily_word(w) for w in words],
        generated_at=generated_at,
        reviewed_count=_reviewed_count(words),
        total_count=len(words),
        timezone=timezone_name,
        next_reset_at=_next_reset_at(timezone_name),
        extra_limit=EXTRA_DAILY_WORD_LIMIT,
        extra_used=_extra_used(words),
        extra_remaining=max(0, EXTRA_DAILY_WORD_LIMIT - _extra_used(words)),
    )


def _daily_history_entry(doc: dict, words: list[dict]) -> DailyHistoryEntry:
    return DailyHistoryEntry(
        date=doc.get("id", ""),
        topic=doc.get("topic", ""),
        words=[_to_daily_word(w) for w in words],
        generated_at=doc.get("generated_at"),
        total_count=len(words),
        reviewed_count=_reviewed_count(words),
        favourite_count=sum(1 for w in words if w.get("is_favourite")),
        weak_count=sum(1 for w in words if w.get("strength") == "Weak"),
        mastered_count=sum(1 for w in words if w.get("strength") == "Mastered"),
    )


def _daily_history_summary(doc: dict) -> DailyHistoryEntry:
    words = doc.get("words", []) or []
    return DailyHistoryEntry(
        date=doc.get("id", ""),
        topic=doc.get("topic", ""),
        words=[],
        generated_at=doc.get("generated_at"),
        total_count=len(words),
        reviewed_count=_reviewed_count(words),
        favourite_count=sum(1 for w in words if w.get("is_favourite")),
        weak_count=sum(1 for w in words if w.get("strength") == "Weak"),
        mastered_count=sum(1 for w in words if w.get("strength") == "Mastered"),
    )


def _daily_status_dict(
    reviewed_count: int,
    total_count: int,
    timezone_name: str,
    words: list[dict] | None = None,
) -> dict:
    extra_used = _extra_used(words or [])
    return {
        "reviewed_count": reviewed_count,
        "total_count": total_count,
        "timezone": timezone_name,
        "next_reset_at": _next_reset_at(timezone_name).isoformat(),
        "extra_limit": EXTRA_DAILY_WORD_LIMIT,
        "extra_used": extra_used,
        "extra_remaining": max(0, EXTRA_DAILY_WORD_LIMIT - extra_used),
    }


def _daily_word_dict(doc: dict) -> dict:
    """Normalize a raw word doc to the shape the frontend expects."""
    return {
        "word": doc.get("word", ""),
        "word_id": doc.get("word_id", ""),
        "daily_source": doc.get("daily_source", "daily"),
        "reviewed": bool(doc.get("reviewed", False)),
        "is_favourite": doc.get("is_favourite", False),
        "strength": doc.get("strength", "New"),
        "definition_en": doc.get("definition_en", doc.get("definition", "")),
        "definition_vi": doc.get("definition_vi", ""),
        "ipa": doc.get("ipa", ""),
        "part_of_speech": doc.get("part_of_speech", ""),
        "example_en": doc.get("example_en", doc.get("example", "")),
        "example_vi": doc.get("example_vi", ""),
    }


async def _daily_sse_generator(
    user_id: int,
    date_str: str,
    count: int,
    band: float,
    topics: list | None,
    timezone_name: str,
):
    def sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    try:
        cached = await asyncio.to_thread(
            firebase_service.get_user_daily_words, user_id, date_str
        )
        if cached:
            words = cached.get("words", []) or []
            topic = cached.get("topic", "")
            if words and any(not w.get("word_id") for w in words):
                await asyncio.to_thread(_persist_daily_to_deck, user_id, words, topic)
                await asyncio.to_thread(
                    firebase_service.save_user_daily_words,
                    user_id,
                    date_str,
                    words,
                    topic,
                )
            elif words and any("is_favourite" not in w for w in words if w.get("word_id")):
                await asyncio.to_thread(_persist_daily_to_deck, user_id, words, topic)
                await asyncio.to_thread(
                    firebase_service.save_user_daily_words,
                    user_id,
                    date_str,
                    words,
                    topic,
                )
            words = await asyncio.to_thread(_refresh_daily_word_status, user_id, words)
            yield sse({
                "type": "start",
                "count": len(words),
                "topic": topic,
                "date": date_str,
                "status": _daily_status_dict(
                    _reviewed_count(words), len(words), timezone_name, words,
                ),
            })
            for w in words:
                yield sse({"type": "word", "word": _daily_word_dict(w)})
            yield sse({"type": "done"})
            return

        accumulated: list[dict] = []
        topic_name = ""

        fav_words = await asyncio.to_thread(firebase_service.get_favourite_words, user_id, 10)

        async for event in vocab_service.stream_personal_daily_words(
            telegram_id=user_id, count=count, band=band, topics=topics,
            context_words=fav_words if len(fav_words) >= 3 else [],
        ):
            if event["type"] == "start":
                topic_name = event["topic"]
                total_count = int(event.get("count", count))
                yield sse({
                    **event,
                    "date": date_str,
                    "status": _daily_status_dict(0, total_count, timezone_name),
                })
            elif event["type"] == "word":
                word = event["word"]
                await asyncio.to_thread(
                    _persist_daily_to_deck, user_id, [word], topic_name,
                )
                accumulated.append(word)
                yield sse({"type": "word", "word": _daily_word_dict(word)})
            elif event["type"] == "done":
                if accumulated:
                    await asyncio.to_thread(
                        firebase_service.save_user_daily_words,
                        user_id, date_str, accumulated, topic_name,
                    )
                yield sse(event)

    except Exception as exc:
        logger.error("vocab stream failed for user %s: %s", user_id, exc, exc_info=True)
        yield sse({"type": "error", "code": "vocab.stream_failed"})


@router.post("/daily/stream")
async def stream_daily(
    body: DailyGenerateRequest | None = None,
    user: dict = Depends(get_current_user),
):
    """Stream today's personal daily words via SSE, one word at a time."""
    timezone_name = _user_timezone(user)
    date_str = _local_date_str(timezone_name)
    count = (body.count if body and body.count
             else int(user.get("daily_words_count") or config.DEFAULT_WORD_COUNT))
    topics = body.topics if body and body.topics else user.get("topics") or None
    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))

    return StreamingResponse(
        _daily_sse_generator(user["id"], date_str, count, band, topics, timezone_name),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=WordListResponse)
async def list_vocabulary(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, description="ISO-8601 added_at from previous page"),
    topic: str | None = Query(None, description="Filter to a single topic slug"),
    favourite: bool | None = Query(None, description="Filter to favourited words only"),
    source: str | None = Query(None, description="Filter to a vocabulary source"),
    user: dict = Depends(get_current_user),
) -> WordListResponse:
    """Paginated vocabulary list with SRS data, newest first.

    With ``?topic=<slug>``, results are scoped to that topic so each
    /learn/vocab/topic/:slug page paginates within its own bucket
    (US-#231 — drill-down navigation).
    """
    after = None
    if cursor:
        try:
            after = datetime.fromisoformat(cursor)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor format; expected ISO-8601 datetime.",
            )
    source_id = _parse_vocab_source_filter(source)

    docs = await asyncio.to_thread(
        firebase_service.get_user_vocabulary_page,
        user["id"], limit, after, topic, favourite, source_id,
    )
    items = [_to_vocab_word(d) for d in docs]
    next_cursor = None
    if len(items) == limit and items[-1].added_at is not None:
        next_cursor = items[-1].added_at.isoformat()
    return WordListResponse(items=items, next_cursor=next_cursor)


class _FavouriteBody(BaseModel):
    favourite: bool


@router.post("/{word_id}/favourite", status_code=status.HTTP_204_NO_CONTENT)
async def toggle_favourite(
    word_id: str,
    body: _FavouriteBody,
    user: dict = Depends(get_current_user),
) -> None:
    await asyncio.to_thread(
        firebase_service.toggle_favourite, user["id"], word_id, body.favourite
    )


@router.post("/daily", response_model=DailyWordsResponse)
async def generate_daily(
    body: DailyGenerateRequest | None = None,
    user: dict = Depends(get_current_user),
) -> DailyWordsResponse:
    """Generate (or return cached) today's personal daily words."""
    timezone_name = _user_timezone(user)
    date_str = _local_date_str(timezone_name)

    cached = await asyncio.to_thread(
        firebase_service.get_user_daily_words, user["id"], date_str
    )
    if cached:
        cached_words = cached.get("words", []) or []
        cached_topic = cached.get("topic", "")
        # Backfill word_ids for cached entries that predate this feature
        # (idempotent via add_word_if_not_exists).
        if cached_words and any(not w.get("word_id") for w in cached_words):
            await asyncio.to_thread(
                _persist_daily_to_deck, user["id"], cached_words, cached_topic
            )
            await asyncio.to_thread(
                firebase_service.save_user_daily_words,
                user["id"], date_str, cached_words, cached_topic,
            )
        cached_words = await asyncio.to_thread(
            _refresh_daily_word_status, user["id"], cached_words,
        )
        return _daily_response(
            date_str,
            cached_topic,
            cached_words,
            timezone_name,
            generated_at=cached.get("generated_at"),
        )

    count = (body.count if body and body.count
             else int(user.get("daily_words_count") or config.DEFAULT_WORD_COUNT))
    topics = (body.topics if body and body.topics else user.get("topics") or None)
    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    fav_words = await asyncio.to_thread(firebase_service.get_favourite_words, user["id"], 10)

    words, topic = await vocab_service.generate_personal_daily_words(
        telegram_id=user["id"], count=count, band=band, topics=topics,
        context_words=fav_words if len(fav_words) >= 3 else [],
    )

    await asyncio.to_thread(
        _persist_daily_to_deck, user["id"], words, topic
    )
    await asyncio.to_thread(
        firebase_service.save_user_daily_words, user["id"], date_str, words, topic
    )

    words = await asyncio.to_thread(_refresh_daily_word_status, user["id"], words)
    return _daily_response(
        date_str,
        topic,
        words,
        timezone_name,
        generated_at=datetime.utcnow(),
    )


def _detail_example(detail: dict, band: float) -> dict:
    examples = detail.get("examples_by_band", {}) or {}
    tier = word_service.band_tier(band)
    return examples.get(tier, {}) or {}


def _detail_to_daily_word(detail: dict, fallback: dict, band: float) -> dict:
    example = _detail_example(detail, band)
    return {
        "word": detail.get("word") or fallback.get("word", ""),
        "daily_source": EXTRA_DAILY_SOURCE,
        "definition_en": detail.get("definition_en", fallback.get("definition_en", "")),
        "definition_vi": detail.get("definition_vi", fallback.get("definition_vi", "")),
        "ipa": detail.get("ipa", fallback.get("ipa", "")),
        "part_of_speech": detail.get("part_of_speech", fallback.get("part_of_speech", "")),
        "example_en": example.get("en") or fallback.get("example_en", ""),
        "example_vi": example.get("vi") or fallback.get("example_vi", ""),
    }


async def _prepare_extra_daily_words(words: list[dict], band: float) -> list[dict]:
    prepared = []
    for word in words:
        word_text = (word.get("word") or "").strip()
        if not word_text:
            continue
        fast = await word_service.get_word_detail_fast(word_text, band)
        if fast is not None and word_service.is_word_core_detail_complete(fast, band):
            detail = fast
        else:
            detail = await word_service.get_complete_word_detail(word_text, band)
        prepared.append(_detail_to_daily_word(detail, word, band))
    return prepared


@router.post("/daily/extra", response_model=DailyWordsResponse)
async def add_extra_daily_words(
    body: DailyExtraRequest | None = None,
    user: dict = Depends(get_current_user),
) -> DailyWordsResponse:
    timezone_name = _user_timezone(user)
    date_str = _local_date_str(timezone_name)
    cached = await asyncio.to_thread(
        firebase_service.get_user_daily_words, user["id"], date_str
    )
    if not cached:
        raise ApiError(ERR.vocab_daily_not_found)

    words = cached.get("words", []) or []
    used = _extra_used(words)
    remaining = max(0, EXTRA_DAILY_WORD_LIMIT - used)
    if remaining <= 0:
        raise ApiError(
            ERR.vocab_extra_limit_exceeded,
            limit=EXTRA_DAILY_WORD_LIMIT,
            next_reset_at=_next_reset_at(timezone_name).isoformat(),
        )

    requested = body.count if body else EXTRA_DAILY_WORD_LIMIT
    count = min(requested, remaining)
    topic = cached.get("topic", "")
    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    selected = await vocab_service.generate_extra_daily_words(
        telegram_id=user["id"],
        count=count,
        band=band,
        topic=topic,
    )
    extra_words = await _prepare_extra_daily_words(selected, band)
    await asyncio.to_thread(_persist_daily_to_deck, user["id"], extra_words, topic)

    next_words = words + extra_words
    await asyncio.to_thread(
        firebase_service.save_user_daily_words,
        user["id"],
        date_str,
        next_words,
        topic,
    )
    refreshed = await asyncio.to_thread(
        _refresh_daily_word_status, user["id"], next_words,
    )
    return _daily_response(
        date_str,
        topic,
        refreshed,
        timezone_name,
        generated_at=cached.get("generated_at"),
    )


@router.post("", response_model=VocabularyWord)
async def add_word(
    body: AddWordRequest,
    user: dict = Depends(get_current_user),
) -> VocabularyWord:
    """Add a single word to the user's vocabulary with auto-enrichment.

    Used by the listening misheard-word → SRS bridge. Deduplicates by word
    atomically inside a Firestore transaction so concurrent clicks can't
    double-insert or double-increment total_words.
    """
    normalized = word_service.normalize_word(body.word)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Word cannot be empty.",
        )

    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    enriched = await word_service.get_enriched_word(normalized, band)

    tier = _band_tier(band)
    example = (enriched.get("examples_by_band", {}) or {}).get(tier, {}) or {}
    word_data = {
        "word": enriched.get("word", normalized),
        "definition": enriched.get("definition_en", ""),
        "definition_vi": enriched.get("definition_vi", ""),
        "ipa": enriched.get("ipa", ""),
        "part_of_speech": enriched.get("part_of_speech", ""),
        "topic": body.topic or "",
        "example_en": example.get("en", ""),
        "example_vi": example.get("vi", ""),
        "source": VOCAB_SOURCE_ID_BY_NAME["manual"],
    }

    word_id, created = await asyncio.to_thread(
        firebase_service.add_word_if_not_exists, user["id"], word_data
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Word already in vocabulary.",
        )
    doc = await asyncio.to_thread(
        firebase_service.get_word_by_id, user["id"], word_id
    )
    return _to_vocab_word(doc or {"id": word_id, **word_data})


@router.get("/daily/history", response_model=DailyHistoryResponse)
async def get_daily_history(
    limit: int = Query(30, ge=1, le=90),
    user: dict = Depends(get_current_user),
) -> DailyHistoryResponse:
    """Return cached daily-word batch summaries, newest first.

    The list intentionally omits per-word detail so /learn/vocab can render
    history quickly. Clients should fetch /daily/{date} only when a learner
    expands a day.
    """
    docs = await asyncio.to_thread(
        firebase_service.list_user_daily_words, user["id"], limit,
    )
    items = [_daily_history_summary(doc) for doc in docs]
    return DailyHistoryResponse(items=items, timezone=_user_timezone(user))


def _band_tier(band: float) -> str:
    if band >= 7.5:
        return "7.5+"
    if band >= 7.0:
        return "7.0"
    if band >= 6.5:
        return "6.5"
    return "6.0"


@router.get("/daily/{date}", response_model=DailyWordsResponse)
async def get_daily_by_date(
    date: str,
    user: dict = Depends(get_current_user),
) -> DailyWordsResponse:
    """Return cached daily words for a given date (YYYY-MM-DD)."""
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date; expected YYYY-MM-DD.",
        )

    cached = await asyncio.to_thread(
        firebase_service.get_user_daily_words, user["id"], date
    )
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No daily words cached for {date}.",
        )
    timezone_name = _user_timezone(user)
    words = await asyncio.to_thread(
        _refresh_daily_word_status, user["id"], cached.get("words", []),
    )
    return _daily_response(
        date,
        cached.get("topic", ""),
        words,
        timezone_name,
        generated_at=cached.get("generated_at"),
    )
