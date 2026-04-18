"""Integration tests for PATCH /api/v1/me (US-4.3)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {
    "id": "123",
    "name": "Alice",
    "email": "alice@example.com",
    "target_band": 7.0,
    "topics": ["environment"],
    "streak": 2,
    "total_words": 10,
    "total_quizzes": 0,
    "total_correct": 0,
    "challenge_wins": 0,
    "weekly_goal_minutes": 150,
}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: dict(FAKE_USER)
    return TestClient(app)


class TestPatchMe:
    def test_sets_exam_date_and_weekly_goal(self, client):
        captured: dict = {}

        def upd(_uid, data):
            captured.update(data)

        with patch(
            "api.routes.auth.firebase_service.update_user",
            side_effect=upd,
        ):
            res = client.patch(
                "/api/v1/me",
                json={"exam_date": "2026-06-01", "weekly_goal_minutes": 210},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["exam_date"] == "2026-06-01"
        assert body["weekly_goal_minutes"] == 210
        assert captured["exam_date"] == "2026-06-01"
        assert captured["weekly_goal_minutes"] == 210

    def test_empty_string_clears_exam_date(self, client):
        captured: dict = {}

        def upd(_uid, data):
            captured.update(data)

        with patch(
            "api.routes.auth.firebase_service.update_user",
            side_effect=upd,
        ):
            res = client.patch("/api/v1/me", json={"exam_date": ""})
        assert res.status_code == 200
        assert res.json()["exam_date"] is None
        assert captured["exam_date"] is None

    def test_invalid_date_rejected(self, client):
        res = client.patch("/api/v1/me", json={"exam_date": "tomorrow"})
        assert res.status_code == 400

    def test_out_of_range_goal_rejected(self, client):
        res = client.patch("/api/v1/me", json={"weekly_goal_minutes": 5})
        assert res.status_code == 422

    def test_partial_update_leaves_other_fields(self, client):
        captured: dict = {}

        def upd(_uid, data):
            captured.update(data)

        with patch(
            "api.routes.auth.firebase_service.update_user",
            side_effect=upd,
        ):
            res = client.patch("/api/v1/me", json={"target_band": 8.0})
        assert res.status_code == 200
        body = res.json()
        assert body["target_band"] == 8.0
        # Unchanged fields still reflect original
        assert body["name"] == "Alice"
        assert "exam_date" not in captured
