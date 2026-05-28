from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from api.models.vocabulary import VocabularyWord


class TeamKnowledgeAuthor(BaseModel):
    user_id: str
    name: str = ""


class TeamWordSnapshot(BaseModel):
    word: str
    definition_en: str = ""
    definition_vi: str = ""
    ipa: str = ""
    part_of_speech: str = ""
    example_en: str = ""
    example_vi: str = ""
    topic: str = ""


class TeamKnowledgePost(BaseModel):
    id: str
    team_id: str
    type: Literal["question", "shared_word", "note"]
    category: str | None = None
    title: str | None = None
    body: str | None = None
    author: TeamKnowledgeAuthor
    word_snapshot: TeamWordSnapshot | None = None
    saved_to_my_words: bool = False
    existing_word_id: str | None = None
    reply_count: int = 0
    helpful_count: int = 0
    helpful_by_me: bool = False
    created_at: datetime


class TeamKnowledgePostsResponse(BaseModel):
    items: list[TeamKnowledgePost]
    next_cursor: str | None = None


class TeamShareWordRequest(BaseModel):
    user_vocab_id: str | None = Field(default=None, min_length=1)
    word: str | None = Field(default=None, min_length=1, max_length=120)
    note: str = Field(default="", max_length=500)


class TeamShareWordResponse(BaseModel):
    post: TeamKnowledgePost


class TeamSaveSharedWordResponse(BaseModel):
    created: bool
    already_saved: bool
    word: VocabularyWord


class TeamCreateKnowledgePostRequest(BaseModel):
    type: Literal["question", "note"] = "question"
    category: str = Field(default="general", min_length=1, max_length=40)
    title: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=3, max_length=2000)


class TeamCreateKnowledgePostResponse(BaseModel):
    post: TeamKnowledgePost


class TeamKnowledgeReply(BaseModel):
    id: str
    post_id: str
    team_id: str
    author: TeamKnowledgeAuthor
    body: str
    helpful_count: int = 0
    helpful_by_me: bool = False
    created_at: datetime


class TeamKnowledgeRepliesResponse(BaseModel):
    items: list[TeamKnowledgeReply]
    next_cursor: str | None = None


class TeamCreateKnowledgeReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class TeamCreateKnowledgeReplyResponse(BaseModel):
    reply: TeamKnowledgeReply


class TeamKnowledgeHelpfulResponse(BaseModel):
    target_type: Literal["post", "reply"]
    target_id: str
    helpful_count: int
    helpful_by_me: bool
