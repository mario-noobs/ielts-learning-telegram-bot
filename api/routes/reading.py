"""Reading Lab API — passages list/detail + session lifecycle (US-M9.2).

Endpoints:
  GET  /api/v1/reading/passages?band=&topic=     → list summaries
  GET  /api/v1/reading/passages/{id}             → full passage (no questions)
  POST /api/v1/reading/sessions                  → start timed session
  POST /api/v1/reading/sessions/{id}/submit      → grade + return result

Design notes:
- Passages are static content loaded from content/reading/passages at
  import time. Session state is per-user in Firestore under
  users/{uid}/reading_sessions/{session_id}.
- Sessions are created with a 20-min expiry. Submits after expiry return
  410 Gone with an expired-session error.
- Idempotent submit: re-submitting a completed session returns the
  original grading (AC2).
- Rate limits: 5/min on session create + submit, enforced via the
  existing rate_limit_service (extended for the "reading" command).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

import config
from api.auth import get_current_user
from api.models.reading import (
    PassageDetail,
    PassageListResponse,
    PassageSummary,
    ReadingQuestion,
    ReadingSession,
    SessionCreateRequest,
    SessionGrade,
    SessionSubmitRequest,
    SessionSubmitResponse,
)
from services import firebase_service, rate_limit_service, reading_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reading", tags=["reading"])

_SESSION_DURATION_SECONDS = 20 * 60
_RATE_LIMIT_COMMAND = "reading"

# The rate-limit service is Telegram-centric (AI_COMMANDS set). Register
# our command idempotently so per-user limits kick in for web-only users.
rate_limit_service.AI_COMMANDS.add(_RATE_LIMIT_COMMAND)


def _check_rate_limit(user: dict) -> None:
    uid = user.get("telegram_id") or user.get("id")
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        # web_<hex> users: hash to a stable int so rate_limit_service keys
        # by per-user bucket without confusing telegram ids.
        uid = hash(str(uid)) & 0x7FFFFFFF
    allowed, msg = rate_limit_service.check_rate_limit(uid, _RATE_LIMIT_COMMAND)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg,
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value))


# ─── Passages ────────────────────────────────────────────────────────


@router.get("/passages", response_model=PassageListResponse)
async def list_passages(
    band: Optional[float] = Query(None, description="Filter to a single band tier"),
    topic: Optional[str] = Query(None, description="Filter to a single topic slug"),
    user: dict = Depends(get_current_user),
) -> PassageListResponse:
    summaries = reading_service.list_summaries(band=band, topic=topic)
    return PassageListResponse(items=[PassageSummary(**s) for s in summaries])


@router.get("/passages/{passage_id}", response_model=PassageDetail)
async def get_passage(
    passage_id: str,
    user: dict = Depends(get_current_user),
) -> PassageDetail:
    passage = reading_service.get_passage(passage_id)
    if not passage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passage '{passage_id}' not found.",
        )
    return PassageDetail(
        id=passage["id"],
        title=passage.get("title", ""),
        topic=passage.get("topic", ""),
        band=passage.get("band", 0.0),
        word_count=passage.get("word_count", 0),
        attribution=passage.get("attribution", ""),
        ai_assisted=bool(passage.get("ai_assisted", False)),
        body=passage.get("body", ""),
    )


# ─── Sessions ────────────────────────────────────────────────────────


@router.post("/sessions", response_model=ReadingSession, status_code=201)
async def start_session(
    body: SessionCreateRequest,
    user: dict = Depends(get_current_user),
) -> ReadingSession:
    _check_rate_limit(user)

    passage = reading_service.get_passage(body.passage_id)
    if not passage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passage '{body.passage_id}' not found.",
        )

    questions_client, answer_key = await reading_service.get_or_generate_questions(passage)
    now = _utcnow()
    expires_at = now + timedelta(seconds=_SESSION_DURATION_SECONDS)
    session_id = f"rs_{uuid.uuid4().hex[:12]}"

    data = {
        "passage_id": body.passage_id,
        "status": "in_progress",
        "started_at": now,
        "expires_at": expires_at,
        "questions": questions_client,
        "answer_key": answer_key,
        "submitted_at": None,
        "grade": None,
        "idempotency_key": None,
    }
    await asyncio.to_thread(
        firebase_service.save_reading_session, user["id"], session_id, data,
    )

    return ReadingSession(
        id=session_id,
        passage_id=body.passage_id,
        status="in_progress",
        started_at=now,
        expires_at=expires_at,
        submitted_at=None,
        questions=[ReadingQuestion(**q) for q in questions_client],
        duration_seconds=_SESSION_DURATION_SECONDS,
    )


@router.post("/sessions/{session_id}/submit", response_model=SessionSubmitResponse)
async def submit_session(
    session_id: str,
    body: SessionSubmitRequest,
    user: dict = Depends(get_current_user),
) -> SessionSubmitResponse:
    _check_rate_limit(user)

    doc = await asyncio.to_thread(
        firebase_service.get_reading_session, user["id"], session_id,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    # AC2: idempotent re-submit — return the original grading unchanged.
    if doc.get("status") == "submitted":
        grade = doc.get("grade") or {}
        if body.idempotency_key and doc.get("idempotency_key") == body.idempotency_key:
            return SessionSubmitResponse(
                session_id=session_id,
                passage_id=doc["passage_id"],
                submitted_at=_parse_dt(doc["submitted_at"]),
                grade=SessionGrade(**grade),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session already submitted.",
        )

    expires_at = _parse_dt(doc["expires_at"])
    if _utcnow() > expires_at:
        await asyncio.to_thread(
            firebase_service.update_reading_session,
            user["id"], session_id, {"status": "expired"},
        )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session expired before submission.",
        )

    grade_dict = reading_service.grade_answers(
        user_answers=body.answers,
        answer_key=doc.get("answer_key", []),
        questions=doc.get("questions", []),
    )
    now = _utcnow()
    await asyncio.to_thread(
        firebase_service.update_reading_session,
        user["id"], session_id,
        {
            "status": "submitted",
            "submitted_at": now,
            "grade": grade_dict,
            "idempotency_key": body.idempotency_key,
            "user_answers": body.answers,
        },
    )

    # US-M9.5 AC4: auto-complete the matching plan activity if present.
    # Best-effort — failures here must not fail the submit.
    passage_id = doc.get("passage_id")
    if passage_id:
        try:
            await asyncio.to_thread(
                firebase_service.complete_plan_activity,
                user["id"], config.local_date_str(), f"reading_{passage_id}",
            )
        except Exception as exc:
            logger.warning("reading: plan auto-complete failed: %s", exc)

    return SessionSubmitResponse(
        session_id=session_id,
        passage_id=doc["passage_id"],
        submitted_at=now,
        grade=SessionGrade(**grade_dict),
    )
