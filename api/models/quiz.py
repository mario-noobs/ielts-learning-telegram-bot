from datetime import datetime

from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    id: str
    type: str
    question: str
    options: list[str] = []
    word_id: str = ""


class QuizStartRequest(BaseModel):
    count: int | None = Field(default=None, ge=1, le=20)
    types: list[str] | None = None
    word_ids: list[str] | None = None


class QuizStartResponse(BaseModel):
    session_id: str
    questions: list[QuizQuestion]


class QuizAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str


class SRSUpdate(BaseModel):
    next_review: datetime | None = None
    old_strength: str = "New"
    new_strength: str = "New"
    strength_change: bool = False


class QuizAnswerResponse(BaseModel):
    is_correct: bool
    feedback: str
    srs_update: SRSUpdate
