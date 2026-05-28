"""Integration tests for /api/v1/vocabulary endpoints (US-1.1)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.errors import ERR, ApiError
from api.main import create_app
from services import vocab_roadmap_service

FAKE_USER = {
    "id": "test-user-1",
    "name": "Alice",
    "target_band": 7.0,
    "topics": ["education", "environment"],
}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def _fake_vocab_doc(word: str, added_at: datetime, topic: str = "education") -> dict:
    return {
        "id": f"doc-{word}",
        "word": word,
        "definition": f"{word} definition",
        "definition_vi": f"{word} vi",
        "ipa": "/test/",
        "part_of_speech": "noun",
        "topic": topic,
        "example_en": f"Example with {word}.",
        "example_vi": "Vi example.",
        "source": 1,
        "srs_interval": 1,
        "srs_ease": 2.5,
        "srs_reps": 0,
        "srs_next_review": added_at,
        "times_correct": 0,
        "times_incorrect": 0,
        "added_at": added_at,
    }


def _complete_detail(word: str) -> dict:
    return {
        "word": word,
        "ipa": "/test/",
        "syllable_stress": "TEST",
        "part_of_speech": "noun",
        "definition_en": f"{word} definition",
        "definition_vi": f"{word} vi",
        "collocations": [{"phrase": f"{word} example", "label": "neutral"}],
        "word_family": [word],
        "ielts_tip": f"Use {word} in academic writing.",
        "examples_by_band": {
            "7": {
                "en": f"Example with {word}.",
                "vi": "Vi example.",
            }
        },
    }


def _fake_public_pool() -> dict:
    return {
        "id": "pool-1",
        "title": "Cambridge IELTS 18",
        "source": "cambridge",
        "source_theme": "ielts_18",
        "word_count": 30,
        "difficulty": 4,
        "difficulty_min": 3,
        "difficulty_max": 5,
        "topics": ["education"],
        "source_url": "https://example.test/source",
        "license": "CC BY 4.0",
        "provenance": "Seed import",
    }


def _fake_public_pool_word() -> dict:
    return {
        "id": "master-1",
        "word": "scalability",
        "definition_en": "ability to be enlarged or increased",
        "definition_vi": "kha nang mo rong",
        "ipa": "skaelability",
        "part_of_speech": "noun",
        "example_en": "Scalability matters.",
        "example_vi": "Kha nang mo rong rat quan trong.",
        "difficulty": 4,
        "topic": "technology",
        "source_ref": "unit-1",
    }


class TestListVocabulary:
    def test_ac1_returns_paginated_words_with_srs(self, client):
        """AC1: GET /api/v1/vocabulary returns paginated list with SRS data."""
        ts = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
        docs = [_fake_vocab_doc(f"word{i}", ts) for i in range(3)]

        with patch("api.routes.vocabulary.firebase_service.get_user_vocabulary_page",
                   return_value=docs) as mock_fn:
            response = client.get("/api/v1/vocabulary?limit=20")

        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 3
        assert body["items"][0]["word"] == "word0"
        assert body["items"][0]["srs_interval"] == 1
        assert body["items"][0]["srs_ease"] == 2.5
        assert body["items"][0]["source"] == "daily"
        assert "strength" in body["items"][0]
        assert body["next_cursor"] is None  # fewer than limit
        mock_fn.assert_called_once_with("test-user-1", 20, None, None, None, None)

    def test_next_cursor_populated_when_page_full(self, client):
        """When items count equals limit, next_cursor is the last added_at."""
        ts = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
        docs = [_fake_vocab_doc(f"w{i}", ts) for i in range(2)]

        with patch("api.routes.vocabulary.firebase_service.get_user_vocabulary_page",
                   return_value=docs):
            response = client.get("/api/v1/vocabulary?limit=2")

        assert response.status_code == 200
        assert response.json()["next_cursor"] is not None

    def test_cursor_parsed_and_forwarded(self, client):
        """Cursor is parsed into datetime and passed through to service."""
        cursor = "2026-04-17T10:00:00+00:00"

        with patch("api.routes.vocabulary.firebase_service.get_user_vocabulary_page",
                   return_value=[]) as mock_fn:
            response = client.get("/api/v1/vocabulary",
                                  params={"limit": 10, "cursor": cursor})

        assert response.status_code == 200
        assert response.json()["items"] == []
        args = mock_fn.call_args.args
        assert args[0] == "test-user-1"
        assert args[1] == 10
        assert args[2] == datetime.fromisoformat(cursor)

    def test_invalid_cursor_returns_400(self, client):
        response = client.get("/api/v1/vocabulary?cursor=not-a-date")
        assert response.status_code == 400

    def test_source_filter_parsed_and_forwarded(self, client):
        with patch("api.routes.vocabulary.firebase_service.get_user_vocabulary_page",
                   return_value=[]) as mock_fn:
            response = client.get("/api/v1/vocabulary", params={"source": "manual"})

        assert response.status_code == 200
        mock_fn.assert_called_once_with("test-user-1", 20, None, None, None, 3)

    def test_all_source_filter_is_ignored(self, client):
        with patch("api.routes.vocabulary.firebase_service.get_user_vocabulary_page",
                   return_value=[]) as mock_fn:
            response = client.get("/api/v1/vocabulary", params={"source": "all"})

        assert response.status_code == 200
        mock_fn.assert_called_once_with("test-user-1", 20, None, None, None, None)

    def test_invalid_source_filter_returns_400(self, client):
        response = client.get("/api/v1/vocabulary?source=unknown")
        assert response.status_code == 400

    def test_empty_vocabulary(self, client):
        with patch("api.routes.vocabulary.firebase_service.get_user_vocabulary_page",
                   return_value=[]):
            response = client.get("/api/v1/vocabulary")
        assert response.status_code == 200
        assert response.json() == {"items": [], "next_cursor": None}


class TestPublicVocabPools:
    def test_list_returns_disabled_when_feature_flag_off(self, client):
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=False) as flag, \
             patch("api.routes.vocabulary.public_vocab_pool_service.list_public_pools") as service:
            response = client.get("/api/v1/vocabulary/public-pools")

        assert response.status_code == 200
        assert response.json() == {"enabled": False, "items": []}
        flag.assert_called_once_with("public_vocab_pools", "test-user-1")
        service.assert_not_called()

    def test_list_returns_read_only_public_pools_with_filters(self, client):
        pool = _fake_public_pool()
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=True), \
             patch("api.routes.vocabulary.public_vocab_pool_service.list_public_pools",
                   return_value=[pool]) as service:
            response = client.get(
                "/api/v1/vocabulary/public-pools",
                params={"difficulty": 4, "topic": "education"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["items"][0]["title"] == "Cambridge IELTS 18"
        assert body["items"][0]["source"] == "cambridge"
        assert body["items"][0]["license"] == "CC BY 4.0"
        service.assert_called_once_with(difficulty=4, topic="education")

    def test_recommendations_use_rule_service_when_feature_flag_enabled(self, client):
        recommendation = {
            **_fake_public_pool(),
            "reasons": [
                {"code": "target_band_match"},
                {"code": "selected_topic", "topic": "education"},
            ],
        }
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=True), \
             patch("api.routes.vocabulary.vocab_roadmap_service.recommend_public_pools",
                   return_value={"target_difficulty": 3, "items": [recommendation]}) as service:
            response = client.get("/api/v1/vocabulary/public-pools/recommendations")

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["target_difficulty"] == 3
        assert body["items"][0]["id"] == "pool-1"
        assert body["items"][0]["reasons"][1]["topic"] == "education"
        service.assert_called_once()

    def test_recommendations_return_disabled_when_feature_flag_off(self, client):
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=False), \
             patch("api.routes.vocabulary.vocab_roadmap_service.recommend_public_pools") as service:
            response = client.get("/api/v1/vocabulary/public-pools/recommendations")

        assert response.status_code == 200
        assert response.json() == {"enabled": False, "target_difficulty": None, "items": []}
        service.assert_not_called()

    def test_roadmap_consult_returns_schema_response(self, client):
        consult = {
            "status": "ready",
            "disclaimer": "This is not official.",
            "confidence": "medium",
            "readiness_range": "6.0-6.5",
            "summary": "Focus on review consistency.",
            "data_used": [{"label": "My Words", "value": "40 saved, 12 reviewed"}],
            "missing_requirements": [],
            "strengths": [
                {"title": "Coverage", "detail": "Good education coverage.", "evidence": "12 words"}
            ],
            "gaps": [
                {"title": "Reviews", "detail": "Some weak words remain.", "evidence": "4 due"}
            ],
            "next_actions": [
                {
                    "title": "Review",
                    "detail": "Clear due cards.",
                    "route": "/learn/review",
                    "priority": "high",
                }
            ],
        }
        with patch("api.routes.vocabulary.vocab_roadmap_service.generate_vocab_consult",
                   new=AsyncMock(return_value=consult)) as service:
            response = client.post("/api/v1/vocabulary/roadmap/consult")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["confidence"] == "medium"
        assert body["next_actions"][0]["route"] == "/learn/review"
        service.assert_awaited_once()

    def test_roadmap_consult_returns_502_for_malformed_ai(self, client):
        with patch(
            "api.routes.vocabulary.vocab_roadmap_service.generate_vocab_consult",
            new=AsyncMock(
                side_effect=vocab_roadmap_service.VocabConsultGenerationError("bad")
            ),
        ):
            response = client.post("/api/v1/vocabulary/roadmap/consult")

        assert response.status_code == 502
        assert response.json()["error"]["code"] == ERR.vocab_consult_failed.code

    def test_detail_returns_words_without_mutating_user_collection(self, client):
        detail = {
            "pool": _fake_public_pool(),
            "words": [
                {
                    "id": "w1",
                    "word": "scalability",
                    "definition_en": "ability to be enlarged or increased",
                    "definition_vi": "kha nang mo rong",
                    "ipa": "skaelability",
                    "part_of_speech": "noun",
                    "difficulty": 4,
                    "topic": "technology",
                    "source_ref": "unit-1",
                }
            ],
        }
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=True), \
             patch("api.routes.vocabulary.public_vocab_pool_service.get_public_pool_detail",
                   return_value=detail) as service, \
             patch("api.routes.vocabulary.firebase_service.get_user_word_list",
                   return_value=[]), \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists") as add_word:
            response = client.get("/api/v1/vocabulary/public-pools/pool-1")

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["pool"]["id"] == "pool-1"
        assert body["words"][0]["word"] == "scalability"
        service.assert_called_once_with("pool-1", difficulty=None, topic=None)
        add_word.assert_not_called()

    def test_detail_marks_words_already_saved(self, client):
        detail = {
            "pool": _fake_public_pool(),
            "words": [_fake_public_pool_word()],
        }
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=True), \
             patch("api.routes.vocabulary.public_vocab_pool_service.get_public_pool_detail",
                   return_value=detail), \
             patch("api.routes.vocabulary.firebase_service.get_user_word_list",
                   return_value=["Scalability"]):
            response = client.get("/api/v1/vocabulary/public-pools/pool-1")

        assert response.status_code == 200
        assert response.json()["words"][0]["already_saved"] is True

    def test_detail_returns_403_when_feature_flag_off(self, client):
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=False), \
             patch("api.routes.vocabulary.public_vocab_pool_service.get_public_pool_detail") as service:
            response = client.get("/api/v1/vocabulary/public-pools/pool-1")

        assert response.status_code == 403
        assert response.json()["error"]["code"] == ERR.forbidden.code
        service.assert_not_called()

    def test_detail_returns_404_for_unknown_pool(self, client):
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=True), \
             patch("api.routes.vocabulary.public_vocab_pool_service.get_public_pool_detail",
                   return_value=None):
            response = client.get("/api/v1/vocabulary/public-pools/missing")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == ERR.not_found.code

    def test_save_public_pool_word_copies_to_user_deck_with_public_source(self, client):
        saved_at = datetime(2026, 5, 28, tzinfo=timezone.utc)
        saved = _fake_vocab_doc("scalability", saved_at, topic="technology")
        saved["id"] = "user-word-1"
        saved["source"] = 5
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=True), \
             patch("api.routes.vocabulary.public_vocab_pool_service.get_public_pool_word",
                   return_value=_fake_public_pool_word()) as public_word, \
             patch("api.routes.vocabulary.firebase_service.get_word_by_text",
                   return_value=None), \
             patch("api.routes.vocabulary.firebase_service.count_user_vocabulary",
                   return_value=10), \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists",
                   return_value=("user-word-1", True)) as add_word, \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   return_value=saved):
            response = client.post(
                "/api/v1/vocabulary/public-pools/pool-1/words/master-1/save"
            )

        assert response.status_code == 200
        body = response.json()
        assert body["created"] is True
        assert body["already_saved"] is False
        assert body["word"]["source"] == "public_pool"
        public_word.assert_called_once_with("pool-1", "master-1")
        word_data = add_word.call_args.args[1]
        assert word_data["word"] == "scalability"
        assert word_data["source"] == 5
        assert word_data["topic"] == "technology"

    def test_save_public_pool_word_returns_existing_duplicate(self, client):
        existing = _fake_vocab_doc("scalability", datetime(2026, 5, 28, tzinfo=timezone.utc))
        existing["id"] = "existing-word"
        existing["source"] = 3
        with patch("api.routes.vocabulary.feature_flag_service.is_enabled",
                   return_value=True), \
             patch("api.routes.vocabulary.public_vocab_pool_service.get_public_pool_word",
                   return_value=_fake_public_pool_word()), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_text",
                   return_value=existing), \
             patch("api.routes.vocabulary.firebase_service.count_user_vocabulary") as count, \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists") as add_word:
            response = client.post(
                "/api/v1/vocabulary/public-pools/pool-1/words/master-1/save"
            )

        assert response.status_code == 200
        body = response.json()
        assert body["created"] is False
        assert body["already_saved"] is True
        assert body["word"]["id"] == "existing-word"
        count.assert_not_called()
        add_word.assert_not_called()


class TestAddWordWithAi:
    def test_draft_returns_ai_card_preview(self, client):
        with patch("api.routes.vocabulary.firebase_service.get_word_by_text",
                   return_value=None), \
             patch("api.routes.vocabulary.word_service.get_word_detail_fast",
                   new=AsyncMock(return_value=_complete_detail("scalability"))) as fast, \
             patch("api.routes.vocabulary.word_service.get_complete_word_detail",
                   new=AsyncMock()) as complete, \
             patch("api.routes.vocabulary.quota_service.check_and_increment") as quota:
            response = client.post("/api/v1/vocabulary/draft", json={"word": "scalability"})

        assert response.status_code == 200
        body = response.json()
        assert body["word"] == "scalability"
        assert body["definition"] == "scalability definition"
        assert body["example_en"] == "Example with scalability."
        assert body["ielts_tip"] == "Use scalability in academic writing."
        assert body["already_exists"] is False
        fast.assert_awaited_once()
        complete.assert_not_awaited()
        quota.assert_not_called()

    def test_draft_duplicate_does_not_call_ai(self, client):
        existing = _fake_vocab_doc("scalability", datetime(2026, 5, 27, tzinfo=timezone.utc))
        with patch("api.routes.vocabulary.firebase_service.get_word_by_text",
                   return_value=existing), \
             patch("api.routes.vocabulary.word_service.get_word_detail_fast",
                   new=AsyncMock()) as fast, \
             patch("api.routes.vocabulary.quota_service.check_and_increment") as quota:
            response = client.post("/api/v1/vocabulary/draft", json={"word": "scalability"})

        assert response.status_code == 200
        body = response.json()
        assert body["already_exists"] is True
        assert body["existing_word_id"] == "doc-scalability"
        fast.assert_not_awaited()
        quota.assert_not_called()

    def test_draft_malformed_empty_word_returns_registered_error(self, client):
        response = client.post("/api/v1/vocabulary/draft", json={"word": "   "})

        assert response.status_code == 400
        assert response.json()["error"]["code"] == ERR.vocab_word_empty.code

    def test_draft_rate_limited_by_ai_quota(self, client):
        with patch("api.routes.vocabulary.firebase_service.get_word_by_text",
                   return_value=None), \
             patch("api.routes.vocabulary.word_service.get_word_detail_fast",
                   new=AsyncMock(return_value=None)), \
             patch("api.routes.vocabulary.word_service.get_complete_word_detail",
                   new=AsyncMock()) as complete, \
             patch("api.routes.vocabulary.quota_service.check_and_increment",
                   side_effect=ApiError(ERR.quota_daily_exceeded, plan_quota=1, used=2, feature="vocab")):
            response = client.post("/api/v1/vocabulary/draft", json={"word": "scalability"})

        assert response.status_code == 429
        assert response.json()["error"]["code"] == ERR.quota_daily_exceeded.code
        complete.assert_not_awaited()

    def test_save_preview_without_second_ai_call(self, client):
        saved_at = datetime(2026, 5, 27, tzinfo=timezone.utc)
        saved = _fake_vocab_doc("scalability", saved_at, topic="technology")
        with patch("api.routes.vocabulary.word_service.get_word_detail_fast",
                   new=AsyncMock()) as fast, \
             patch("api.routes.vocabulary.firebase_service.get_word_by_text",
                   return_value=None), \
             patch("api.routes.vocabulary.firebase_service.count_user_vocabulary",
                   return_value=12), \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists",
                   return_value=("wid", True)) as add, \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   return_value=saved):
            response = client.post("/api/v1/vocabulary", json={
                "word": "scalability",
                "definition": "ability to grow",
                "definition_vi": "kha nang mo rong",
                "part_of_speech": "noun",
                "topic": "technology",
                "example_en": "Scalability matters.",
                "example_vi": "Vi example.",
                "use_ai": False,
            })

        assert response.status_code == 200
        assert response.json()["word"] == "scalability"
        fast.assert_not_awaited()
        word_data = add.call_args.args[1]
        assert word_data["definition"] == "ability to grow"
        assert word_data["source"] == 3

    def test_private_word_cap_blocks_add_before_ai(self, client):
        with patch("api.routes.vocabulary.firebase_service.get_word_by_text",
                   return_value=None), \
             patch("api.routes.vocabulary.firebase_service.count_user_vocabulary",
                   return_value=100), \
             patch("api.routes.vocabulary.word_service.get_word_detail_fast",
                   new=AsyncMock()) as fast, \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists") as add:
            response = client.post("/api/v1/vocabulary", json={
                "word": "constraint",
                "definition": "limit",
                "use_ai": False,
            })

        assert response.status_code == 429
        body = response.json()["error"]
        assert body["code"] == ERR.vocab_private_word_limit_exceeded.code
        assert body["params"]["limit"] == 100
        assert body["params"]["used"] == 100
        fast.assert_not_awaited()
        add.assert_not_called()

    def test_duplicate_add_bypasses_private_word_cap(self, client):
        existing = _fake_vocab_doc("scalability", datetime(2026, 5, 27, tzinfo=timezone.utc))
        with patch("api.routes.vocabulary.firebase_service.get_word_by_text",
                   return_value=existing), \
             patch("api.routes.vocabulary.firebase_service.count_user_vocabulary") as count, \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists") as add:
            response = client.post("/api/v1/vocabulary", json={
                "word": "scalability",
                "definition": "ability to grow",
                "use_ai": False,
            })

        assert response.status_code == 409
        assert response.json()["error"]["code"] == ERR.vocab_word_duplicate.code
        count.assert_not_called()
        add.assert_not_called()


class TestImportWords:
    def test_import_from_topic_returns_candidates(self, client):
        generated = [
            {
                "word": "sustainability",
                "definition_en": "ability to continue over time",
                "definition_vi": "tính bền vững",
                "part_of_speech": "noun",
                "example_en": "Sustainability is central to urban planning.",
                "example_vi": "Tính bền vững là trọng tâm trong quy hoạch đô thị.",
                "ielts_tip": "Use it in environment essays.",
            }
        ]
        with patch("api.routes.vocabulary.quota_service.check_and_increment") as quota, \
             patch("api.routes.vocabulary.firebase_service.get_user_word_list",
                   return_value=[]), \
             patch("api.routes.vocabulary.vocab_service.generate_import_candidates",
                   new=AsyncMock(return_value=generated)) as mock_gen:
            response = client.post("/api/v1/vocabulary/import/draft", json={
                "mode": "topic",
                "input": "environment",
                "count": 1,
            })

        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "topic"
        assert body["candidates"][0]["word"] == "sustainability"
        assert body["candidates"][0]["topic"] == "environment"
        assert body["duplicate_count"] == 0
        quota.assert_called_once()
        mock_gen.assert_awaited_once()

    def test_import_from_text_marks_duplicates(self, client):
        generated = [
            {"word": "resilience", "definition_en": "ability to recover"},
            {"word": "adaptation", "definition_en": "change to fit conditions"},
        ]
        with patch("api.routes.vocabulary.quota_service.check_and_increment"), \
             patch("api.routes.vocabulary.firebase_service.get_user_word_list",
                   return_value=["resilience"]), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_text",
                   return_value={"id": "existing-id", "word": "resilience"}), \
             patch("api.routes.vocabulary.vocab_service.generate_import_candidates",
                   new=AsyncMock(return_value=generated)):
            response = client.post("/api/v1/vocabulary/import/draft", json={
                "mode": "text",
                "input": "Cities need resilience and adaptation to climate risks.",
                "count": 2,
            })

        assert response.status_code == 200
        body = response.json()
        assert body["duplicate_count"] == 1
        assert body["candidates"][0]["already_exists"] is True
        assert body["candidates"][0]["existing_word_id"] == "existing-id"
        assert body["candidates"][1]["already_exists"] is False

    def test_import_rejects_count_above_plan_limit_before_ai(self, client):
        with patch("api.routes.vocabulary.quota_service.check_and_increment") as quota, \
             patch("api.routes.vocabulary.vocab_service.generate_import_candidates",
                   new=AsyncMock()) as mock_gen:
            response = client.post("/api/v1/vocabulary/import/draft", json={
                "mode": "topic",
                "input": "technology",
                "count": 6,
            })

        assert response.status_code == 400
        assert response.json()["error"]["code"] == ERR.vocab_import_count_exceeded.code
        quota.assert_not_called()
        mock_gen.assert_not_awaited()

    def test_import_rejects_input_above_plan_limit_before_ai(self, client):
        with patch("api.routes.vocabulary.quota_service.check_and_increment") as quota, \
             patch("api.routes.vocabulary.vocab_service.generate_import_candidates",
                   new=AsyncMock()) as mock_gen:
            response = client.post("/api/v1/vocabulary/import/draft", json={
                "mode": "text",
                "input": "x" * 1001,
                "count": 1,
            })

        assert response.status_code == 400
        assert response.json()["error"]["code"] == ERR.vocab_import_input_too_long.code
        quota.assert_not_called()
        mock_gen.assert_not_awaited()

    def test_import_rate_limit_does_not_call_ai(self, client):
        with patch("api.routes.vocabulary.quota_service.check_and_increment",
                   side_effect=ApiError(ERR.quota_daily_exceeded, plan_quota=1, used=2, feature="vocab")), \
             patch("api.routes.vocabulary.vocab_service.generate_import_candidates",
                   new=AsyncMock()) as mock_gen:
            response = client.post("/api/v1/vocabulary/import/draft", json={
                "mode": "topic",
                "input": "technology",
                "count": 1,
            })

        assert response.status_code == 429
        assert response.json()["error"]["code"] == ERR.quota_daily_exceeded.code
        mock_gen.assert_not_awaited()


class TestGenerateDaily:
    def test_ac2_generates_daily_words_when_none_cached(self, client):
        """AC2: POST /api/v1/vocabulary/daily generates and returns 10 words."""
        generated = [
            {"word": f"w{i}", "definition_en": f"def{i}", "definition_vi": f"vi{i}"}
            for i in range(10)
        ]
        add_calls = [f"wid{i}" for i in range(10)]
        add_iter = iter(add_calls)
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=None), \
             patch("api.routes.vocabulary.firebase_service.save_user_daily_words"), \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists",
                   side_effect=lambda uid, doc: (next(add_iter), True)), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   side_effect=lambda uid, wid: {"id": wid, "is_favourite": False, "srs_reps": 0}), \
             patch("api.routes.vocabulary.firebase_service.get_favourite_words",
                   return_value=[]), \
             patch("api.routes.vocabulary.vocab_service.generate_personal_daily_words",
                   new=AsyncMock(return_value=(generated, "Education & Learning"))):
            response = client.post("/api/v1/vocabulary/daily", json={})

        assert response.status_code == 200
        body = response.json()
        assert body["topic"] == "Education & Learning"
        assert len(body["words"]) == 10
        assert body["words"][0]["word"] == "w0"
        # word_id is persisted into the response so fill-blank quizzes can
        # target today's new words.
        assert body["words"][0]["word_id"] == "wid0"
        assert body["words"][0]["strength"] == "New"

    def test_daily_generation_passes_favourite_context(self, client):
        generated = [{"word": "thematic", "definition_en": "d"}]
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=None), \
             patch("api.routes.vocabulary.firebase_service.save_user_daily_words"), \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists",
                   return_value=("wid", True)), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   return_value={"id": "wid", "is_favourite": False, "srs_reps": 0}), \
             patch("api.routes.vocabulary.firebase_service.get_favourite_words",
                   return_value=["climate", "carbon", "renewable"]), \
             patch("api.routes.vocabulary.vocab_service.generate_personal_daily_words",
                   new=AsyncMock(return_value=(generated, "Environment"))) as mock_gen:
            response = client.post("/api/v1/vocabulary/daily", json={})

        assert response.status_code == 200
        assert mock_gen.call_args.kwargs["context_words"] == [
            "climate", "carbon", "renewable",
        ]

    def test_returns_cached_when_already_generated(self, client):
        ts = datetime(2026, 4, 17, tzinfo=timezone.utc)
        cached = {
            "topic": "Technology & Innovation",
            "generated_at": ts,
            "words": [{
                "word": "cached",
                "word_id": "wid-cached",
                "definition_en": "d",
                "definition_vi": "v",
                "is_favourite": False,
                "strength": "New",
            }],
        }
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   return_value={
                       "id": "wid-cached",
                       "is_favourite": False,
                       "srs_reps": 0,
                       "times_correct": 0,
                       "times_incorrect": 0,
                   }), \
             patch("api.routes.vocabulary.vocab_service.generate_personal_daily_words",
                   new=AsyncMock()) as mock_gen:
            response = client.post("/api/v1/vocabulary/daily", json={})

        assert response.status_code == 200
        body = response.json()
        assert body["topic"] == "Technology & Innovation"
        assert body["words"][0]["word"] == "cached"
        assert body["words"][0]["word_id"] == "wid-cached"
        assert body["reviewed_count"] == 0
        assert body["total_count"] == 1
        assert body["timezone"] == "Asia/Ho_Chi_Minh"
        assert body["next_reset_at"] is not None
        mock_gen.assert_not_called()

    def test_cached_daily_status_counts_reviewed_words(self, client):
        cached = {
            "topic": "Technology & Innovation",
            "generated_at": datetime(2026, 4, 17, tzinfo=timezone.utc),
            "words": [
                {"word": "reviewed", "word_id": "wid-1", "definition_en": "d"},
                {"word": "new", "word_id": "wid-2", "definition_en": "d"},
            ],
        }

        def get_word(_uid, word_id):
            if word_id == "wid-1":
                return {
                    "id": word_id,
                    "is_favourite": False,
                    "srs_reps": 1,
                    "times_correct": 1,
                    "times_incorrect": 0,
                }
            return {
                "id": word_id,
                "is_favourite": False,
                "srs_reps": 0,
                "times_correct": 0,
                "times_incorrect": 0,
            }

        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   side_effect=get_word), \
             patch("api.routes.vocabulary.vocab_service.generate_personal_daily_words",
                   new=AsyncMock()) as mock_gen:
            response = client.post("/api/v1/vocabulary/daily", json={})

        assert response.status_code == 200
        body = response.json()
        assert body["reviewed_count"] == 1
        assert body["total_count"] == 2
        assert body["words"][0]["reviewed"] is True
        assert body["words"][1]["reviewed"] is False
        mock_gen.assert_not_called()

    def test_backfills_word_ids_for_legacy_cached_words(self, client):
        """Cached entries from before this feature lack word_ids; the
        endpoint persists them into the user's deck and returns the ids."""
        ts = datetime(2026, 4, 17, tzinfo=timezone.utc)
        cached = {
            "topic": "Health",
            "generated_at": ts,
            "words": [
                {"word": "legacy1", "definition_en": "d1", "definition_vi": "v1"},
                {"word": "legacy2", "definition_en": "d2", "definition_vi": "v2"},
            ],
        }
        add_iter = iter(["wid-1", "wid-2"])
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.firebase_service.save_user_daily_words"), \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists",
                   side_effect=lambda uid, doc: (next(add_iter), True)), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   side_effect=lambda uid, wid: {"id": wid, "is_favourite": False, "srs_reps": 0}):
            response = client.post("/api/v1/vocabulary/daily", json={})

        assert response.status_code == 200
        body = response.json()
        assert [w["word_id"] for w in body["words"]] == ["wid-1", "wid-2"]

    def test_repairs_stale_cached_word_id(self, client):
        """Cached daily rows can hold a dead word_id after migrations or
        earlier persistence bugs. The endpoint should resolve the word back
        into the user's deck and return the live id so interactions work."""
        cached = {
            "topic": "Health",
            "generated_at": datetime(2026, 4, 17, tzinfo=timezone.utc),
            "words": [{
                "word": "stamina",
                "word_id": "stale-id",
                "definition_en": "ability to keep going",
                "definition_vi": "suc ben",
            }],
        }

        def get_word(_uid, word_id):
            if word_id == "stale-id":
                return None
            return {"id": word_id, "is_favourite": False, "srs_reps": 0}

        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.firebase_service.save_user_daily_words") as save_daily, \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists",
                   return_value=("wid-current", False)) as add_word, \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   side_effect=get_word), \
             patch("api.routes.vocabulary.vocab_service.generate_personal_daily_words",
                   new=AsyncMock()) as mock_gen:
            response = client.post("/api/v1/vocabulary/daily", json={})

        assert response.status_code == 200
        body = response.json()
        assert body["words"][0]["word_id"] == "wid-current"
        add_word.assert_called_once()
        saved_words = save_daily.call_args.args[2]
        assert saved_words[0]["word_id"] == "wid-current"
        mock_gen.assert_not_called()

    def test_adds_extra_daily_words_from_master_without_ai_when_detail_complete(self, client):
        cached = {
            "topic": "Technology",
            "generated_at": datetime(2026, 5, 27, tzinfo=timezone.utc),
            "words": [
                {
                    "word": "base",
                    "word_id": "wid-base",
                    "definition_en": "base definition",
                    "reviewed": True,
                }
            ],
        }

        def get_word(_uid, word_id):
            return {
                "wid-base": {"id": word_id, "is_favourite": False, "srs_reps": 1},
                "wid-extra": {"id": word_id, "is_favourite": False, "srs_reps": 0},
            }[word_id]

        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.vocab_service.generate_extra_daily_words",
                   new=AsyncMock(return_value=[{"word": "resilient"}])) as mock_extra, \
             patch("api.routes.vocabulary.word_service.get_word_detail_fast",
                   new=AsyncMock(return_value=_complete_detail("resilient"))), \
             patch("api.routes.vocabulary.word_service.get_complete_word_detail",
                   new=AsyncMock()) as mock_ai_detail, \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists",
                   return_value=("wid-extra", True)), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   side_effect=get_word), \
             patch("api.routes.vocabulary.firebase_service.save_user_daily_words") as mock_save:
            response = client.post("/api/v1/vocabulary/daily/extra", json={"count": 5})

        assert response.status_code == 200
        body = response.json()
        mock_extra.assert_awaited_once()
        mock_ai_detail.assert_not_awaited()
        assert body["extra_limit"] == 5
        assert body["extra_used"] == 1
        assert body["extra_remaining"] == 4
        assert body["words"][1]["word"] == "resilient"
        assert body["words"][1]["daily_source"] == "extra"
        saved_words = mock_save.call_args.args[2]
        assert saved_words[1]["daily_source"] == "extra"

    def test_extra_daily_words_enrich_missing_core_detail(self, client):
        cached = {
            "topic": "Technology",
            "generated_at": datetime(2026, 5, 27, tzinfo=timezone.utc),
            "words": [{"word": "base", "word_id": "wid-base", "definition_en": "d"}],
        }

        def get_word(_uid, word_id):
            return {"id": word_id, "is_favourite": False, "srs_reps": 0}

        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.vocab_service.generate_extra_daily_words",
                   new=AsyncMock(return_value=[{"word": "resilient"}])), \
             patch("api.routes.vocabulary.word_service.get_word_detail_fast",
                   new=AsyncMock(return_value={"word": "resilient"})), \
             patch("api.routes.vocabulary.word_service.get_complete_word_detail",
                   new=AsyncMock(return_value=_complete_detail("resilient"))) as mock_ai_detail, \
             patch("api.routes.vocabulary.firebase_service.add_word_if_not_exists",
                   return_value=("wid-extra", True)), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   side_effect=get_word), \
             patch("api.routes.vocabulary.firebase_service.save_user_daily_words"):
            response = client.post("/api/v1/vocabulary/daily/extra", json={"count": 1})

        assert response.status_code == 200
        mock_ai_detail.assert_awaited_once_with("resilient", 7.0)
        assert response.json()["words"][1]["definition_en"] == "resilient definition"

    def test_extra_daily_words_enforces_daily_limit(self, client):
        cached = {
            "topic": "Technology",
            "generated_at": datetime(2026, 5, 27, tzinfo=timezone.utc),
            "words": [
                {"word": f"extra-{i}", "daily_source": "extra"}
                for i in range(5)
            ],
        }
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.vocab_service.generate_extra_daily_words",
                   new=AsyncMock()) as mock_extra:
            response = client.post("/api/v1/vocabulary/daily/extra", json={"count": 1})

        assert response.status_code == 429
        body = response.json()["error"]
        assert body["code"] == "vocab.extra_limit_exceeded"
        assert body["params"]["limit"] == 5
        mock_extra.assert_not_awaited()


class TestGetDailyByDate:
    def test_daily_history_returns_cached_batches_with_progress_counts(self, client):
        docs = [
            {
                "id": "2026-05-27",
                "topic": "Technology",
                "generated_at": datetime(2026, 5, 27, 0, 30, tzinfo=timezone.utc),
                "words": [
                    {"word": "scalability", "word_id": "wid-1", "definition_en": "ability to grow"},
                    {
                        "word": "latency",
                        "word_id": "wid-2",
                        "definition_en": "delay",
                        "daily_source": "extra",
                    },
                ],
            },
            {
                "id": "2026-05-26",
                "topic": "Education",
                "generated_at": datetime(2026, 5, 26, 0, 30, tzinfo=timezone.utc),
                "words": [
                    {"word": "pedagogy", "word_id": "wid-3", "definition_en": "teaching method"},
                ],
            },
        ]

        with patch("api.routes.vocabulary.firebase_service.list_user_daily_words",
                   return_value=docs) as mock_history, \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id") as mock_get_word, \
             patch("api.routes.vocabulary.vocab_service.generate_personal_daily_words",
                   new=AsyncMock()) as mock_gen:
            response = client.get("/api/v1/vocabulary/daily/history?limit=10")

        assert response.status_code == 200
        body = response.json()
        mock_history.assert_called_once_with("test-user-1", 10)
        mock_get_word.assert_not_called()
        mock_gen.assert_not_called()
        assert body["timezone"] == "Asia/Ho_Chi_Minh"
        assert [item["date"] for item in body["items"]] == ["2026-05-27", "2026-05-26"]
        assert body["items"][0]["total_count"] == 2
        assert body["items"][0]["reviewed_count"] == 0
        assert body["items"][0]["favourite_count"] == 0
        assert body["items"][0]["weak_count"] == 0
        assert body["items"][0]["mastered_count"] == 0
        assert body["items"][0]["words"] == []
        assert body["items"][1]["mastered_count"] == 0

    def test_daily_history_empty_state_uses_cache_only(self, client):
        with patch("api.routes.vocabulary.firebase_service.list_user_daily_words",
                   return_value=[]), \
             patch("api.routes.vocabulary.vocab_service.generate_personal_daily_words",
                   new=AsyncMock()) as mock_gen:
            response = client.get("/api/v1/vocabulary/daily/history")

        assert response.status_code == 200
        assert response.json() == {"items": [], "timezone": "Asia/Ho_Chi_Minh"}
        mock_gen.assert_not_called()

    def test_returns_cached_for_valid_date(self, client):
        ts = datetime(2026, 4, 17, tzinfo=timezone.utc)
        cached = {"topic": "Health", "generated_at": ts,
                  "words": [{"word": "cached", "word_id": "wid-cached", "definition_en": "d"}]}
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   return_value={"id": "wid-cached", "is_favourite": False, "srs_reps": 0}):
            response = client.get("/api/v1/vocabulary/daily/2026-04-17")
        assert response.status_code == 200
        assert response.json()["topic"] == "Health"

    def test_404_when_no_cached_daily(self, client):
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=None):
            response = client.get("/api/v1/vocabulary/daily/2026-04-17")
        assert response.status_code == 404

    def test_400_for_invalid_date_format(self, client):
        response = client.get("/api/v1/vocabulary/daily/invalid-date")
        assert response.status_code == 400
