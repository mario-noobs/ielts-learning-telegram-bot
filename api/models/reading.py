"""Pydantic models for the Reading Lab API (US-M9.2, issue #136)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─── Passage summary / detail ────────────────────────────────────────


class PassageSummary(BaseModel):
    id: str
    title: str
    topic: str
    band: float
    word_count: int
    attribution: str
    ai_assisted: bool


class PassageListResponse(BaseModel):
    items: list[PassageSummary]


class PassageDetail(PassageSummary):
    body: str


# ─── Questions ───────────────────────────────────────────────────────


class QuestionOption(BaseModel):
    id: str
    text: str


QuestionType = Literal["mcq", "tfng", "gap-fill", "matching"]


class ReadingQuestion(BaseModel):
    id: str
    type: QuestionType
    stem: str
    options: Optional[list[QuestionOption]] = None  # populated for mcq / matching


# ─── Sessions ────────────────────────────────────────────────────────


class SessionCreateRequest(BaseModel):
    passage_id: str


class ReadingSession(BaseModel):
    id: str
    passage_id: str
    status: Literal["in_progress", "submitted", "expired"]
    started_at: datetime
    expires_at: datetime
    submitted_at: Optional[datetime] = None
    questions: list[ReadingQuestion]
    duration_seconds: int = Field(default=20 * 60)


class SessionSubmitRequest(BaseModel):
    answers: dict[str, str]  # {question_id: option_id}
    idempotency_key: Optional[str] = None


class QuestionResult(BaseModel):
    id: str
    user_answer: Optional[str]
    correct_answer: str
    is_correct: bool
    explanation: str


class SessionGrade(BaseModel):
    correct: int
    total: int
    band: float
    per_question: list[QuestionResult]


class SessionSubmitResponse(BaseModel):
    session_id: str
    passage_id: str
    submitted_at: datetime
    grade: SessionGrade
