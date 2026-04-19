from datetime import datetime

from pydantic import BaseModel


class VocabSkill(BaseModel):
    band: float
    total_words: int = 0
    mastered_count: int = 0


class WritingSkill(BaseModel):
    band: float
    sample_size: int = 0


class ListeningSkill(BaseModel):
    band: float
    sample_size: int = 0
    accuracy_by_type: dict[str, float] = {}


class ReadingSkill(BaseModel):
    band: float
    sample_size: int = 0


class SkillBreakdown(BaseModel):
    vocabulary: VocabSkill
    writing: WritingSkill
    listening: ListeningSkill
    reading: ReadingSkill


class ProgressSnapshot(BaseModel):
    overall_band: float
    skills: SkillBreakdown
    target_band: float = 7.0
    date: str | None = None
    generated_at: datetime | None = None


class TrendPoint(BaseModel):
    date: str
    overall_band: float
    vocabulary_band: float
    writing_band: float
    listening_band: float
    reading_band: float = 0.0


class ProgressPrediction(BaseModel):
    days_ahead: int
    projected_band: float


class ProgressResponse(BaseModel):
    snapshot: ProgressSnapshot
    trend: list[TrendPoint]
    predictions: list[ProgressPrediction]


class ProgressHistoryResponse(BaseModel):
    items: list[TrendPoint]


class CoachingTip(BaseModel):
    id: str
    skill: str
    tip_en: str
    tip_vi: str
    action_label: str
    action_route: str


class ProgressRecommendationsResponse(BaseModel):
    week_key: str
    tips: list[CoachingTip]
    generated_at: datetime | None = None
