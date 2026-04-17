"""Integration tests for /api/v1/topics (US-1.1)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {"id": "test-user-1", "name": "Alice", "target_band": 7.0, "topics": []}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


class TestListTopics:
    def test_returns_all_topics_with_counts(self, client):
        counts = {"education": 12, "environment": 38, "technology": 3}
        with patch("api.routes.topics.firebase_service.count_words_by_topic",
                   return_value=counts):
            response = client.get("/api/v1/topics")

        assert response.status_code == 200
        body = response.json()

        assert len(body["items"]) >= 6  # data/ielts_topics.json ships with 12
        by_id = {t["id"]: t for t in body["items"]}
        assert by_id["education"]["word_count"] == 12
        assert by_id["environment"]["word_count"] == 38
        assert by_id["technology"]["word_count"] == 3
        assert by_id["health"]["word_count"] == 0
        assert body["total_words"] == 53

    def test_topic_includes_name_and_subtopics(self, client):
        with patch("api.routes.topics.firebase_service.count_words_by_topic",
                   return_value={}):
            response = client.get("/api/v1/topics")

        body = response.json()
        env = next(t for t in body["items"] if t["id"] == "environment")
        assert env["name"] == "Environment & Nature"
        assert "pollution" in env["subtopics"]

    def test_zero_counts_when_no_vocabulary(self, client):
        with patch("api.routes.topics.firebase_service.count_words_by_topic",
                   return_value={}):
            response = client.get("/api/v1/topics")

        body = response.json()
        assert body["total_words"] == 0
        assert all(t["word_count"] == 0 for t in body["items"])
