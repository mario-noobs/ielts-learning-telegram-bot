from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class VocabularyWord(BaseModel):
    id: str
    word: str
    definition: str = ""
    definition_vi: str = ""
    ipa: str = ""
    part_of_speech: str = ""
    topic: str = ""
    example_en: str = ""
    example_vi: str = ""
    source: str = "daily"
    srs_interval: int = 0
    srs_ease: float = 2.5
    srs_reps: int = 0
    srs_next_review: datetime | None = None
    times_correct: int = 0
    times_incorrect: int = 0
    strength: str = "New"
    is_favourite: bool = False
    added_at: datetime | None = None


class WordListResponse(BaseModel):
    items: list[VocabularyWord]
    next_cursor: str | None = None


class DailyWord(BaseModel):
    word: str
    word_id: str = ""
    daily_source: str = "daily"
    reviewed: bool = False
    is_favourite: bool = False
    strength: str = "New"
    definition_en: str = ""
    definition_vi: str = ""
    ipa: str = ""
    part_of_speech: str = ""
    example_en: str = ""
    example_vi: str = ""


class DailyWordsResponse(BaseModel):
    date: str
    topic: str
    words: list[DailyWord]
    generated_at: datetime | None = None
    reviewed_count: int = 0
    total_count: int = 0
    timezone: str = ""
    next_reset_at: datetime | None = None
    extra_limit: int = 0
    extra_used: int = 0
    extra_remaining: int = 0


class DailyHistoryEntry(BaseModel):
    date: str
    topic: str
    words: list[DailyWord]
    generated_at: datetime | None = None
    total_count: int = 0
    reviewed_count: int = 0
    favourite_count: int = 0
    weak_count: int = 0
    mastered_count: int = 0


class DailyHistoryResponse(BaseModel):
    items: list[DailyHistoryEntry]
    timezone: str = ""


class DailyGenerateRequest(BaseModel):
    count: int | None = Field(default=None, ge=1, le=20)
    topics: list[str] | None = None


class DailyExtraRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=5)


class AddWordRequest(BaseModel):
    word: str = Field(min_length=1, max_length=80)
    topic: str = ""
    definition: str = ""
    definition_vi: str = ""
    ipa: str = ""
    part_of_speech: str = ""
    example_en: str = ""
    example_vi: str = ""
    use_ai: bool = True


class VocabularyDraftResponse(BaseModel):
    word: str
    definition: str = ""
    definition_vi: str = ""
    ipa: str = ""
    part_of_speech: str = ""
    topic: str = ""
    example_en: str = ""
    example_vi: str = ""
    ielts_tip: str = ""
    already_exists: bool = False
    existing_word_id: str | None = None


class ImportWordsRequest(BaseModel):
    mode: Literal["topic", "text"]
    input: str = Field(min_length=1, max_length=5000)
    count: int = Field(default=8, ge=1, le=30)


class ImportWordsResponse(BaseModel):
    mode: Literal["topic", "text"]
    input: str
    candidates: list[VocabularyDraftResponse]
    duplicate_count: int = 0
    max_candidates: int
    max_input_chars: int


class EnrichedExample(BaseModel):
    en: str = ""
    vi: str = ""


class Collocation(BaseModel):
    phrase: str
    label: str = ""


class EnrichedWord(BaseModel):
    word: str
    ipa: str = ""
    syllable_stress: str = ""
    part_of_speech: str = ""
    definition_en: str = ""
    definition_vi: str = ""
    word_family: list[str] = []
    collocations: list[Collocation] = []
    examples_by_band: dict[str, EnrichedExample] = {}
    ielts_tip: str = ""
    synonyms: list[str] = []
    antonyms: list[str] = []
    image_url: str | None = None


class TopicSummary(BaseModel):
    id: str
    name: str
    word_count: int = 0
    mastered_count: int = 0
    subtopics: list[str] = []


class TopicsResponse(BaseModel):
    items: list[TopicSummary]
    total_words: int


class PublicVocabPool(BaseModel):
    id: str
    title: str
    source: str
    source_theme: str = ""
    word_count: int
    difficulty: int | None = None
    difficulty_min: int | None = None
    difficulty_max: int | None = None
    topics: list[str] = []
    source_url: str = ""
    license: str = ""
    provenance: str = ""


class PublicVocabPoolRecommendationReason(BaseModel):
    code: str
    topic: str | None = None


class PublicVocabPoolRecommendation(PublicVocabPool):
    reasons: list[PublicVocabPoolRecommendationReason] = []


class PublicVocabPoolWord(BaseModel):
    id: str
    word: str
    definition_en: str = ""
    definition_vi: str = ""
    ipa: str = ""
    part_of_speech: str = ""
    example_en: str = ""
    example_vi: str = ""
    difficulty: int | None = None
    topic: str = ""
    source_ref: str = ""
    already_saved: bool = False
    existing_word_id: str | None = None


class PublicVocabPoolsResponse(BaseModel):
    enabled: bool
    items: list[PublicVocabPool] = []


class PublicVocabPoolRecommendationsResponse(BaseModel):
    enabled: bool
    target_difficulty: int | None = None
    items: list[PublicVocabPoolRecommendation] = []


class PublicVocabPoolDetailResponse(BaseModel):
    enabled: bool
    pool: PublicVocabPool
    words: list[PublicVocabPoolWord] = []


class PublicVocabPoolSaveResponse(BaseModel):
    created: bool
    already_saved: bool
    word: VocabularyWord


class VocabConsultDataPoint(BaseModel):
    label: str
    value: str


class VocabConsultMissingRequirement(BaseModel):
    code: str
    current: int
    required: int
    route: str


class VocabConsultItem(BaseModel):
    title: str
    detail: str
    evidence: str = ""


class VocabConsultAction(BaseModel):
    title: str
    detail: str
    route: str | None = None
    priority: Literal["high", "medium", "low"] = "medium"


class VocabRoadmapConsultResponse(BaseModel):
    status: Literal["ready", "insufficient_data"]
    disclaimer: str
    confidence: Literal["low", "medium", "high"]
    readiness_range: str = ""
    summary: str
    data_used: list[VocabConsultDataPoint] = []
    missing_requirements: list[VocabConsultMissingRequirement] = []
    strengths: list[VocabConsultItem] = []
    gaps: list[VocabConsultItem] = []
    next_actions: list[VocabConsultAction] = []
