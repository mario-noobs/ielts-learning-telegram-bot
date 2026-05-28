from unittest.mock import AsyncMock, patch

import pytest

from api.errors import ERR, ApiError
from services import vocab_roadmap_service


def _pool(
    pool_id: str,
    title: str,
    difficulty: int,
    topics: list[str],
) -> dict:
    return {
        "id": pool_id,
        "title": title,
        "source": "seed",
        "source_theme": title.lower().replace(" ", "_"),
        "word_count": 50,
        "difficulty": difficulty,
        "difficulty_min": difficulty,
        "difficulty_max": difficulty,
        "topics": topics,
        "source_url": "",
        "license": "CC BY 4.0",
        "provenance": "seed",
    }


def test_target_band_maps_to_difficulty():
    assert vocab_roadmap_service.target_difficulty_for_band(5.5) == 1
    assert vocab_roadmap_service.target_difficulty_for_band(6.0) == 2
    assert vocab_roadmap_service.target_difficulty_for_band(7.0) == 3
    assert vocab_roadmap_service.target_difficulty_for_band(7.5) == 4
    assert vocab_roadmap_service.target_difficulty_for_band(8.0) == 5


def test_recommends_matching_band_and_weak_topic_first():
    pools = [
        _pool("advanced", "Advanced", 5, ["arts"]),
        _pool("upper", "Upper Intermediate", 3, ["environment"]),
        _pool("elementary", "Elementary", 1, ["education"]),
    ]
    user = {
        "id": "u1",
        "target_band": 7.0,
        "topics": ["environment"],
        "total_words": 40,
    }
    with patch("services.vocab_roadmap_service.public_vocab_pool_service.list_public_pools",
               return_value=pools), \
         patch("services.vocab_roadmap_service.firebase_service.count_words_by_topic_with_mastery",
               return_value={"environment": {"total": 10, "mastered": 2}}), \
         patch("services.vocab_roadmap_service.firebase_service.get_due_words",
               return_value=[{"topic": "environment"}]):
        result = vocab_roadmap_service.recommend_public_pools(user)

    assert result["target_difficulty"] == 3
    assert result["items"][0]["id"] == "upper"
    reason_codes = [reason["code"] for reason in result["items"][0]["reasons"]]
    assert "target_band_match" in reason_codes
    assert "weak_topic" in reason_codes


def test_recommendations_fall_back_to_target_band_without_progress():
    pools = [
        _pool("pre", "Pre Intermediate", 2, ["education"]),
        _pool("upper", "Upper Intermediate", 4, ["technology"]),
    ]
    user = {
        "id": "u1",
        "target_band": 6.0,
        "topics": [],
        "total_words": 0,
    }
    with patch("services.vocab_roadmap_service.public_vocab_pool_service.list_public_pools",
               return_value=pools), \
         patch("services.vocab_roadmap_service.firebase_service.count_words_by_topic_with_mastery",
               return_value={}), \
         patch("services.vocab_roadmap_service.firebase_service.get_due_words",
               return_value=[]):
        result = vocab_roadmap_service.recommend_public_pools(user)

    assert result["target_difficulty"] == 2
    assert result["items"][0]["id"] == "pre"
    assert any(
        reason["code"] == "target_band_match"
        for reason in result["items"][0]["reasons"]
    )


@pytest.mark.asyncio
async def test_consult_returns_insufficient_data_without_ai_or_quota():
    context = {
        "target_band": 7.0,
        "total_words": 2,
        "reviewed_words": 0,
        "due_count": 0,
        "weak_due_count": 0,
        "topic_summaries": [],
        "recommended_pools": [],
        "missing_requirements": [
            {
                "code": "save_more_words",
                "current": 2,
                "required": vocab_roadmap_service.MIN_CONSULT_WORDS,
                "route": "/learn/vocab/add",
            },
        ],
    }
    with patch("services.vocab_roadmap_service.build_consult_context",
               return_value=context), \
         patch("services.vocab_roadmap_service.ai_service.generate_json",
               new=AsyncMock()) as ai:
        result = await vocab_roadmap_service.generate_vocab_consult(
            {"id": "u1", "plan": "free"},
        )

    assert result["status"] == "insufficient_data"
    assert result["confidence"] == "low"
    assert result["missing_requirements"][0]["code"] == "save_more_words"
    ai.assert_not_called()


@pytest.mark.asyncio
async def test_consult_validates_ai_response_and_sanitizes_routes():
    context = {
        "target_band": 7.0,
        "total_words": 40,
        "reviewed_words": 12,
        "due_count": 4,
        "weak_due_count": 1,
        "topic_summaries": [{"topic": "education", "total": 12, "mastered": 2}],
        "recommended_pools": [{"title": "Upper Intermediate"}],
        "missing_requirements": [],
    }
    ai_response = {
        "confidence": "medium",
        "readiness_range": "6.0-6.5",
        "summary": "Vocabulary is growing, but review consistency is the gap.",
        "strengths": [
            {"title": "Topic coverage", "detail": "Education has enough saved words.", "evidence": "12 words"}
        ],
        "gaps": [
            {"title": "Weak review queue", "detail": "Some due words need repeat practice.", "evidence": "4 due"}
        ],
        "next_actions": [
            {
                "title": "Review due words",
                "detail": "Clear today's due cards first.",
                "route": "/unsafe",
                "priority": "high",
            }
        ],
    }
    with patch("services.vocab_roadmap_service.build_consult_context",
               return_value=context), \
         patch("services.vocab_roadmap_service.ai_service.generate_json",
               new=AsyncMock(return_value=ai_response)):
        result = await vocab_roadmap_service.generate_vocab_consult(
            {"id": "u1", "plan": "free"},
            charge_quota=False,
        )

    assert result["status"] == "ready"
    assert result["readiness_range"] == "6.0-6.5"
    assert "not an official IELTS band score" in result["disclaimer"]
    assert result["next_actions"][0]["route"] == "/learn/review"


@pytest.mark.asyncio
async def test_consult_rejects_malformed_ai_response():
    context = {
        "target_band": 7.0,
        "total_words": 40,
        "reviewed_words": 12,
        "due_count": 0,
        "weak_due_count": 0,
        "topic_summaries": [],
        "recommended_pools": [],
        "missing_requirements": [],
    }
    with patch("services.vocab_roadmap_service.build_consult_context",
               return_value=context), \
         patch("services.vocab_roadmap_service.ai_service.generate_json",
               new=AsyncMock(return_value={"confidence": "sure"})):
        with pytest.raises(vocab_roadmap_service.VocabConsultGenerationError):
            await vocab_roadmap_service.generate_vocab_consult(
                {"id": "u1", "plan": "free"},
                charge_quota=False,
            )


@pytest.mark.asyncio
async def test_consult_plan_limit_blocks_before_ai_call():
    context = {
        "target_band": 7.0,
        "total_words": 40,
        "reviewed_words": 12,
        "due_count": 0,
        "weak_due_count": 0,
        "topic_summaries": [],
        "recommended_pools": [],
        "missing_requirements": [],
    }
    error = ApiError(ERR.quota_daily_exceeded, plan_quota=10)
    with patch("services.vocab_roadmap_service.build_consult_context",
               return_value=context), \
         patch("services.admin.quota_service.check_and_increment",
               side_effect=error), \
         patch("services.vocab_roadmap_service.ai_service.generate_json",
               new=AsyncMock()) as ai:
        with pytest.raises(ApiError) as exc:
            await vocab_roadmap_service.generate_vocab_consult(
                {"id": "u1", "plan": "free"},
            )

    assert exc.value.code == ERR.quota_daily_exceeded.code
    ai.assert_not_called()
