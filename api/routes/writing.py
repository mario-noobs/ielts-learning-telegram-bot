import asyncio
import json

from fastapi import APIRouter, Depends

import config
from api.auth import get_current_user
from api.errors import ERR, ApiError
from api.models.writing import (
    TaskPromptRequest,
    TaskPromptResponse,
    WritingHistoryItem,
    WritingHistoryResponse,
    WritingReviseRequest,
    WritingSubmission,
    WritingSubmitRequest,
)
from api.permissions import enforce_ai_quota
from services import firebase_service, writing_service

router = APIRouter(prefix="/api/v1/writing", tags=["writing"])

_MIN_WORDS = 20
_PREVIEW_LEN = 80


def _preview(text: str) -> str:
    clean = text.strip().replace("\n", " ")
    return clean[:_PREVIEW_LEN] + ("…" if len(clean) > _PREVIEW_LEN else "")


def _to_submission(doc: dict) -> WritingSubmission:
    return WritingSubmission(
        id=doc["id"],
        text=doc.get("text", ""),
        task_type=doc.get("task_type", "task2"),
        prompt=doc.get("prompt", ""),
        overall_band=float(doc.get("overall_band", 0.0)),
        scores=doc.get("scores", {}),
        criterion_feedback=doc.get("criterion_feedback", {}),
        paragraph_annotations=doc.get("paragraph_annotations", []),
        summary_vi=doc.get("summary_vi", ""),
        word_count=int(doc.get("word_count", 0)),
        created_at=doc.get("created_at"),
        original_id=doc.get("original_id"),
        delta_band=doc.get("delta_band"),
    )


def _to_history_item(doc: dict) -> WritingHistoryItem:
    return WritingHistoryItem(
        id=doc["id"],
        task_type=doc.get("task_type", "task2"),
        prompt_preview=_preview(doc.get("prompt", "") or doc.get("text", "")),
        overall_band=float(doc.get("overall_band", 0.0)),
        word_count=int(doc.get("word_count", 0)),
        created_at=doc.get("created_at"),
        original_id=doc.get("original_id"),
    )


async def _score_and_store(
    user: dict,
    text: str,
    task_type: str,
    prompt: str,
    original_id: str | None = None,
) -> WritingSubmission:
    word_count = writing_service.count_words(text)
    if word_count < _MIN_WORDS:
        raise ApiError(
            ERR.writing_too_short,
            min_words=_MIN_WORDS,
            got=word_count,
        )

    try:
        feedback = await writing_service.score_essay(text, task_type, prompt)
    except json.JSONDecodeError as exc:
        raise ApiError(ERR.writing_scoring_failed, detail=str(exc))

    data: dict = {
        "text": text,
        "task_type": task_type,
        "prompt": prompt,
        "word_count": word_count,
        **feedback,
    }
    if original_id:
        data["original_id"] = original_id
        original = await asyncio.to_thread(
            firebase_service.get_writing_submission, user["id"], original_id
        )
        if original:
            data["delta_band"] = round(
                data["overall_band"] - float(original.get("overall_band", 0.0)), 1
            )

    submission_id = await asyncio.to_thread(
        firebase_service.save_writing_submission, user["id"], data
    )

    stored = await asyncio.to_thread(
        firebase_service.get_writing_submission, user["id"], submission_id
    )
    return _to_submission(stored or {"id": submission_id, **data})


@router.post(
    "/submit",
    response_model=WritingSubmission,
    dependencies=[Depends(enforce_ai_quota("writing"))],
)
async def submit_writing(
    body: WritingSubmitRequest,
    user: dict = Depends(get_current_user),
) -> WritingSubmission:
    return await _score_and_store(user, body.text, body.task_type, body.prompt)


@router.post("/prompt", response_model=TaskPromptResponse)
async def generate_prompt(
    body: TaskPromptRequest,
    user: dict = Depends(get_current_user),
) -> TaskPromptResponse:
    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    result = await writing_service.generate_task_prompt(body.task_type, band)
    return TaskPromptResponse(**result)


@router.get("/history", response_model=WritingHistoryResponse)
async def writing_history(
    user: dict = Depends(get_current_user),
) -> WritingHistoryResponse:
    docs = await asyncio.to_thread(
        firebase_service.list_writing_submissions, user["id"], 50
    )
    return WritingHistoryResponse(items=[_to_history_item(d) for d in docs])


@router.get("/{submission_id}", response_model=WritingSubmission)
async def get_writing(
    submission_id: str,
    user: dict = Depends(get_current_user),
) -> WritingSubmission:
    doc = await asyncio.to_thread(
        firebase_service.get_writing_submission, user["id"], submission_id
    )
    if not doc:
        raise ApiError(ERR.writing_submission_not_found, submission_id=submission_id)
    return _to_submission(doc)


@router.post("/{submission_id}/revise", response_model=WritingSubmission)
async def revise_writing(
    submission_id: str,
    body: WritingReviseRequest,
    user: dict = Depends(get_current_user),
) -> WritingSubmission:
    original = await asyncio.to_thread(
        firebase_service.get_writing_submission, user["id"], submission_id
    )
    if not original:
        raise ApiError(ERR.writing_submission_not_found, submission_id=submission_id)

    return await _score_and_store(
        user,
        body.text,
        original.get("task_type", "task2"),
        original.get("prompt", ""),
        original_id=submission_id,
    )
