from datetime import datetime

from pydantic import BaseModel, Field


class ListeningGenerateRequest(BaseModel):
    exercise_type: str = Field(
        default="dictation", pattern=r"^(dictation|gap_fill|comprehension)$",
    )
    topic: str = Field(default="", max_length=60)


class GapBlank(BaseModel):
    index: int
    answer: str = ""


class ComprehensionQuestionView(BaseModel):
    question: str
    options: list[str]
    # correct_index deliberately omitted in pre-submit view


class ComprehensionQuestionFull(ComprehensionQuestionView):
    correct_index: int
    explanation_vi: str = ""


class ListeningExerciseBase(BaseModel):
    id: str
    exercise_type: str
    band: float
    topic: str
    title: str
    duration_estimate_sec: int
    audio_url: str
    created_at: datetime | None = None
    submitted: bool = False
    score: float | None = None


class ListeningExerciseView(ListeningExerciseBase):
    """Pre-submit view: hides transcript and answers."""
    display_text: str = ""
    questions: list[ComprehensionQuestionView] = []


class ListeningExerciseResult(ListeningExerciseBase):
    """Post-submit view: includes transcript and correct answers + scoring details."""
    transcript: str
    display_text: str = ""
    blanks: list[GapBlank] = []
    questions: list[ComprehensionQuestionFull] = []
    # Scoring payloads (shape depends on type)
    dictation_diff: list[dict] = []
    gap_fill_results: list[dict] = []
    comprehension_results: list[dict] = []
    misheard_words: list[str] = []


class ListeningSubmitRequest(BaseModel):
    user_text: str = ""
    answers: list[str] = []


class ListeningHistoryItem(BaseModel):
    id: str
    exercise_type: str
    title: str
    band: float
    score: float | None = None
    submitted: bool = False
    created_at: datetime | None = None


class ListeningHistoryResponse(BaseModel):
    items: list[ListeningHistoryItem]
