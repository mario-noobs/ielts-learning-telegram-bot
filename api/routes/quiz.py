import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user
from api.models.quiz import (
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizQuestion,
    QuizStartRequest,
    QuizStartResponse,
    SRSUpdate,
)
from api.permissions import enforce_ai_quota
from services import firebase_service, quiz_service
from services.srs_service import get_word_strength

router = APIRouter(prefix="/api/v1/quiz", tags=["quiz"])

DEFAULT_QUIZ_COUNT = 5


def _sanitize(question: dict, qid: str) -> QuizQuestion:
    return QuizQuestion(
        id=qid,
        type=question.get("type", "multiple_choice"),
        question=question.get("question", ""),
        options=question.get("options", []) or [],
        word_id=question.get("word_id", ""),
    )


def _normalize_answer(answer: str, question: dict) -> str:
    """Accept letter (A–D) or 0-based numeric index; pass paraphrase through."""
    q_type = question.get("type", "multiple_choice")
    if q_type == "paraphrase":
        return answer
    stripped = answer.strip()
    if stripped.isdigit():
        idx = int(stripped)
        options = question.get("options", [])
        if 0 <= idx < len(options):
            return chr(ord("A") + idx)
    return stripped


@router.post(
    "/start",
    response_model=QuizStartResponse,
    dependencies=[Depends(enforce_ai_quota("quiz"))],
)
async def start_quiz(
    body: QuizStartRequest | None = None,
    user: dict = Depends(get_current_user),
) -> QuizStartResponse:
    """Generate a batch of quiz questions and open a session."""
    count = (body.count if body and body.count else DEFAULT_QUIZ_COUNT)
    types = body.types if body else None
    word_ids = body.word_ids if body else None

    questions = await quiz_service.generate_quiz_batch(
        telegram_id=user["id"], count=count, types=types, word_ids=word_ids
    )
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not enough vocabulary to generate {count} questions. "
                   f"Add more words first.",
        )

    session_id = uuid.uuid4().hex
    for i, q in enumerate(questions):
        q["id"] = f"q{i}"

    await asyncio.to_thread(
        firebase_service.save_quiz_session, user["id"], session_id, questions
    )

    return QuizStartResponse(
        session_id=session_id,
        questions=[_sanitize(q, q["id"]) for q in questions],
    )


@router.post("/answer", response_model=QuizAnswerResponse)
async def answer_quiz(
    body: QuizAnswerRequest,
    user: dict = Depends(get_current_user),
) -> QuizAnswerResponse:
    """Submit an answer for a quiz question; return feedback + SRS change."""
    session = await asyncio.to_thread(
        firebase_service.get_quiz_session, user["id"], body.session_id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found or expired.",
        )

    if body.question_id in (session.get("answered_ids") or []):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This question has already been answered.",
        )

    question = next(
        (q for q in session.get("questions", []) if q.get("id") == body.question_id),
        None,
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {body.question_id} not in session.",
        )

    word_id = question.get("word_id", "")
    old_word = None
    if word_id:
        old_word = await asyncio.to_thread(
            firebase_service.get_word_by_id, user["id"], word_id
        )
    old_strength = get_word_strength(old_word or {})

    normalized = _normalize_answer(body.answer, question)
    is_correct, feedback = await quiz_service.check_answer(
        question, normalized, user["id"]
    )

    new_word = None
    if word_id:
        new_word = await asyncio.to_thread(
            firebase_service.get_word_by_id, user["id"], word_id
        )
    new_strength = get_word_strength(new_word or {})

    await asyncio.to_thread(
        firebase_service.mark_session_question_answered,
        user["id"], body.session_id, body.question_id,
    )

    next_review = (new_word or {}).get("srs_next_review")
    return QuizAnswerResponse(
        is_correct=is_correct,
        feedback=feedback,
        srs_update=SRSUpdate(
            next_review=next_review,
            old_strength=old_strength,
            new_strength=new_strength,
            strength_change=old_strength != new_strength,
        ),
    )
