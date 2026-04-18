import asyncio

from fastapi import APIRouter, Depends, Query

from api.auth import get_current_user
from api.models.progress import (
    ProgressHistoryResponse,
    ProgressPrediction,
    ProgressResponse,
    ProgressSnapshot,
    TrendPoint,
)
from services import progress_service

router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


def _to_trend_point(doc: dict) -> TrendPoint:
    skills = doc.get("skills", {}) or {}
    vocab = (skills.get("vocabulary") or {}).get("band", 0.0)
    writing = (skills.get("writing") or {}).get("band", 0.0)
    listening = (skills.get("listening") or {}).get("band", 0.0)
    return TrendPoint(
        date=doc.get("date", ""),
        overall_band=float(doc.get("overall_band", 0.0)),
        vocabulary_band=float(vocab),
        writing_band=float(writing),
        listening_band=float(listening),
    )


def _to_snapshot(doc: dict) -> ProgressSnapshot:
    return ProgressSnapshot(
        overall_band=float(doc.get("overall_band", 0.0)),
        skills=doc.get("skills", {}),
        target_band=float(doc.get("target_band", 7.0)),
        date=doc.get("date"),
        generated_at=doc.get("generated_at"),
    )


@router.get("", response_model=ProgressResponse)
async def get_progress(
    user: dict = Depends(get_current_user),
) -> ProgressResponse:
    """Return the learner's current per-skill band + 30-day trend + predictions.

    Always computes a fresh snapshot from source data (vocabulary, writing,
    listening). Today's snapshot is persisted idempotently so trends fill in
    without a separate scheduler job.
    """
    snapshot = await asyncio.to_thread(progress_service.build_snapshot, user)

    await asyncio.to_thread(
        progress_service.save_today_snapshot, user, snapshot,
    )

    history = await asyncio.to_thread(
        progress_service.history_window, user["id"], 30,
    )
    trend = [_to_trend_point(h) for h in history]

    predictions = [
        ProgressPrediction(
            days_ahead=offset,
            projected_band=progress_service.predict_band(history, offset),
        )
        for offset in (30, 60, 90)
    ]

    return ProgressResponse(
        snapshot=_to_snapshot(snapshot),
        trend=trend,
        predictions=predictions,
    )


@router.get("/history", response_model=ProgressHistoryResponse)
async def get_progress_history(
    days: int = Query(30, ge=1, le=90),
    user: dict = Depends(get_current_user),
) -> ProgressHistoryResponse:
    history = await asyncio.to_thread(
        progress_service.history_window, user["id"], days,
    )
    return ProgressHistoryResponse(
        items=[_to_trend_point(h) for h in history],
    )


# Recommendations route (US-5.3) is added via a separate import in main.
# Keeping the progress router narrowly scoped to the snapshot/history payloads.


def _snapshot_for_tests(doc: dict) -> ProgressSnapshot:  # pragma: no cover
    return _to_snapshot(doc)
