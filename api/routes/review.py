import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user
from api.errors import ApiError, ERR
from api.models.review import (
    DueWord,
    ReviewDueRequest,
    ReviewDueResponse,
    ReviewRateRequest,
    ReviewRateResponse,
)
from services import firebase_service
from services.srs_service import calculate_next_review, get_word_strength

router = APIRouter(prefix="/api/v1/review", tags=["review"])

DEFAULT_DUE_LIMIT = 10
VOCAB_SOURCE_BY_ID = {
    1: "daily",
    2: "quiz",
    3: "manual",
    4: "reading",
    5: "public_pool",
}
VOCAB_SOURCE_ID_BY_NAME = {name: source_id for source_id, name in VOCAB_SOURCE_BY_ID.items()}


def _source_label(raw: object) -> str:
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        return normalized if normalized in VOCAB_SOURCE_ID_BY_NAME else "daily"
    try:
        return VOCAB_SOURCE_BY_ID.get(int(raw or 1), "daily")
    except (TypeError, ValueError):
        return "daily"


def _parse_source_filter(source: str | None) -> int | None:
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


def _to_due_word(doc: dict) -> DueWord:
    return DueWord(
        word_id=doc.get("id", ""),
        word=doc.get("word", ""),
        ipa=doc.get("ipa", ""),
        part_of_speech=doc.get("part_of_speech", ""),
        definition_en=doc.get("definition", "") or doc.get("definition_en", ""),
        definition_vi=doc.get("definition_vi", ""),
        example_en=doc.get("example_en", ""),
        example_vi=doc.get("example_vi", ""),
        source=_source_label(doc.get("source")),
        topic=doc.get("topic", ""),
        strength=get_word_strength(doc),
    )


@router.post("/due", response_model=ReviewDueResponse)
async def get_due(
    body: ReviewDueRequest | None = None,
    user: dict = Depends(get_current_user),
) -> ReviewDueResponse:
    """Return vocab rows whose SRS next_review is in the past, newest first."""
    limit = (body.limit if body and body.limit else DEFAULT_DUE_LIMIT)
    source_id = _parse_source_filter(body.source if body else None)
    topic = body.topic if body else None
    status_filter = body.status if body else None
    docs = await asyncio.to_thread(
        firebase_service.get_due_words,
        user["id"],
        limit,
        source_id,
        topic,
        status_filter,
    )
    return ReviewDueResponse(items=[_to_due_word(d) for d in docs])


@router.post("/rate", response_model=ReviewRateResponse)
async def rate_word(
    body: ReviewRateRequest,
    user: dict = Depends(get_current_user),
) -> ReviewRateResponse:
    """Apply SM-2 to a flashcard rating (again/good/easy) and persist."""
    word = await asyncio.to_thread(
        firebase_service.get_word_by_id, user["id"], body.word_id
    )
    if not word:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Word {body.word_id} not found in vocabulary.",
        )

    old_strength = get_word_strength(word)
    is_correct = body.rating != "again"
    srs_update = calculate_next_review(word, is_correct)

    # "Easy" gives a small extra interval bump on top of SM-2 correct.
    if body.rating == "easy" and is_correct:
        srs_update["srs_interval"] = max(
            srs_update["srs_interval"] + 1,
            round(srs_update["srs_interval"] * 1.3),
        )

    await asyncio.to_thread(
        firebase_service.update_word_srs, user["id"], body.word_id, srs_update
    )

    new_word = await asyncio.to_thread(
        firebase_service.get_word_by_id, user["id"], body.word_id
    )
    new_strength = get_word_strength(new_word or {})

    return ReviewRateResponse(
        word_id=body.word_id,
        old_strength=old_strength,
        new_strength=new_strength,
        strength_change=old_strength != new_strength,
        next_review=(new_word or {}).get("srs_next_review"),
    )
