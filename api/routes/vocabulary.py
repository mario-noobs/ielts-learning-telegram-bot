import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

import config
from api.auth import get_current_user
from api.models.vocabulary import (
    AddWordRequest,
    DailyGenerateRequest,
    DailyWord,
    DailyWordsResponse,
    VocabularyWord,
    WordListResponse,
)
from services import firebase_service, vocab_service, word_service
from services.srs_service import get_word_strength

router = APIRouter(prefix="/api/v1/vocabulary", tags=["vocabulary"])


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
        srs_interval=doc.get("srs_interval", 0),
        srs_ease=doc.get("srs_ease", 2.5),
        srs_reps=doc.get("srs_reps", 0),
        srs_next_review=doc.get("srs_next_review"),
        times_correct=doc.get("times_correct", 0),
        times_incorrect=doc.get("times_incorrect", 0),
        strength=get_word_strength(doc),
        added_at=doc.get("added_at"),
    )


def _to_daily_word(doc: dict) -> DailyWord:
    return DailyWord(
        word=doc.get("word", ""),
        word_id=doc.get("word_id", ""),
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


@router.get("", response_model=WordListResponse)
async def list_vocabulary(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, description="ISO-8601 added_at from previous page"),
    user: dict = Depends(get_current_user),
) -> WordListResponse:
    """Paginated vocabulary list with SRS data, newest first."""
    after = None
    if cursor:
        try:
            after = datetime.fromisoformat(cursor)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor format; expected ISO-8601 datetime.",
            )

    docs = await asyncio.to_thread(
        firebase_service.get_user_vocabulary_page, user["id"], limit, after
    )
    items = [_to_vocab_word(d) for d in docs]
    next_cursor = None
    if len(items) == limit and items[-1].added_at is not None:
        next_cursor = items[-1].added_at.isoformat()
    return WordListResponse(items=items, next_cursor=next_cursor)


@router.post("/daily", response_model=DailyWordsResponse)
async def generate_daily(
    body: DailyGenerateRequest | None = None,
    user: dict = Depends(get_current_user),
) -> DailyWordsResponse:
    """Generate (or return cached) today's personal daily words."""
    date_str = config.local_date_str()

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
        return DailyWordsResponse(
            date=date_str,
            topic=cached_topic,
            words=[_to_daily_word(w) for w in cached_words],
            generated_at=cached.get("generated_at"),
        )

    count = (body.count if body and body.count else config.DEFAULT_WORD_COUNT)
    topics = (body.topics if body and body.topics else user.get("topics") or None)
    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))

    words, topic = await vocab_service.generate_personal_daily_words(
        telegram_id=user["id"], count=count, band=band, topics=topics
    )

    await asyncio.to_thread(
        _persist_daily_to_deck, user["id"], words, topic
    )
    await asyncio.to_thread(
        firebase_service.save_user_daily_words, user["id"], date_str, words, topic
    )

    return DailyWordsResponse(
        date=date_str,
        topic=topic,
        words=[_to_daily_word(w) for w in words],
        generated_at=datetime.utcnow(),
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
    return DailyWordsResponse(
        date=date,
        topic=cached.get("topic", ""),
        words=[_to_daily_word(w) for w in cached.get("words", [])],
        generated_at=cached.get("generated_at"),
    )
