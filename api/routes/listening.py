import asyncio
import json
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

import config
from api.auth import get_current_user
from api.models.listening import (
    ListeningExerciseResult,
    ListeningExerciseView,
    ListeningGenerateRequest,
    ListeningHistoryItem,
    ListeningHistoryResponse,
    ListeningSubmitRequest,
)
from api.permissions import enforce_ai_quota
from services import firebase_service, listening_service, tts_service

router = APIRouter(prefix="/api/v1/listening", tags=["listening"])


def _pick_topic(user: dict, requested: str) -> str:
    if requested and requested.strip():
        return requested.strip()
    topics = user.get("topics") or []
    return topics[0] if topics else "general"


def _audio_url(exercise_id: str) -> str:
    return f"/api/v1/listening/{exercise_id}/audio"


def _to_view(doc: dict) -> ListeningExerciseView:
    questions_view = [
        {"question": q.get("question", ""), "options": q.get("options", [])}
        for q in (doc.get("questions") or [])
    ]
    return ListeningExerciseView(
        id=doc["id"],
        exercise_type=doc.get("exercise_type", "dictation"),
        band=float(doc.get("band", 6.0)),
        topic=doc.get("topic", ""),
        title=doc.get("title", ""),
        duration_estimate_sec=int(doc.get("duration_estimate_sec", 30)),
        audio_url=_audio_url(doc["id"]),
        created_at=doc.get("created_at"),
        submitted=bool(doc.get("submitted", False)),
        score=doc.get("score"),
        display_text=doc.get("display_text", ""),
        questions=questions_view,
    )


def _to_result(doc: dict, *, hide_answers: bool = False) -> ListeningExerciseResult:
    """Build the result payload.

    When hide_answers is True (pre-submit reads), the transcript, gap-fill
    answer key, and per-question correct indices/explanations are stripped
    so the learner can't peek before submitting.
    """
    if hide_answers:
        transcript = ""
        blanks = [
            {"index": b.get("index", i), "answer": ""}
            for i, b in enumerate(doc.get("blanks") or [])
        ]
        questions = [
            {
                "question": q.get("question", ""),
                "options": q.get("options", []),
                "correct_index": -1,
                "explanation_vi": "",
            }
            for q in (doc.get("questions") or [])
        ]
        dictation_diff: list[dict] = []
        gap_fill_results: list[dict] = []
        comprehension_results: list[dict] = []
        misheard_words: list[str] = []
    else:
        transcript = doc.get("transcript", "")
        blanks = doc.get("blanks", [])
        questions = doc.get("questions", [])
        dictation_diff = doc.get("dictation_diff", [])
        gap_fill_results = doc.get("gap_fill_results", [])
        comprehension_results = doc.get("comprehension_results", [])
        misheard_words = doc.get("misheard_words", [])

    return ListeningExerciseResult(
        id=doc["id"],
        exercise_type=doc.get("exercise_type", "dictation"),
        band=float(doc.get("band", 6.0)),
        topic=doc.get("topic", ""),
        title=doc.get("title", ""),
        duration_estimate_sec=int(doc.get("duration_estimate_sec", 30)),
        audio_url=_audio_url(doc["id"]),
        created_at=doc.get("created_at"),
        submitted=bool(doc.get("submitted", False)),
        score=doc.get("score"),
        transcript=transcript,
        display_text=doc.get("display_text", ""),
        blanks=blanks,
        questions=questions,
        dictation_diff=dictation_diff,
        gap_fill_results=gap_fill_results,
        comprehension_results=comprehension_results,
        misheard_words=misheard_words,
    )


def _to_history_item(doc: dict) -> ListeningHistoryItem:
    return ListeningHistoryItem(
        id=doc["id"],
        exercise_type=doc.get("exercise_type", "dictation"),
        title=doc.get("title", ""),
        band=float(doc.get("band", 6.0)),
        score=doc.get("score"),
        submitted=bool(doc.get("submitted", False)),
        created_at=doc.get("created_at"),
    )


@router.post(
    "/generate",
    response_model=ListeningExerciseView,
    dependencies=[Depends(enforce_ai_quota("listening"))],
)
async def generate_listening(
    body: ListeningGenerateRequest,
    user: dict = Depends(get_current_user),
) -> ListeningExerciseView:
    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    topic = _pick_topic(user, body.topic)

    try:
        exercise = await listening_service.generate_exercise(
            body.exercise_type, band, topic,
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Listening service returned invalid JSON: {exc}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    # Render audio in background thread (gTTS is blocking)
    audio_path = await asyncio.to_thread(
        tts_service.generate_passage_audio, exercise["transcript"],
    )
    if not audio_path:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audio generation failed.",
        )

    exercise_id = await asyncio.to_thread(
        firebase_service.save_listening_exercise, user["id"], exercise,
    )
    stored = await asyncio.to_thread(
        firebase_service.get_listening_exercise, user["id"], exercise_id,
    )
    return _to_view(stored or {"id": exercise_id, **exercise})


@router.get("/history", response_model=ListeningHistoryResponse)
async def listening_history(
    user: dict = Depends(get_current_user),
) -> ListeningHistoryResponse:
    docs = await asyncio.to_thread(
        firebase_service.list_listening_exercises, user["id"], 50,
    )
    return ListeningHistoryResponse(items=[_to_history_item(d) for d in docs])


@router.get("/{exercise_id}", response_model=ListeningExerciseResult)
async def get_listening(
    exercise_id: str,
    user: dict = Depends(get_current_user),
) -> ListeningExerciseResult:
    doc = await asyncio.to_thread(
        firebase_service.get_listening_exercise, user["id"], exercise_id,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found.",
        )
    return _to_result(doc, hide_answers=not doc.get("submitted", False))


@router.get("/{exercise_id}/audio")
async def get_listening_audio(
    exercise_id: str,
    user: dict = Depends(get_current_user),
) -> FileResponse:
    doc = await asyncio.to_thread(
        firebase_service.get_listening_exercise, user["id"], exercise_id,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found.",
        )
    transcript = doc.get("transcript", "")
    path = await asyncio.to_thread(tts_service.generate_passage_audio, transcript)
    if not path or not os.path.exists(path):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audio unavailable.",
        )
    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"listening_{exercise_id}.mp3",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post("/{exercise_id}/submit", response_model=ListeningExerciseResult)
async def submit_listening(
    exercise_id: str,
    body: ListeningSubmitRequest,
    user: dict = Depends(get_current_user),
) -> ListeningExerciseResult:
    doc = await asyncio.to_thread(
        firebase_service.get_listening_exercise, user["id"], exercise_id,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found.",
        )
    if doc.get("submitted"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exercise already submitted.",
        )

    exercise_type = doc.get("exercise_type", "dictation")
    update: dict = {"submitted": True}

    if exercise_type == "dictation":
        result = listening_service.score_dictation(
            body.user_text, doc.get("transcript", ""),
        )
        update["score"] = result["score"]
        update["dictation_diff"] = result["diff"]
        update["misheard_words"] = result["misheard_words"]
        update["user_text"] = body.user_text
    elif exercise_type == "gap_fill":
        result = listening_service.score_gap_fill(
            body.answers, doc.get("blanks", []),
        )
        update["score"] = result["score"]
        update["gap_fill_results"] = result["per_blank"]
        update["user_answers"] = body.answers
    elif exercise_type == "comprehension":
        indices: list[int] = []
        for a in body.answers:
            try:
                indices.append(int(a))
            except (TypeError, ValueError):
                indices.append(-1)
        result = listening_service.score_comprehension(
            indices, doc.get("questions", []),
        )
        update["score"] = result["score"]
        update["comprehension_results"] = result["per_question"]
        update["user_indices"] = indices
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown exercise_type: {exercise_type}",
        )

    await asyncio.to_thread(
        firebase_service.update_listening_exercise,
        user["id"], exercise_id, update,
    )

    merged = {**doc, **update}
    return _to_result(merged)
