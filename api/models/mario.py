"""Pydantic models for Mario onboarding assistant endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MarioEventType = Literal[
    "shown",
    "expanded",
    "minimized",
    "dismissed",
    "action_clicked",
]


class MarioGreeting(BaseModel):
    key: str
    params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class MarioActionSuggestion(BaseModel):
    id: str
    label_key: str
    route: str
    params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class MarioStateResponse(BaseModel):
    enabled: bool
    minimized: bool = True
    greeting: MarioGreeting | None = None
    suggestions: list[MarioActionSuggestion] = Field(default_factory=list)


class MarioEventRequest(BaseModel):
    event: MarioEventType
    route: str | None = Field(default=None, max_length=120)
    suggestion_id: str | None = Field(default=None, max_length=80)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


MarioChatRole = Literal["user", "assistant"]


class MarioChatMessage(BaseModel):
    role: MarioChatRole
    content: str = Field(min_length=1, max_length=1200)


class MarioChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=800)
    route: str | None = Field(default=None, max_length=120)
    history: list[MarioChatMessage] = Field(default_factory=list, max_length=8)


class MarioChatResponse(BaseModel):
    message: MarioChatMessage
