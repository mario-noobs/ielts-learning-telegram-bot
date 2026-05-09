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
    """Return all IELTS topics with the user's word count + mastered count.

    /learn/vocab home renders a card per topic with a mastery progress
    bar — sourcing both fields from one call avoids loading the full
    word list just to compute aggregates (US-#231 follow-up).
    """
    topics = _load_topics()
    breakdown = await asyncio.to_thread(
        firebase_service.count_words_by_topic_with_mastery, user["id"],
    )

    items = [
        TopicSummary(
            id=t["id"],
            name=t.get("name", t["id"]),
            word_count=breakdown.get(t["id"], {}).get("total", 0),
            mastered_count=breakdown.get(t["id"], {}).get("mastered", 0),
            subtopics=t.get("subtopics", []),
        )
        for t in topics
    ]
    total_words = sum(b.get("total", 0) for b in breakdown.values())
    return TopicsResponse(items=items, total_words=total_words)
