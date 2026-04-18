"""Integration tests for /api/v1/plan (US-4.1)."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {
    "id": "123",
    "name": "Alice",
    "target_band": 6.5,
    "topics": ["environment"],
    "total_words": 20,
}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def _fake_weakness(**overrides) -> dict:
    base = {
        "due_srs_count": 4,
        "total_vocab": 20,
        "daily_words_done_today": False,
        "last_writing_band": 0.0,
        "writing_sample_size": 0,
        "last_listening_score": 0.0,
        "listening_sample_size": 0,
        "weakest_listening_type": "dictation",
        "streak": 0,
    }
    base.update(overrides)
    return base


class TestGetTodayPlan:
    def test_generates_and_caches(self, client):
        captured: dict = {}

        def save(_uid, _date, plan):
            captured["plan"] = plan

        with patch(
            "api.routes.plan.firebase_service.get_daily_plan",
            return_value=None,
        ), patch(
            "api.routes.plan.weakness_service.build_weakness_profile",
            return_value=_fake_weakness(),
        ), patch(
            "api.routes.plan.firebase_service.save_daily_plan",
            side_effect=save,
        ):
            res = client.get("/api/v1/plan/today")

        assert res.status_code == 200
        body = res.json()
        assert 3 <= len(body["activities"]) <= 5
        assert body["total_minutes"] <= body["cap_minutes"]
        # First call wrote to cache
        assert "plan" in captured
        # SRS always first when due
        assert body["activities"][0]["id"] == "srs_review"

    def test_returns_cached_when_present(self, client):
        stored = {
            "date": "2026-04-18",
            "activities": [
                {"id": "srs_review", "type": "srs_review", "title": "x",
                 "description": "", "estimated_minutes": 5, "route": "/review",
                 "meta": {}, "completed": True},
            ],
            "total_minutes": 5,
            "cap_minutes": 30,
            "exam_urgent": False,
            "days_until_exam": None,
            "completed_count": 1,
            "generated_at": datetime.now(timezone.utc),
        }
        with patch(
            "api.routes.plan.firebase_service.get_daily_plan",
            return_value=stored,
        ):
            res = client.get("/api/v1/plan/today")
        assert res.status_code == 200
        body = res.json()
        assert body["completed_count"] == 1
        assert body["activities"][0]["completed"] is True


class TestCompleteActivity:
    def test_marks_and_returns_updated_plan(self, client):
        stored = {
            "date": "2026-04-18",
            "activities": [
                {"id": "a", "type": "writing", "title": "", "description": "",
                 "estimated_minutes": 10, "route": "/write", "meta": {},
                 "completed": False},
                {"id": "b", "type": "listening", "title": "", "description": "",
                 "estimated_minutes": 8, "route": "/listening", "meta": {},
                 "completed": False},
            ],
            "total_minutes": 18,
            "cap_minutes": 30,
            "completed_count": 0,
        }
        updates: dict = {}

        def upd(_uid, _date, payload):
            updates.update(payload)

        with patch(
            "api.routes.plan.firebase_service.get_daily_plan",
            return_value=stored,
        ), patch(
            "api.routes.plan.firebase_service.update_daily_plan",
            side_effect=upd,
        ):
            res = client.post("/api/v1/plan/today/complete/b")

        assert res.status_code == 200
        body = res.json()
        assert body["completed_count"] == 1
        assert body["activities"][1]["completed"] is True
        assert updates["completed_count"] == 1

    def test_missing_plan_returns_404(self, client):
        with patch(
            "api.routes.plan.firebase_service.get_daily_plan",
            return_value=None,
        ):
            res = client.post("/api/v1/plan/today/complete/anything")
        assert res.status_code == 404

    def test_unknown_activity_returns_404(self, client):
        stored = {
            "date": "2026-04-18",
            "activities": [
                {"id": "a", "type": "writing", "title": "", "description": "",
                 "estimated_minutes": 10, "route": "/", "meta": {},
                 "completed": False},
            ],
            "completed_count": 0,
        }
        with patch(
            "api.routes.plan.firebase_service.get_daily_plan",
            return_value=stored,
        ):
            res = client.post("/api/v1/plan/today/complete/ghost")
        assert res.status_code == 404
