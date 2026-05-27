from datetime import datetime

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


class AddWordRequest(BaseModel):
    word: str = Field(min_length=1, max_length=40)
    topic: str = ""


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
