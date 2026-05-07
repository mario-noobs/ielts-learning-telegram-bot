from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DueWord(BaseModel):
    word_id: str
    word: str
    ipa: str = ""
    part_of_speech: str = ""
    definition_en: str = ""
    definition_vi: str = ""
    example_en: str = ""
    example_vi: str = ""
    strength: str = "New"


class ReviewDueRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=50)


class ReviewDueResponse(BaseModel):
    items: list[DueWord]


class ReviewRateRequest(BaseModel):
    word_id: str
    rating: Literal["again", "good", "easy"]


class ReviewRateResponse(BaseModel):
    word_id: str
    old_strength: str
    new_strength: str
    strength_change: bool
    next_review: datetime | None = None
