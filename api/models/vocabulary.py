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
    added_at: datetime | None = None


class WordListResponse(BaseModel):
    items: list[VocabularyWord]
    next_cursor: str | None = None


class DailyWord(BaseModel):
    word: str
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


class TopicSummary(BaseModel):
    id: str
    name: str
    word_count: int = 0
    subtopics: list[str] = []


class TopicsResponse(BaseModel):
    items: list[TopicSummary]
    total_words: int
