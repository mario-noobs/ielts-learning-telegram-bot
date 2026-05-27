from unittest.mock import patch

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
