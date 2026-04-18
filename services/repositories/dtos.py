"""Pydantic DTOs for the repositories layer.

These DTOs mirror the **Firestore document shape** for the user-scoped
collections that will migrate to Postgres in M8 (#130). They are
intentionally distinct from the API response models under
``api/models/`` — those are response-shaped (lean, client-facing),
whereas these carry the full persisted row shape (counters, timestamps,
SRS state, etc.).

Design rules:
- Every DTO has an ``id`` field (doc id or primary key).
- Timestamps normalize to ``datetime`` (UTC). Firestore returns
  ``DatetimeWithNanoseconds`` which is a subclass of ``datetime``; Pydantic
  will accept it directly but ``to_firestore_dict`` strips any pydantic-
  specific decoration.
- Extra fields are allowed (``extra="allow"``) so that ad-hoc fields
  added by earlier migrations round-trip without data loss.
- Use ``DTO.from_snapshot(doc)`` on reads and ``dto.to_firestore_dict()``
  on writes. ``model_dump(exclude={"id"})`` is also safe for write paths
  because ``id`` is the document id, not a field inside the document.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# ─── Base ────────────────────────────────────────────────────────────

class _FirestoreDTO(BaseModel):
    """Common configuration for all repository DTOs."""

    model_config = ConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,
    )

    @classmethod
    def from_snapshot(cls, snapshot: Any) -> "_FirestoreDTO":
        """Build a DTO from a Firestore ``DocumentSnapshot``.

        Uses ``snapshot.to_dict()`` for the payload and ``snapshot.id`` for
        the id field. Returns None semantics belong to callers — this
        constructor assumes the snapshot exists.
        """
        data = snapshot.to_dict() or {}
        return cls.model_validate({"id": snapshot.id, **data})

    @classmethod
    def from_dict(cls, doc_id: str, data: dict) -> "_FirestoreDTO":
        """Build a DTO from a raw id + payload dict."""
        return cls.model_validate({"id": doc_id, **(data or {})})

    def to_firestore_dict(self) -> dict:
        """Return the document body (without ``id``) for Firestore writes.

        ``None`` values are preserved so callers can explicitly clear
        fields via ``.update()``.
        """
        return self.model_dump(exclude={"id"}, mode="python")


# ─── Users ───────────────────────────────────────────────────────────

class UserDoc(_FirestoreDTO):
    """A user profile document at ``users/{id}``.

    ``id`` is the stringified Telegram id for bot-created users, or a
    ``web_<hex>`` prefix for web-registered users.
    """

    id: str
    name: str = ""
    username: str = ""
    email: Optional[str] = None
    auth_uid: Optional[str] = None
    group_id: Optional[int] = None
    target_band: float = 7.0
    topics: list[str] = Field(default_factory=list)
    daily_time: Optional[str] = None
    timezone: Optional[str] = None
    streak: int = 0
    last_active: Optional[datetime] = None
    total_words: int = 0
    total_quizzes: int = 0
    total_correct: int = 0
    challenge_wins: int = 0
    exam_date: Optional[str] = None
    weekly_goal_minutes: Optional[int] = None
    created_at: Optional[datetime] = None


class QuizStats(BaseModel):
    """Aggregate quiz stats derived from the user profile counters."""

    total: int = 0
    correct: int = 0
    accuracy: float = 0.0


# ─── Vocabulary ──────────────────────────────────────────────────────

class VocabularyItem(_FirestoreDTO):
    """A vocabulary card at ``users/{uid}/vocabulary/{id}``.

    Carries both the lexical fields and the SRS scheduling state.
    """

    id: str
    word: str = ""
    definition: str = ""
    definition_en: str = ""
    definition_vi: str = ""
    ipa: str = ""
    part_of_speech: str = ""
    topic: str = ""
    example_en: str = ""
    example_vi: str = ""

    # SRS state
    srs_interval: int = 0
    srs_ease: float = 2.5
    srs_reps: int = 0
    srs_next_review: Optional[datetime] = None
    times_correct: int = 0
    times_incorrect: int = 0

    added_at: Optional[datetime] = None


# ─── Quiz history ────────────────────────────────────────────────────

class QuizHistoryEntry(_FirestoreDTO):
    """A single answered quiz question at ``users/{uid}/quiz_history/{id}``.

    The schema is intentionally loose (``extra="allow"``) because quiz
    payloads vary by quiz type. The only always-present fields are
    ``id``, ``created_at``, and ``is_correct``.
    """

    id: str
    is_correct: bool = False
    created_at: Optional[datetime] = None


# ─── Writing history ─────────────────────────────────────────────────

class WritingHistoryEntry(_FirestoreDTO):
    """A writing submission + feedback at ``users/{uid}/writing_history/{id}``.

    Holds the raw text plus the AI feedback payload. Shape is loose
    because feedback fields are optional until scoring completes.
    """

    id: str
    text: str = ""
    task_type: str = "task2"
    prompt: str = ""
    overall_band: float = 0.0
    word_count: int = 0
    created_at: Optional[datetime] = None


# ─── Daily words (DM / user scope) ──────────────────────────────────

class DailyWordsDoc(_FirestoreDTO):
    """Personal daily words at ``users/{uid}/daily_words/{date_str}``.

    The document id is the local date string (``YYYY-MM-DD``). Group
    daily words live under ``groups/*`` and are intentionally NOT
    covered by this repository — groups stay on Firestore permanently.
    """

    id: str  # date_str
    words: list[dict] = Field(default_factory=list)
    topic: str = ""
    generated_at: Optional[datetime] = None


# ─── Helpers ─────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    """Return ``datetime.now(timezone.utc)`` — extracted for mocking in tests."""
    return datetime.now(timezone.utc)


__all__ = [
    "UserDoc",
    "QuizStats",
    "VocabularyItem",
    "QuizHistoryEntry",
    "WritingHistoryEntry",
    "DailyWordsDoc",
]
