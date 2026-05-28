from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.auth import get_current_user
from api.models.team_knowledge import (
    TeamKnowledgePostsResponse,
    TeamSaveSharedWordResponse,
    TeamShareWordRequest,
    TeamShareWordResponse,
)
from api.models.vocabulary import VocabularyWord
from services import team_knowledge_service
from services.srs_service import get_word_strength

router = APIRouter(prefix="/api/v1/teams/{team_id}/knowledge", tags=["team-knowledge"])

VOCAB_SOURCE_BY_ID = {
    1: "daily",
    2: "quiz",
    3: "manual",
    4: "reading",
    5: "public_pool",
}


def _vocab_source_label(raw: object) -> str:
    try:
        return VOCAB_SOURCE_BY_ID.get(int(raw or 1), "daily")
    except (TypeError, ValueError):
        return "daily"


def _to_vocab_word(doc: dict) -> VocabularyWord:
    return VocabularyWord(
        id=doc["id"],
        word=doc.get("word", ""),
        definition=doc.get("definition", doc.get("definition_en", "")),
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
        strength=get_word_strength(doc),
        is_favourite=doc.get("is_favourite", False),
        added_at=doc.get("added_at"),
    )


@router.get("/posts", response_model=TeamKnowledgePostsResponse)
def list_team_knowledge_posts(
    team_id: str,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
    user: dict = Depends(get_current_user),
) -> TeamKnowledgePostsResponse:
    payload = team_knowledge_service.list_posts(
        team_id=team_id,
        user_id=str(user["id"]),
        limit=limit,
        cursor=cursor,
    )
    return TeamKnowledgePostsResponse(**payload)


@router.post("/posts/share-word", response_model=TeamShareWordResponse, status_code=201)
def share_word_to_team(
    team_id: str,
    body: TeamShareWordRequest,
    user: dict = Depends(get_current_user),
) -> TeamShareWordResponse:
    post = team_knowledge_service.share_word(
        team_id=team_id,
        user_id=str(user["id"]),
        user_vocab_id=body.user_vocab_id,
        word_text=body.word,
        note=body.note,
    )
    return TeamShareWordResponse(post=post)


@router.post(
    "/posts/{post_id}/save-word",
    response_model=TeamSaveSharedWordResponse,
)
def save_team_shared_word(
    team_id: str,
    post_id: str,
    user: dict = Depends(get_current_user),
) -> TeamSaveSharedWordResponse:
    result = team_knowledge_service.save_shared_word(
        team_id=team_id,
        post_id=post_id,
        user=user,
    )
    return TeamSaveSharedWordResponse(
        created=result["created"],
        already_saved=result["already_saved"],
        word=_to_vocab_word(result["word"]),
    )
