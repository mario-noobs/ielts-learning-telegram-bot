from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from starlette.status import HTTP_204_NO_CONTENT

from api.auth import get_current_user
from api.models.team_knowledge import (
    TeamCreateKnowledgePostRequest,
    TeamCreateKnowledgePostResponse,
    TeamCreateKnowledgeReplyRequest,
    TeamCreateKnowledgeReplyResponse,
    TeamKnowledgeHelpfulResponse,
    TeamKnowledgePostsResponse,
    TeamKnowledgeRepliesResponse,
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


@router.post("/posts", response_model=TeamCreateKnowledgePostResponse, status_code=201)
def create_team_knowledge_post(
    team_id: str,
    body: TeamCreateKnowledgePostRequest,
    user: dict = Depends(get_current_user),
) -> TeamCreateKnowledgePostResponse:
    post = team_knowledge_service.create_post(
        team_id=team_id,
        user_id=str(user["id"]),
        post_type=body.type,
        category=body.category,
        title=body.title,
        body=body.body,
        word_context=body.word_context.model_dump() if body.word_context else None,
    )
    return TeamCreateKnowledgePostResponse(post=post)


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


@router.get(
    "/posts/{post_id}/replies",
    response_model=TeamKnowledgeRepliesResponse,
)
def list_team_knowledge_replies(
    team_id: str,
    post_id: str,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
    user: dict = Depends(get_current_user),
) -> TeamKnowledgeRepliesResponse:
    payload = team_knowledge_service.list_replies(
        team_id=team_id,
        post_id=post_id,
        user_id=str(user["id"]),
        limit=limit,
        cursor=cursor,
    )
    return TeamKnowledgeRepliesResponse(**payload)


@router.post(
    "/posts/{post_id}/replies",
    response_model=TeamCreateKnowledgeReplyResponse,
    status_code=201,
)
def create_team_knowledge_reply(
    team_id: str,
    post_id: str,
    body: TeamCreateKnowledgeReplyRequest,
    user: dict = Depends(get_current_user),
) -> TeamCreateKnowledgeReplyResponse:
    reply = team_knowledge_service.create_reply(
        team_id=team_id,
        post_id=post_id,
        user_id=str(user["id"]),
        body=body.body,
    )
    return TeamCreateKnowledgeReplyResponse(reply=reply)


@router.post(
    "/posts/{post_id}/helpful",
    response_model=TeamKnowledgeHelpfulResponse,
)
def toggle_team_knowledge_post_helpful(
    team_id: str,
    post_id: str,
    user: dict = Depends(get_current_user),
) -> TeamKnowledgeHelpfulResponse:
    payload = team_knowledge_service.toggle_post_helpful(
        team_id=team_id,
        post_id=post_id,
        user_id=str(user["id"]),
    )
    return TeamKnowledgeHelpfulResponse(**payload)


@router.post(
    "/posts/{post_id}/replies/{reply_id}/helpful",
    response_model=TeamKnowledgeHelpfulResponse,
)
def toggle_team_knowledge_reply_helpful(
    team_id: str,
    post_id: str,
    reply_id: str,
    user: dict = Depends(get_current_user),
) -> TeamKnowledgeHelpfulResponse:
    payload = team_knowledge_service.toggle_reply_helpful(
        team_id=team_id,
        post_id=post_id,
        reply_id=reply_id,
        user_id=str(user["id"]),
    )
    return TeamKnowledgeHelpfulResponse(**payload)


@router.delete("/posts/{post_id}", status_code=HTTP_204_NO_CONTENT)
def delete_team_knowledge_post(
    team_id: str,
    post_id: str,
    user: dict = Depends(get_current_user),
) -> Response:
    team_knowledge_service.delete_post(
        team_id=team_id,
        post_id=post_id,
        user_id=str(user["id"]),
    )
    return Response(status_code=HTTP_204_NO_CONTENT)


@router.delete(
    "/posts/{post_id}/replies/{reply_id}",
    status_code=HTTP_204_NO_CONTENT,
)
def delete_team_knowledge_reply(
    team_id: str,
    post_id: str,
    reply_id: str,
    user: dict = Depends(get_current_user),
) -> Response:
    team_knowledge_service.delete_reply(
        team_id=team_id,
        post_id=post_id,
        reply_id=reply_id,
        user_id=str(user["id"]),
    )
    return Response(status_code=HTTP_204_NO_CONTENT)
