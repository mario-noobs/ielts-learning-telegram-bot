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
    ImportWordsRequest,
    ImportWordsResponse,
    PublicVocabPoolDetailResponse,
    PublicVocabPoolsResponse,
    VocabularyDraftResponse,
    VocabularyWord,
    WordListResponse,
)
from services import (
    feature_flag_service,
    firebase_service,
    public_vocab_pool_service,
    vocab_service,
    word_service,
)
from services.admin import quota_service
from services.srs_service import get_word_strength

router = APIRouter(prefix="/api/v1/vocabulary", tags=["vocabulary"])
logger = logging.getLogger(__name__)
EXTRA_DAILY_WORD_LIMIT = 5
EXTRA_DAILY_SOURCE = "extra"
PUBLIC_POOLS_FLAG = "public_vocab_pools"
VOCAB_LIMITS_BY_PLAN = {
    "free": {
        "max_private_words": 100,
        "max_import_candidates": 5,
        "max_import_input_chars": 1000,
    },
    "personal_pro": {
        "max_private_words": 1000,
        "max_import_candidates": 20,
        "max_import_input_chars": 3000,
    },
    "team_member": {
        "max_private_words": 5000,
        "max_import_candidates": 30,
        "max_import_input_chars": 5000,
    },
    "org_member": {
        "max_private_words": 10000,
        "max_import_candidates": 30,
        "max_import_input_chars": 5000,
    },
}
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


def _vocab_limits(plan: str | None) -> dict[str, int]:
    return VOCAB_LIMITS_BY_PLAN.get(plan or "free", VOCAB_LIMITS_BY_PLAN["free"])


def _public_pools_enabled(user: dict) -> bool:
    uid = str(user.get("auth_uid") or user.get("id") or "")
    return feature_flag_service.is_enabled(PUBLIC_POOLS_FLAG, uid)


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


def _daily_vocab_doc(word: dict, topic: str) -> dict:
    return {
        "word": word.get("word", ""),
        "definition": word.get("definition_en", word.get("definition", "")),
        "definition_vi": word.get("definition_vi", ""),
        "ipa": word.get("ipa", ""),
        "part_of_speech": word.get("part_of_speech", ""),
        "topic": topic,
        "example_en": word.get("example_en", word.get("example", "")),
        "example_vi": word.get("example_vi", ""),
    }


def _persist_daily_to_deck(user_id: int | str, words: list[dict], topic: str) -> None:
    """Add each daily word to the user's vocab deck (idempotent via
    add_word_if_not_exists). Stamps word_id into the daily payload so
    downstream clients can target the word for quizzes/reviews.
    """
    for w in words:
        doc = _daily_vocab_doc(w, topic)
        if not doc["word"]:
            continue
        word_id, _ = firebase_service.add_word_if_not_exists(user_id, doc)
        w["word_id"] = word_id
        saved = firebase_service.get_word_by_id(user_id, word_id) or {}
        w["is_favourite"] = saved.get("is_favourite", False)
        w["strength"] = get_word_strength(saved)
        w["reviewed"] = _is_daily_word_reviewed(saved)


def _refresh_daily_word_status(
    user_id: int | str,
    words: list[dict],
    topic: str = "",
) -> tuple[list[dict], bool]:
    refreshed = []
    changed = False
    for w in words:
        item = dict(w)
        word_id = item.get("word_id")
        saved = firebase_service.get_word_by_id(user_id, word_id) if word_id else None
        if not saved and item.get("word"):
            doc = _daily_vocab_doc(item, topic or item.get("topic", ""))
            word_id, _ = firebase_service.add_word_if_not_exists(user_id, doc)
            item["word_id"] = word_id
            saved = firebase_service.get_word_by_id(user_id, word_id) or {}
            changed = True
        if word_id:
            if saved:
                item["is_favourite"] = saved.get(
                    "is_favourite", item.get("is_favourite", False),
                )
                item["strength"] = get_word_strength(saved)
                item["reviewed"] = _is_daily_word_reviewed(saved)
        refreshed.append(item)
    return refreshed, changed


@router.get("/public-pools", response_model=PublicVocabPoolsResponse)
async def list_public_vocab_pools(
    difficulty: int | None = Query(default=None, ge=1, le=5),
    topic: str | None = Query(default=None, min_length=1, max_length=80),
    user: dict = Depends(get_current_user),
) -> PublicVocabPoolsResponse:
    if not _public_pools_enabled(user):
        return PublicVocabPoolsResponse(enabled=False, items=[])
    items = await asyncio.to_thread(
        public_vocab_pool_service.list_public_pools,
        difficulty=difficulty,
        topic=topic,
    )
    return PublicVocabPoolsResponse(enabled=True, items=items)


@router.get("/public-pools/{pool_id}", response_model=PublicVocabPoolDetailResponse)
async def get_public_vocab_pool(
    pool_id: str,
    difficulty: int | None = Query(default=None, ge=1, le=5),
    topic: str | None = Query(default=None, min_length=1, max_length=80),
    user: dict = Depends(get_current_user),
) -> PublicVocabPoolDetailResponse:
    if not _public_pools_enabled(user):
        raise ApiError(ERR.forbidden)
    try:
        detail = await asyncio.to_thread(
            public_vocab_pool_service.get_public_pool_detail,
            pool_id,
            difficulty=difficulty,
            topic=topic,
        )
    except ValueError:
        raise ApiError(ERR.not_found)
    if detail is None:
        raise ApiError(ERR.not_found)
    return PublicVocabPoolDetailResponse(enabled=True, **detail)


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
            words, changed = await asyncio.to_thread(
                _refresh_daily_word_status, user_id, words, topic
            )
            if changed:
                await asyncio.to_thread(
                    firebase_service.save_user_daily_words,
                    user_id,
                    date_str,
                    words,
                    topic,
                )
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
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
        cached_words, changed = await asyncio.to_thread(
            _refresh_daily_word_status, user["id"], cached_words, cached_topic,
        )
        if changed:
            await asyncio.to_thread(
                firebase_service.save_user_daily_words,
                user["id"], date_str, cached_words, cached_topic,
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

    words, _ = await asyncio.to_thread(
        _refresh_daily_word_status, user["id"], words, topic
    )
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


def _word_data_from_detail(
    detail: dict,
    normalized: str,
    band: float,
    topic: str = "",
) -> dict:
    examples = detail.get("examples_by_band", {}) or {}
    example = (
        examples.get(_band_tier(band))
        or examples.get(word_service.band_tier(band))
        or next(iter(examples.values()), {})
        or {}
    )
    return {
        "word": detail.get("word", normalized),
        "definition": detail.get("definition_en", ""),
        "definition_vi": detail.get("definition_vi", ""),
        "ipa": detail.get("ipa", ""),
        "part_of_speech": detail.get("part_of_speech", ""),
        "topic": topic or "",
        "example_en": example.get("en", ""),
        "example_vi": example.get("vi", ""),
        "source": VOCAB_SOURCE_ID_BY_NAME["manual"],
    }


def _word_data_from_request(body: AddWordRequest, normalized: str) -> dict:
    return {
        "word": body.word.strip() or normalized,
        "definition": body.definition,
        "definition_vi": body.definition_vi,
        "ipa": body.ipa,
        "part_of_speech": body.part_of_speech,
        "topic": body.topic or "",
        "example_en": body.example_en,
        "example_vi": body.example_vi,
        "source": VOCAB_SOURCE_ID_BY_NAME["manual"],
    }


def _draft_from_word_data(
    data: dict,
    *,
    already_exists: bool = False,
    existing_word_id: str | None = None,
    ielts_tip: str = "",
) -> VocabularyDraftResponse:
    return VocabularyDraftResponse(
        word=data.get("word", ""),
        definition=data.get("definition", data.get("definition_en", "")),
        definition_vi=data.get("definition_vi", ""),
        ipa=data.get("ipa", ""),
        part_of_speech=data.get("part_of_speech", ""),
        topic=data.get("topic", ""),
        example_en=data.get("example_en", ""),
        example_vi=data.get("example_vi", ""),
        ielts_tip=ielts_tip,
        already_exists=already_exists,
        existing_word_id=existing_word_id,
    )


def _candidate_from_generated(
    raw: dict,
    *,
    topic: str = "",
    existing_word_id: str | None = None,
) -> VocabularyDraftResponse | None:
    word = str(raw.get("word") or "").strip()
    if not word:
        return None
    return VocabularyDraftResponse(
        word=word,
        definition=raw.get("definition_en", raw.get("definition", "")) or "",
        definition_vi=raw.get("definition_vi", "") or "",
        ipa=raw.get("ipa", "") or "",
        part_of_speech=raw.get("part_of_speech", "") or "",
        topic=topic,
        example_en=raw.get("example_en", "") or "",
        example_vi=raw.get("example_vi", "") or "",
        ielts_tip=raw.get("ielts_tip", "") or "",
        already_exists=existing_word_id is not None,
        existing_word_id=existing_word_id,
    )


async def _enforce_private_vocab_cap(user: dict, normalized: str) -> None:
    existing = await asyncio.to_thread(
        firebase_service.get_word_by_text, user["id"], normalized,
    )
    if existing:
        raise ApiError(ERR.vocab_word_duplicate, word=normalized)

    limits = _vocab_limits(user.get("plan", "free"))
    used = await asyncio.to_thread(
        firebase_service.count_user_vocabulary, user["id"],
    )
    cap = limits["max_private_words"]
    if used >= cap:
        logger.info(
            "vocab private word cap blocked user=%s plan=%s used=%s cap=%s",
            user["id"], user.get("plan", "free"), used, cap,
        )
        raise ApiError(
            ERR.vocab_private_word_limit_exceeded,
            plan=user.get("plan", "free"),
            limit=cap,
            used=used,
        )


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
    refreshed, changed = await asyncio.to_thread(
        _refresh_daily_word_status, user["id"], next_words, topic,
    )
    if changed:
        await asyncio.to_thread(
            firebase_service.save_user_daily_words,
            user["id"],
            date_str,
            refreshed,
            topic,
        )
    return _daily_response(
        date_str,
        topic,
        refreshed,
        timezone_name,
        generated_at=cached.get("generated_at"),
    )


@router.post("/draft", response_model=VocabularyDraftResponse)
async def draft_word(
    body: AddWordRequest,
    user: dict = Depends(get_current_user),
) -> VocabularyDraftResponse:
    """Create an IELTS-focused preview card without saving it."""
    normalized = word_service.normalize_word(body.word)
    if not normalized:
        raise ApiError(ERR.vocab_word_empty)

    existing = await asyncio.to_thread(
        firebase_service.get_word_by_text, user["id"], normalized
    )
    if existing:
        return _draft_from_word_data(
            existing,
            already_exists=True,
            existing_word_id=existing.get("id"),
        )

    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    detail = await word_service.get_word_detail_fast(normalized, band)
    if detail is None or not word_service.is_word_core_detail_complete(detail, band):
        quota_service.check_and_increment(
            user_uid=str(user["id"]),
            feature="vocab",
            plan=user.get("plan", "free"),
            quota_override=user.get("quota_override"),
        )
        detail = await word_service.get_complete_word_detail(normalized, band)

    data = _word_data_from_detail(detail, normalized, band, body.topic)
    return _draft_from_word_data(data, ielts_tip=detail.get("ielts_tip", ""))


@router.post("/import/draft", response_model=ImportWordsResponse)
async def draft_import_words(
    body: ImportWordsRequest,
    user: dict = Depends(get_current_user),
) -> ImportWordsResponse:
    """Generate unsaved candidates from a topic or English text."""
    raw_input = body.input.strip()
    if not raw_input:
        raise ApiError(ERR.vocab_word_empty)

    limits = _vocab_limits(user.get("plan", "free"))
    if len(raw_input) > limits["max_import_input_chars"]:
        raise ApiError(
            ERR.vocab_import_input_too_long,
            max_chars=limits["max_import_input_chars"],
            got=len(raw_input),
        )
    if body.count > limits["max_import_candidates"]:
        raise ApiError(
            ERR.vocab_import_count_exceeded,
            max_candidates=limits["max_import_candidates"],
            got=body.count,
        )

    quota_service.check_and_increment(
        user_uid=str(user["id"]),
        feature="vocab",
        plan=user.get("plan", "free"),
        quota_override=user.get("quota_override"),
    )
    existing_words = await asyncio.to_thread(
        firebase_service.get_user_word_list, user["id"],
    )
    existing_by_norm = {
        word_service.normalize_word(word): word
        for word in existing_words
        if word_service.normalize_word(word)
    }
    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    generated = await vocab_service.generate_import_candidates(
        mode=body.mode,
        input_text=raw_input,
        count=body.count,
        band=band,
        exclude_words=existing_words,
        plan=user.get("plan", "free"),
    )

    candidates: list[VocabularyDraftResponse] = []
    seen: set[str] = set()
    for item in generated:
        normalized = word_service.normalize_word(str(item.get("word") or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        existing_word_id = None
        if normalized in existing_by_norm:
            existing = await asyncio.to_thread(
                firebase_service.get_word_by_text, user["id"], normalized,
            )
            existing_word_id = existing.get("id") if existing else None
        candidate = _candidate_from_generated(
            item,
            topic=raw_input if body.mode == "topic" else "",
            existing_word_id=existing_word_id,
        )
        if candidate is not None:
            candidates.append(candidate)
        if len(candidates) >= body.count:
            break

    return ImportWordsResponse(
        mode=body.mode,
        input=raw_input,
        candidates=candidates,
        duplicate_count=sum(1 for candidate in candidates if candidate.already_exists),
        max_candidates=limits["max_import_candidates"],
        max_input_chars=limits["max_import_input_chars"],
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
        raise ApiError(ERR.vocab_word_empty)

    await _enforce_private_vocab_cap(user, normalized)

    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    has_preview_data = any([
        body.definition,
        body.definition_vi,
        body.ipa,
        body.part_of_speech,
        body.example_en,
        body.example_vi,
    ])
    if body.use_ai and not has_preview_data:
        detail = await word_service.get_word_detail_fast(normalized, band)
        if detail is None or not word_service.is_word_core_detail_complete(detail, band):
            quota_service.check_and_increment(
                user_uid=str(user["id"]),
                feature="vocab",
                plan=user.get("plan", "free"),
                quota_override=user.get("quota_override"),
            )
            detail = await word_service.get_complete_word_detail(normalized, band)
        word_data = _word_data_from_detail(detail, normalized, band, body.topic)
    else:
        word_data = _word_data_from_request(body, normalized)

    word_id, created = await asyncio.to_thread(
        firebase_service.add_word_if_not_exists, user["id"], word_data
    )
    if not created:
        raise ApiError(ERR.vocab_word_duplicate, word=normalized)
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
    topic = cached.get("topic", "")
    words, changed = await asyncio.to_thread(
        _refresh_daily_word_status, user["id"], cached.get("words", []), topic,
    )
    if changed:
        await asyncio.to_thread(
            firebase_service.save_user_daily_words,
            user["id"], date, words, topic,
        )
    return _daily_response(
        date,
        topic,
        words,
        timezone_name,
        generated_at=cached.get("generated_at"),
    )
