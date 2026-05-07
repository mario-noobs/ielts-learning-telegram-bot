"""Integration tests for /api/v1/vocabulary endpoints (US-1.1)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
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
        "srs_interval": 1,
        "srs_ease": 2.5,
        "srs_reps": 0,
        "srs_next_review": added_at,
        "times_correct": 0,
        "times_incorrect": 0,
        "added_at": added_at,
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
        assert "strength" in body["items"][0]
        assert body["next_cursor"] is None  # fewer than limit
        mock_fn.assert_called_once_with("test-user-1", 20, None)

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

    def test_empty_vocabulary(self, client):
        with patch("api.routes.vocabulary.firebase_service.get_user_vocabulary_page",
                   return_value=[]):
            response = client.get("/api/v1/vocabulary")
        assert response.status_code == 200
        assert response.json() == {"items": [], "next_cursor": None}


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
            }],
        }
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached), \
             patch("api.routes.vocabulary.vocab_service.generate_personal_daily_words",
                   new=AsyncMock()) as mock_gen:
            response = client.post("/api/v1/vocabulary/daily", json={})

        assert response.status_code == 200
        body = response.json()
        assert body["topic"] == "Technology & Innovation"
        assert body["words"][0]["word"] == "cached"
        assert body["words"][0]["word_id"] == "wid-cached"
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
                   side_effect=lambda uid, doc: (next(add_iter), True)):
            response = client.post("/api/v1/vocabulary/daily", json={})

        assert response.status_code == 200
        body = response.json()
        assert [w["word_id"] for w in body["words"]] == ["wid-1", "wid-2"]


class TestGetDailyByDate:
    def test_returns_cached_for_valid_date(self, client):
        ts = datetime(2026, 4, 17, tzinfo=timezone.utc)
        cached = {"topic": "Health", "generated_at": ts,
                  "words": [{"word": "cached", "definition_en": "d"}]}
        with patch("api.routes.vocabulary.firebase_service.get_user_daily_words",
                   return_value=cached):
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
