import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

import config
from api.auth import get_current_user
from api.models.vocabulary import (
    DailyGenerateRequest,
    DailyWord,
    DailyWordsResponse,
    VocabularyWord,
    WordListResponse,
)
from services import firebase_service, vocab_service
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
        definition_en=doc.get("definition_en", doc.get("definition", "")),
        definition_vi=doc.get("definition_vi", ""),
        ipa=doc.get("ipa", ""),
        part_of_speech=doc.get("part_of_speech", ""),
        example_en=doc.get("example_en", doc.get("example", "")),
        example_vi=doc.get("example_vi", ""),
    )


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
        return DailyWordsResponse(
            date=date_str,
            topic=cached.get("topic", ""),
            words=[_to_daily_word(w) for w in cached.get("words", [])],
            generated_at=cached.get("generated_at"),
        )

    count = (body.count if body and body.count else config.DEFAULT_WORD_COUNT)
    topics = (body.topics if body and body.topics else user.get("topics") or None)
    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))

    words, topic = await vocab_service.generate_personal_daily_words(
        telegram_id=user["id"], count=count, band=band, topics=topics
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
