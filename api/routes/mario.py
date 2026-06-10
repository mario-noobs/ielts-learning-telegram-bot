"""Mario onboarding assistant API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Response

from api.auth import get_current_user
from api.models.mario import MarioEventRequest, MarioStateResponse
from services import mario_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mario", tags=["mario"])


@router.get("/state", response_model=MarioStateResponse)
async def get_mario_state(
    route: str | None = Query(default=None, max_length=120),
    user: dict = Depends(get_current_user),
) -> MarioStateResponse:
    return mario_service.build_state(user, route)


@router.post("/events", status_code=204)
async def track_mario_event(
    body: MarioEventRequest,
    user: dict = Depends(get_current_user),
) -> Response:
    metadata_keys = sorted(body.metadata.keys())
    logger.info(
        "mario_event user_id=%s event=%s route=%s suggestion_id=%s metadata_keys=%s",
        user["id"],
        body.event,
        body.route,
        body.suggestion_id,
        metadata_keys,
    )
    return Response(status_code=204)
