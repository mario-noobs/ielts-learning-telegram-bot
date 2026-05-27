import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

import config
from api.auth import get_current_user
from api.errors import ApiError, ERR
from api.models.vocabulary import Collocation, EnrichedExample, EnrichedWord
from services import word_service
from services.admin import quota_service


def _to_collocation(item) -> Collocation:
    if isinstance(item, dict):
        return Collocation(phrase=item.get("phrase", ""), label=item.get("label", ""))
    return Collocation(phrase=str(item), label="")

router = APIRouter(prefix="/api/v1/words", tags=["words"])


# ── Strength override (US-#231) ──────────────────────────────────────
#
# Per-user-per-day rate limit on manual mastery overrides. Defends
# against a user spamming "Mastered" on every word to game the
# progress dashboard. 30/day is comfortably above honest usage but
# tight enough that a script-y bulk-edit notices.
#
# Window is "today in UTC" — same boundary as ai_usage. In-memory
# deque per user; resets at midnight UTC. If we ever go multi-process
# move to ai_usage table or its own counter.
_OVERRIDE_LIMIT_PER_DAY = 30
_override_log: dict[str, deque[float]] = defaultdict(deque)


def _check_override_rate_limit(user_uid: str) -> None:
    now = time.monotonic()
    cutoff = now - 24 * 3600
    log = _override_log[user_uid]
    while log and log[0] < cutoff:
        log.popleft()
    if len(log) >= _OVERRIDE_LIMIT_PER_DAY:
        raise ApiError(ERR.vocab_override_rate_limited)
    log.append(now)


class _StrengthBody(BaseModel):
    """Body for ``PATCH /api/v1/words/{word_id}/strength``."""

    strength: Literal["Weak", "Learning", "Good", "Mastered"]


class _StrengthResponse(BaseModel):
    """Response — echoes back the resolved strength + new SRS state.

    ``strength_applied`` is true when the override actually changed
    state. False means we honoured the "don't roll back quiz progress"
    rule (e.g. user clicked Mastered but they were already past 30d
    interval) — UI uses this to decide whether to flash a confirmation
    or not.
    """

    word_id: str
    strength: str
    strength_applied: bool
    srs_interval: int
    srs_reps: int
    srs_next_review: str | None


@router.patch("/{word_id}/strength", response_model=_StrengthResponse)
async def update_word_strength(
    word_id: str,
    body: _StrengthBody,
    user: dict = Depends(get_current_user),
) -> _StrengthResponse:
    """Manually set a word's mastery tier (US-#231).

    Translates the chosen tier to an SRS interval/reps target so the
    review engine continues from the new state. Anti-game: max 30
    overrides/user/day; protects against bulk "Mastered" spam.

    Per the saved memory rule, manual overrides shouldn't roll back
    quiz progress: if the user is already past the chosen tier's
    interval, the request is acknowledged but state is not changed.
    """
    user_id = str(user.get("id") or "")
    if not user_id:
        raise ApiError(ERR.vocab_word_not_found)

    auth_uid = str(user.get("auth_uid") or user_id)
    _check_override_rate_limit(auth_uid)

    try:
        before_word = await asyncio.to_thread(
            word_service.firebase_service.get_word_by_id,
            user_id, word_id,
        )
        if not before_word:
            raise ApiError(ERR.vocab_word_not_found)

        before_interval = int(before_word.get("srs_interval") or 0)
        updated = await asyncio.to_thread(
            word_service.set_word_strength_manual,
            user_id, word_id, body.strength,
        )
    except ValueError:
        raise ApiError(ERR.vocab_word_not_found)

    after_interval = int(updated.get("srs_interval") or 0)
    applied = before_interval != after_interval or before_word.get("srs_reps") != updated.get("srs_reps")

    next_review = updated.get("srs_next_review")
    if isinstance(next_review, datetime):
        next_review_iso = next_review.astimezone(timezone.utc).isoformat()
    else:
        next_review_iso = str(next_review) if next_review else None

    return _StrengthResponse(
        word_id=word_id,
        strength=body.strength,
        strength_applied=applied,
        srs_interval=after_interval,
        srs_reps=int(updated.get("srs_reps") or 0),
        srs_next_review=next_review_iso,
    )


@router.get(
    "/{word}",
    response_model=EnrichedWord,
)
async def get_enriched_word(
    word: str,
    user: dict = Depends(get_current_user),
) -> EnrichedWord:
    """Return full enrichment for a word (IPA, examples, collocations, ...)."""
    normalized = word_service.normalize_word(word)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Word cannot be empty.",
        )

    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    data = await word_service.get_word_detail_fast(normalized, band)
    if data is None or not word_service.is_word_core_detail_complete(data, band):
        quota_service.check_and_increment(
            user_uid=str(user["id"]),
            feature="words",
            plan=user.get("plan", "free"),
            quota_override=user.get("quota_override"),
        )
        data = await word_service.get_complete_word_detail(normalized, band)

    raw_examples = data.get("examples_by_band", {}) or {}
    examples = {
        tier: EnrichedExample(en=ex.get("en", ""), vi=ex.get("vi", ""))
        for tier, ex in raw_examples.items()
    }

    raw_collocations = data.get("collocations", []) or []
    collocations = [_to_collocation(c) for c in raw_collocations if c]

    raw_synonyms = data.get("synonyms")
    raw_antonyms = data.get("antonyms")
    synonyms = (
        raw_synonyms.get("words", [])
        if isinstance(raw_synonyms, dict)
        else (raw_synonyms or [])
    )
    antonyms = (
        raw_antonyms.get("words", [])
        if isinstance(raw_antonyms, dict)
        else (raw_antonyms or [])
    )

    return EnrichedWord(
        word=data.get("word", normalized),
        ipa=data.get("ipa", ""),
        syllable_stress=data.get("syllable_stress", ""),
        part_of_speech=data.get("part_of_speech", ""),
        definition_en=data.get("definition_en", ""),
        definition_vi=data.get("definition_vi", ""),
        word_family=data.get("word_family", []) or [],
        collocations=collocations,
        examples_by_band=examples,
        ielts_tip=data.get("ielts_tip", ""),
        synonyms=synonyms,
        antonyms=antonyms,
        image_url=data.get("image_url"),
    )
