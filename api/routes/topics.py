import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.models.vocabulary import TopicsResponse, TopicSummary
from services import firebase_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/topics", tags=["topics"])

_TOPICS_FILE = Path(__file__).resolve().parents[2] / "data" / "ielts_topics.json"


def _load_topics() -> list[dict]:
    try:
        with _TOPICS_FILE.open("r") as f:
            return json.load(f).get("topics", [])
    except FileNotFoundError:
        logger.warning("Topics file not found at %s", _TOPICS_FILE)
        return []


@router.get("", response_model=TopicsResponse)
async def list_topics(user: dict = Depends(get_current_user)) -> TopicsResponse:
    """Return all IELTS topics with the user's word count per topic."""
    topics = _load_topics()
    counts = await asyncio.to_thread(firebase_service.count_words_by_topic, user["id"])

    items = [
        TopicSummary(
            id=t["id"],
            name=t.get("name", t["id"]),
            word_count=counts.get(t["id"], 0),
            subtopics=t.get("subtopics", []),
        )
        for t in topics
    ]
    return TopicsResponse(items=items, total_words=sum(counts.values()))
