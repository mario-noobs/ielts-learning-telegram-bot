"""Integration tests for /api/v1/vocabulary endpoints (US-1.1)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.errors import ERR, ApiError
from api.main import create_app

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
                  "words": [{"word": "cached", "definition_en": "d"}]}
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.firebase_service.get_word_by_id",
                   return_value=None):
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
